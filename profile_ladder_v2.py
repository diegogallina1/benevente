"""The v2 profile ladder: selection, global sleeve and intra-year overlay.

v1 declared one configuration per profile and stopped there. Two layers were
then measured against it and both survived, so v2 is v1 plus those two, with one
parameter changed and one policy conflict resolved.

What changed from v1, and why:

* **A declared global sleeve**, twenty per cent of the equity budget in a
  B3-listed fund holding the S&P 500 in reais. It is carved out of the budget,
  not added to it. Its daily correlation with the domestic sleeve is 0.064,
  against 0.93 for simply owning more Brazilian names.
* **The intra-year overlay, with the fund outside it.** The overlay moves the
  domestic sleeve to CDI on observable Ibovespa stress and leaves the fund
  alone, because selling the uncorrelated asset on a domestic signal discards
  the reason for holding it. Measured risk-matched, keeping it outside beat
  keeping it inside in all three profiles.
* **Arrojado drops from 95% to 75% in equities.** Two registered policies
  disagreed: this ladder said 95% and ``benevente_profile_risk_v1`` said 75%.
  The measurement settled it rather than a preference -- at 75% the full stack
  returns 19.87% a year with a 28.9% drawdown, against 20.74% and 34.4% at 95%.
  The extra twenty points of equity buy 0.87 points of return and cost 5.5
  points of drawdown. Adopting 75% also makes the two registrations agree
  without revoking either.

This module does not register itself. Running ``--register`` is a human act, and
in a system whose whole thesis is that a person signs the decision, a policy
that registered itself would be the first violation of it.
"""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json
import subprocess

import pandas as pd

from annual_walk_forward import AnnualWalkForwardConfig, BrazilianTaxModel, apply_annual_taxes
from benevente2_event_risk import reconcile_daily_returns
from corporate_action_reconciliation import file_sha256
from profile_intrayear_risk import FIXED_OVERLAY, apply_profile_overlay
from profile_ladder import CODE_INPUTS, MAXIMUM_NAMES_PER_SECTOR, FACTOR
from research_configuration_search import ISSUER_CAP_SLACK, MAXIMUM_ISSUER_CAP
from research_global_sleeve import GLOBAL_INPUTS, GLOBAL_TICKER, build_global_engine
from research_ladder_v2 import _annual_rebalanced_blend, _daily, _metrics

ROOT = Path(__file__).resolve().parent
CONFIRMATORY_FROM_YEAR = 2027
GLOBAL_FRACTION = .20

LADDER_V2: dict[str, dict] = {
    "conservador": {
        "maximum_equity_weight": .35, "top_assets": 12,
        "rationale": "Widest basket at the smallest budget. With the two layers the worst calendar "
                     "year measured in sample was positive and the drawdown halved.",
    },
    "equilibrado": {
        "maximum_equity_weight": .55, "top_assets": 8,
        "rationale": "The published budget with a wider basket, at the count where diversification "
                     "stops costing efficiency.",
    },
    "arrojado": {
        "maximum_equity_weight": .75, "top_assets": 5,
        "rationale": "Concentration, at the budget the measurement supports. 95% returned 0.87 points "
                     "more a year for 5.5 points more drawdown and a worse excess Sharpe.",
    },
}


def _issuer_cap(budget: float, count: int) -> float:
    return round(min(MAXIMUM_ISSUER_CAP, budget / count * ISSUER_CAP_SLACK), 6)


def domestic_protocol(profile: str, start_year: int, end_year: int) -> AnnualWalkForwardConfig:
    """The domestic book, sized so the fund's share lands exactly on target.

    Holding a share ``s`` of the whole portfolio in the fund dilutes the CDI
    residual as well as the equity, so the domestic budget has to be solved
    rather than simply scaled; otherwise the profile quietly ends up holding
    more equity than it declares.
    """
    item = LADDER_V2[profile]
    budget, count = float(item["maximum_equity_weight"]), int(item["top_assets"])
    share = budget * GLOBAL_FRACTION
    return AnnualWalkForwardConfig(
        start_year, end_year, factor=FACTOR, top_assets=count,
        maximum_equity_weight=budget * (1 - GLOBAL_FRACTION) / (1 - share),
        maximum_asset_weight=_issuer_cap(budget, count),
        maximum_names_per_sector=MAXIMUM_NAMES_PER_SECTOR,
    )


def evaluate(profile: str, engine, panel: pd.DataFrame, start_year: int, end_year: int) -> tuple[pd.Series, dict]:
    """Daily returns of the full v2 stack for one profile."""
    protocol = domestic_protocol(profile, start_year, end_year)
    results, _, _ = engine.run(protocol)
    results = apply_annual_taxes(results, BrazilianTaxModel())
    daily = _daily(engine, results)
    overlaid = apply_profile_overlay(
        daily, daily.decision_year.map(results.set_index("decision_year").target_equity_weight), profile)
    fund = panel[GLOBAL_TICKER].reindex(daily.date).pct_change().fillna(0.0).reset_index(drop=True)
    share = float(LADDER_V2[profile]["maximum_equity_weight"]) * GLOBAL_FRACTION
    blended = _annual_rebalanced_blend(overlaid.protected_return, fund, daily.decision_year, share)
    realised_equity = float((1 - share) * results.target_equity_weight.mean() + share)
    return blended, {"daily": daily, "results": results, "realised_equity": realised_equity, "share": share}


