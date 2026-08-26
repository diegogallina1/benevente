"""Freeze and run the three declared profile configurations.

The nested search exists to prove a rule does not need hindsight to be chosen.
Widened to 256 candidates it stopped doing that: on identical inputs, code and
window, going from 36 to 256 candidates cost 2.63 percentage points of CAGR a
year and pushed the deflated Sharpe below significance. With ten annual
observations, ranking that many candidates on trailing Sharpe selects noise.

So this ladder is *declared*, not searched. One configuration per investor
profile, frozen with the SHA-256 of every input, evaluated prospectively from
2027. The in-sample numbers this module prints are exploratory and are recorded
only so a later reader can see what was known when the choice was made.

Scope: this freezes selection and the equity budget. The intra-year risk
overlay is a separate policy, already registered as
``benevente_profile_risk_v1``; combining the two has not been measured and must
not be assumed additive.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json

import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 BrazilianTaxModel, _annual_benchmark_summary, apply_annual_taxes)
from config import SystemConfig
from corporate_action_reconciliation import file_sha256
from research_configuration_search import ISSUER_CAP_SLACK, MAXIMUM_ISSUER_CAP
from total_return_adapter import load_total_return_export

ROOT = Path(__file__).resolve().parent

# One configuration per profile. The equity budget is the risk dial: within a
# configuration family the Sharpe of the excess over CDI is invariant to it
# (eq35, eq55 and eq75 of n5_triple_factor all measured 0.7602), so the budget
# moves risk and return together without buying or destroying efficiency.
# The holding count moves the other way: measured across the whole factorial,
# a twenty-name book had the best excess Sharpe (0.512) and the mildest worst
# year (-3.8%), and a five-name book the highest raw return.
LADDER: dict[str, dict] = {
    "conservador": {
        "maximum_equity_weight": .35, "top_assets": 12,
        "rationale": "Widest basket at the smallest budget. The worst calendar year measured in sample was "
                     "positive; the profile buys stability, not upside.",
    },
    "equilibrado": {
        "maximum_equity_weight": .55, "top_assets": 8,
        "rationale": "The published budget with a wider basket than the published five names, at the point "
                     "where the count stops costing efficiency.",
    },
    "arrojado": {
        "maximum_equity_weight": .95, "top_assets": 5,
        "rationale": "Concentration and the largest budget. The in-sample worst year was -21%, which is the "
                     "cost the profile exists to accept.",
    },
}
# A governance limit, not a performance improvement. Measured where it binds it
# cost 0.15 percentage points of CAGR and improved the excess Sharpe in none of
# the twenty configurations affected. It is frozen because an undeclared sector
# bet is a governance failure even in the years it happens to pay.
MAXIMUM_NAMES_PER_SECTOR = 3
FACTOR = "triple_factor"
CONFIRMATORY_FROM_YEAR = 2027

DATA_INPUTS = {
    "prices": ROOT / "data/prices_b3_total_return_full_2011_2025.csv",
    "total_return_manifest": ROOT / "data/prices_b3_total_return_full_2011_2025_manifest.json",
    "fundamentals": ROOT / "data/fundamentals_b3_cvm_full_2013_2025_v2.csv",
    "universe": ROOT / "data/b3_historical_universes.csv",
    "mapping": ROOT / "data/b3_historical_cvm_ticker_map.csv",
    "benchmarks": ROOT / "data/benchmarks_market_2011_2025.csv",
}
CODE_INPUTS = [ROOT / "annual_walk_forward.py", ROOT / "portfolio_risk.py", ROOT / "profile_ladder.py"]


def protocol_for(profile: str, start_year: int, end_year: int) -> AnnualWalkForwardConfig:
    """The frozen protocol for one profile, with the issuer cap derived."""
    item = LADDER[profile]
    budget, count = float(item["maximum_equity_weight"]), int(item["top_assets"])
    return AnnualWalkForwardConfig(
        start_year, end_year, factor=FACTOR, top_assets=count,
        maximum_equity_weight=budget,
        maximum_asset_weight=round(min(MAXIMUM_ISSUER_CAP, budget / count * ISSUER_CAP_SLACK), 6),
        maximum_names_per_sector=MAXIMUM_NAMES_PER_SECTOR,
    )


def build_engine() -> AnnualWalkForwardEngine:
    prices, _ = load_total_return_export(str(DATA_INPUTS["prices"]), str(DATA_INPUTS["total_return_manifest"]))
    fundamentals = pd.read_csv(DATA_INPUTS["fundamentals"], parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(str(DATA_INPUTS["universe"]), str(DATA_INPUTS["mapping"]))
    benchmarks = pd.read_csv(DATA_INPUTS["benchmarks"], parse_dates=["date"]).set_index("date")
    return AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals),
                                   SystemConfig(), evidence, benchmarks)


def register(output: Path) -> dict:
    """Write the frozen ladder. It records no performance statistic by design."""
    payload = {
        "policy": "benevente_profile_ladder_v1",
        "status": "registered_not_prospectively_validated",
        "registered_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "confirmatory_sample_starts": f"first B3 trading session of {CONFIRMATORY_FROM_YEAR}",
        "selection_method": "declared, not searched",
        "why_not_searched": (
            "On identical inputs, code and window (2016-2025) a 36-candidate nested search returned 15.31% a "
            "year with a deflated Sharpe of 0.957, and the same search over 256 candidates returned 12.68% "
            "with a deflated Sharpe of 0.777, below significance. The expected maximum Sharpe under the null "
            "rose from 0.375 to 0.746. Ten annual observations cannot rank 256 candidates."
        ),
        "signal_family": FACTOR,
        "review_frequency": "annual",
        "maximum_names_per_sector": MAXIMUM_NAMES_PER_SECTOR,
        "sector_limit_status": (
            "Governance constraint. Where it binds it cost 0.15 percentage points of CAGR and improved the "
            "excess Sharpe in none of the twenty configurations affected. It is not claimed to improve returns."
        ),
        "intrayear_overlay": "not included; see benevente_profile_risk_v1. The combination is unmeasured.",
        "profiles": {
            profile: {
                "maximum_equity_weight": item["maximum_equity_weight"],
                "top_assets": item["top_assets"],
                "maximum_asset_weight": protocol_for(profile, 2012, 2026).maximum_asset_weight,
                "rationale": item["rationale"],
            }
            for profile, item in LADDER.items()
        },
        "inputs": {name: file_sha256(path) for name, path in DATA_INPUTS.items()},
        "code": {path.name: file_sha256(path) for path in CODE_INPUTS},
        "success_criterion": {
            "minimum_years": 3,
            "must_beat_cdi_after_tax": True,
            "must_beat_investable_market_etf": True,
            "profile_ordering_must_hold": "conservador <= equilibrado <= arrojado in realised risk and return",
            "falsification": (
                "A profile that fails to clear the CDI after tax over the full prospective window, or a ladder "
                "whose realised risk ordering inverts, refutes the policy. One good year confirms nothing."
            ),
        },
        "non_negotiable_gates": {
            "no_parameter_change_after_sample_start": True,
            "in_sample_window_is_exploratory": "2013-2025",
        },
    }
    payload["registration_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def run(output: Path, start_year: int, end_year: int) -> pd.DataFrame:
    engine = build_engine()
    rows = []
    for profile in LADDER:
        protocol = protocol_for(profile, start_year, end_year)
        results, transitions, holdings = engine.run(protocol)
        results = apply_annual_taxes(results, BrazilianTaxModel())
        target = output / profile
        target.mkdir(parents=True, exist_ok=True)
        results.to_csv(target / "annual_results.csv", index=False)
        transitions.to_csv(target / "annual_transitions.csv", index=False)
        holdings.to_csv(target / "annual_holdings.csv", index=False)
        _annual_benchmark_summary(results).to_csv(target / "annual_benchmark_summary.csv", index=False)
        if not engine.daily_curve.empty:
            daily = engine.daily_curve
            daily[daily.decision_year.isin(results.decision_year)].to_csv(target / "daily_curve.csv", index=False)
        (target / "protocol.json").write_text(json.dumps(asdict(protocol), indent=2, ensure_ascii=False),
                                              encoding="utf-8")
        net = results.net_return
        wealth = (1 + net).cumprod()
        excess = (net - results.cdi_net_return).dropna()
        rows.append({
            "perfil": profile, "acoes": protocol.maximum_equity_weight, "posicoes": protocol.top_assets,
            "teto_emissor": protocol.maximum_asset_weight, "anos": len(net),
            "cagr": wealth.iloc[-1] ** (1 / len(net)) - 1,
            "cagr_pos_ir": (1 + results.net_return_after_tax).prod() ** (1 / len(net)) - 1,
            "vol": net.std(ddof=1), "pior_ano": net.min(),
            "sharpe_excesso": excess.mean() / excess.std(ddof=1),
            "ganha_cdi": int((net > results.cdi_net_return).sum()),
            "giro_medio": results.turnover.mean(),
            "posicoes_medias": results.equity_positions.mean(),
            "setores_medios": results.distinct_sectors.mean(),
            "cdi_cagr": (1 + results.cdi_net_return).prod() ** (1 / len(net)) - 1,
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(output / "ladder_summary.csv", index=False)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze and run the declared profile ladder.")
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--registration", default="data/benevente_profile_ladder_v1_registration.json")
    parser.add_argument("--output", default="artifacts/profile_ladder_v1")
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    if args.register:
        payload = register(Path(args.registration))
        print(f"registered {payload['policy']} sha256={payload['registration_sha256'][:16]}")
    if args.run:
        summary = run(Path(args.output), args.start_year, args.end_year)
        print(summary.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
