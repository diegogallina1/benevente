"""Is a global equity sleeve the diversification the domestic basket is not?

Every widening tested so far drew from the same B3 factor ranking, and the
sixth-to-twentieth names came back 0.93 correlated with the top five. This
measures the first exposure in the project that is not another draw from that
ranking: a B3-listed fund holding the S&P 500 in reais, carved out of the
equity budget rather than added to it.

The window starts at the 2016 decision, the first January at which IVVB11 had a
complete trailing year. Comparing a sleeve that does not exist yet against one
that does would credit the sleeve with years it could not have been held in.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 BrazilianTaxModel, apply_annual_taxes)
from config import SystemConfig
from profile_ladder import DATA_INPUTS, LADDER, protocol_for
from total_return_adapter import load_total_return_export

GLOBAL_TICKER = "IVVB11"
SLEEVE_FRACTIONS = (0.0, .10, .20, .30)
# First January at which the fund had a complete trailing year.
FIRST_DECISION_YEAR = 2016

GLOBAL_INPUTS = {
    **DATA_INPUTS,
    "prices": Path("data/prices_b3_with_global_2011_2025.csv"),
    "total_return_manifest": Path("data/prices_b3_with_global_2011_2025_manifest.json"),
}


def build_global_engine() -> tuple[AnnualWalkForwardEngine, pd.DataFrame]:
    prices, _ = load_total_return_export(str(GLOBAL_INPUTS["prices"]), str(GLOBAL_INPUTS["total_return_manifest"]))
    fundamentals = pd.read_csv(GLOBAL_INPUTS["fundamentals"], parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(str(GLOBAL_INPUTS["universe"]), str(GLOBAL_INPUTS["mapping"]))
    benchmarks = pd.read_csv(GLOBAL_INPUTS["benchmarks"], parse_dates=["date"]).set_index("date")
    panel = prices.set_index("date")
    return AnnualWalkForwardEngine(panel, snapshots_from_frame(fundamentals), SystemConfig(),
                                   evidence, benchmarks), panel


def _metrics(results: pd.DataFrame, engine: AnnualWalkForwardEngine) -> dict:
    net = results.net_return
    wealth = (1 + net).cumprod()
    excess = (net - results.cdi_net_return).dropna()
    daily = engine.daily_curve
    curve = daily[daily.decision_year.isin(results.decision_year)].strategy
    return {
        "anos": len(net),
        "cagr": float(wealth.iloc[-1] ** (1 / len(net)) - 1),
        "cagr_pos_ir": float((1 + results.net_return_after_tax).prod() ** (1 / len(net)) - 1),
        "vol": float(net.std(ddof=1)),
        "pior_ano": float(net.min()),
        "drawdown": float((curve / curve.cummax() - 1).min()),
        "sharpe_excesso": float(excess.mean() / excess.std(ddof=1)),
        "ganha_cdi": int((net > results.cdi_net_return).sum()),
        "giro_medio": float(results.turnover.mean()),
    }


def sleeve_correlation(engine: AnnualWalkForwardEngine, panel: pd.DataFrame,
                       start_year: int, end_year: int) -> dict:
    """Correlation between the domestic equity sleeve and the global fund.

    This is the number the whole sleeve rests on. A wider domestic basket
    measured 0.93 against the concentrated one; anything near that here would
    mean the fund is not diversification either.
    """
    protocol = replace(protocol_for("equilibrado", start_year, end_year), global_sleeve_fraction=0.0)
    results, _, _ = engine.run(protocol)
    daily = engine.daily_curve
    curve = daily[daily.decision_year.isin(results.decision_year)].copy()
    curve["date"] = pd.to_datetime(curve.date)
    sleeve = curve.set_index("date").equity_sleeve.pct_change().dropna()
    fund = panel[GLOBAL_TICKER].reindex(sleeve.index).pct_change().dropna()
    joined = pd.concat([sleeve, fund], axis=1).dropna()
    joined.columns = ["sleeve_b3", "global"]
    annual = joined.groupby(joined.index.year).apply(lambda frame: (1 + frame).prod() - 1)
    return {
        "correlacao_diaria": float(joined.corr().iloc[0, 1]),
        "correlacao_anual": float(annual.corr().iloc[0, 1]),
        "sessoes": int(len(joined)),
        "anos": int(len(annual)),
        "retorno_anual_medio_sleeve_b3": float(annual.sleeve_b3.mean()),
        "retorno_anual_medio_global": float(annual["global"].mean()),
    }


def run(output: Path, start_year: int, end_year: int) -> pd.DataFrame:
    engine, panel = build_global_engine()
    rows = []
    for profile in LADDER:
        for fraction in SLEEVE_FRACTIONS:
            protocol = replace(protocol_for(profile, start_year, end_year),
                               global_sleeve_ticker=GLOBAL_TICKER if fraction else None,
                               global_sleeve_fraction=fraction)
            results, _, holdings = engine.run(protocol)
            results = apply_annual_taxes(results, BrazilianTaxModel())
            sleeve = holdings[holdings.ticker.eq(GLOBAL_TICKER)]
            rows.append({"perfil": profile, "global": fraction,
                         "anos_com_sleeve": int(sleeve.decision_year.nunique()),
                         **_metrics(results, engine)})
    frame = pd.DataFrame(rows)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "global_sleeve_by_profile.csv", index=False)
    correlation = sleeve_correlation(engine, panel, start_year, end_year)
    (output / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "instrument": GLOBAL_TICKER,
        "first_decision_year": FIRST_DECISION_YEAR,
        "correlation": correlation,
        "limitations": [
            "The fund is declared policy, never selected; it has no CVM filing and no fundamental screen.",
            "Its adjusted close carries the management fee; brokerage and spread on the sleeve use the engine's "
            "liquidity floor, which overstates its execution cost.",
            "Unhedged: the series contains the BRL/USD move, which is part of the exposure being bought.",
            "A public adjusted-close feed, with no primary reconciliation of its own.",
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(correlation, indent=2, ensure_ascii=False))
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure a declared global equity sleeve against the ladder.")
    parser.add_argument("--output", default="artifacts/global_sleeve_v1")
    parser.add_argument("--start-year", type=int, default=FIRST_DECISION_YEAR - 1)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    frame = run(Path(args.output), args.start_year, args.end_year)
    print(frame.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