def resolve_approver(explicit: str | None) -> tuple[str, str]:
    """Who is freezing this policy, and how we know.

    Neither v1 nor the risk policy recorded a signer, which is a gap in a system
    whose thesis is that an identified person signs the decision. A registration
    with no name attached is an audit trail that stops exactly where it matters.
    Falling back to the repository identity is acceptable because that identity
    is already attached to every commit; falling back to nothing is not.
    """
    if explicit:
        return explicit.strip(), "explicit"
    try:
        name = subprocess.run(["git", "config", "user.name"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        name = ""
    if not name:
        raise SystemExit("Recuse-se a registrar sem assinante: informe --approved-by ou configure git config user.name")
    return name, "git identity"


def register(output: Path, approved_by: str | None = None) -> dict:
    approver, approval_source = resolve_approver(approved_by)
    payload = {
        "policy": "benevente_profile_ladder_v2",
        "approved_by": approver,
        "approval_source": approval_source,
        "supersedes": "benevente_profile_ladder_v1",
        "status": "registered_not_prospectively_validated",
        "registered_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "confirmatory_sample_starts": f"first B3 trading session of {CONFIRMATORY_FROM_YEAR}",
        "selection_method": "declared, not searched",
        "signal_family": FACTOR,
        "review_frequency": "annual",
        "maximum_names_per_sector": MAXIMUM_NAMES_PER_SECTOR,
        "global_sleeve": {
            "instrument": GLOBAL_TICKER,
            "share_of_equity_budget": GLOBAL_FRACTION,
            "status": "declared exposure, never selected; no CVM filing and no fundamental screen",
            "unhedged_currency_warning": (
                "About a third of this instrument's return over 2015-2025 came from BRL depreciation, "
                "not from the American market. It is an unhedged long dollar position and must be "
                "described as one."
            ),
        },
        "intrayear_overlay": {
            "config": {k: getattr(FIXED_OVERLAY, k) for k in
                       ("alert_drawdown", "severe_drawdown", "alert_volatility", "severe_volatility",
                        "recovery_days", "cost_bps", "volatility_window", "peak_window")},
            "applies_to": "domestic sleeve only",
            "why": ("The fund is held because it does not follow the Ibovespa. Cutting it on a domestic "
                    "stress signal sells the one asset the signal does not apply to. Measured "
                    "risk-matched, excluding it beat including it in all three profiles."),
        },
        "resolved_conflict": {
            "issue": "ladder v1 declared arrojado at 95% equity while benevente_profile_risk_v1 declared 75%",
            "resolution": "arrojado adopts 75%, which the measurement supports and which makes both "
                          "registrations agree without revoking either",
        },
        "trials_disclosure": (
            "Two combination variants were measured before this one was chosen. That choice is a "
            "selection over two candidates and is declared here rather than presented as the only "
            "option considered."
        ),
        "profiles": {
            profile: {
                "maximum_equity_weight": item["maximum_equity_weight"],
                "top_assets": item["top_assets"],
                "maximum_asset_weight": _issuer_cap(item["maximum_equity_weight"], item["top_assets"]),
                "domestic_budget_solved": round(domestic_protocol(profile, 2015, 2026).maximum_equity_weight, 6),
                "global_share_of_portfolio": round(item["maximum_equity_weight"] * GLOBAL_FRACTION, 6),
                "rationale": item["rationale"],
            }
            for profile, item in LADDER_V2.items()
        },
        "inputs": {name: file_sha256(path) for name, path in GLOBAL_INPUTS.items()},
        "code": {path.name: file_sha256(path) for path in [*CODE_INPUTS, ROOT / "profile_ladder_v2.py"]},
        "success_criterion": {
            "minimum_years": 3,
            "must_beat_cdi_after_tax": True,
            "must_beat_investable_market_etf": True,
            "profile_ordering_must_hold": "conservador <= equilibrado <= arrojado in realised risk and return",
            "falsification": (
                "A profile that fails to clear the CDI after tax over the full prospective window, or a "
                "ladder whose realised risk ordering inverts, refutes the policy."
            ),
        },
        "non_negotiable_gates": {
            "no_parameter_change_after_sample_start": True,
            "in_sample_window_is_exploratory": "2015-2025",
            "intrayear_tax_not_modelled": True,
        },
    }
    payload["registration_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def run(output: Path, start_year: int, end_year: int) -> pd.DataFrame:
    engine, panel = build_global_engine()
    rows = []
    for profile in LADDER_V2:
        blended, context = evaluate(profile, engine, panel, start_year, end_year)
        daily = context["daily"]
        rows.append({
            "perfil": profile,
            "acoes_alvo": round(context["realised_equity"], 4),
            "global_da_carteira": round(context["share"], 4),
            "posicoes": LADDER_V2[profile]["top_assets"],
            **_metrics(blended, daily.date, daily.cdi_daily_return),
        })
    frame = pd.DataFrame(rows)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "ladder_v2_summary.csv", index=False)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate, and optionally freeze, the v2 profile ladder.")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--register", action="store_true",
                        help="Freeze the policy. This is a human act and is never run automatically.")
    parser.add_argument("--approved-by", default=None,
                        help="Person accountable for freezing this policy. Defaults to the git identity.")
    parser.add_argument("--registration", default="data/benevente_profile_ladder_v2_registration.json")
    parser.add_argument("--output", default="artifacts/profile_ladder_v2")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    if args.run:
        frame = run(Path(args.output), args.start_year, args.end_year)
        print(frame.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    if args.register:
        payload = register(Path(args.registration), args.approved_by)
        print(f"registered {payload['policy']} sha256={payload['registration_sha256'][:16]}")
        print(f"aprovado por {payload['approved_by']} ({payload['approval_source']}) "
              f"em {payload['registered_at']}")
    if not (args.run or args.register):
        parser.print_help()


if __name__ == "__main__":
    main()
