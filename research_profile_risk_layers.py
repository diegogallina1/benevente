"""Close the gap between a profile's worst calendar year and its drawdown.

The frozen ladder revises once a year, so the book cannot respond to anything
that happens inside a year. Measured over 2013-2025 that produced a conservador
whose worst *calendar year* was +0.92% and whose worst *drawdown* was -19.23%.
The second number is the one the investor experiences, and no annual protocol
can improve it on its own.

Two separate layers could. This module measures both against the frozen ladder:

* the annual volatility target, which sizes the sleeve at the January decision.
  It is the layer that compressed the published profiles, holding 54%, 65% and
  78% of their declared caps on average, and the exposure floor exists to stop
  that. It cannot reduce a drawdown that begins after January;
* the intra-year overlay, which observes Ibovespa stress at the previous close
  and moves part of the sleeve to CDI without ever changing a holding.

Neither layer is new and neither is prospective evidence: both were designed
after the crises visible in this sample.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

import pandas as pd

from annual_walk_forward import BrazilianTaxModel, apply_annual_taxes
from portfolio_risk import risk_profile_spec
from profile_intrayear_risk import annual_returns, apply_profile_overlay, metrics
from benevente2_event_risk import reconcile_daily_returns
from profile_ladder import LADDER, build_engine, protocol_for

# Share of the declared cap the volatility target may not cut below.
EXPOSURE_FLOOR = .60


def _overlay(profile: str, source: Path) -> tuple[pd.DataFrame, dict]:
    """Apply the fixed intra-year overlay to an already-computed ladder run."""
    curve = pd.read_csv(source / "daily_curve.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    annual = pd.read_csv(source / "annual_results.csv").set_index("decision_year")
    curve["strategy_daily_return"] = reconcile_daily_returns(curve.strategy, curve.decision_year, annual.net_return)
    curve["cdi_daily_return"] = reconcile_daily_returns(curve.cdi, curve.decision_year, annual.cdi_net_return)
    target_equity = curve.decision_year.map(annual.target_equity_weight)
    if target_equity.isna().any():
        raise ValueError("Every daily row must map to an annual target equity weight")
    result = apply_profile_overlay(curve, target_equity, profile)
    return result, {
        "base": metrics(result.strategy_daily_return, result.date),
        "protegido": metrics(result.protected_return, result.date),
        "CDI": metrics(result.cdi_daily_return, result.date),
    }


def _annual_layer(engine, profile: str, start_year: int, end_year: int,
                  floor: float | None) -> tuple[pd.DataFrame, dict] | None:
    """Run the ladder with the January volatility target, optionally floored.

    The registered risk spec carries its own equity cap. Where that cap
    disagrees with the ladder's declared budget the two policies cannot be
    combined without deciding which one governs, so this returns ``None``
    rather than silently letting one override the other.
    """
    ladder_budget = LADDER[profile]["maximum_equity_weight"]
    spec_budget = risk_profile_spec(profile).maximum_equity_weight
    if abs(ladder_budget - spec_budget) > 1e-9:
        return None
    protocol = replace(protocol_for(profile, start_year, end_year),
                       risk_profile=profile, apply_profile_risk_layer=True,
                       exposure_floor_fraction=floor)
    results, _, _ = engine.run(protocol)
    results = apply_annual_taxes(results, BrazilianTaxModel())
    exposure = results.target_equity_weight
    return results, {
        "exposicao_media": float(exposure.mean()),
        "exposicao_minima": float(exposure.min()),
        "share_do_teto": float(exposure.mean() / ladder_budget),
    }


def run(output: Path, start_year: int, end_year: int) -> pd.DataFrame:
    engine = build_engine()
    ladder_root = Path("artifacts/profile_ladder_v1")
    rows: list[dict] = []
    output.mkdir(parents=True, exist_ok=True)

    for profile in LADDER:
        source = ladder_root / profile
        if not (source / "daily_curve.csv").exists():
            raise FileNotFoundError(f"Run profile_ladder.py --run first; missing {source}")
        result, summary = _overlay(profile, source)
        target = output / profile
        target.mkdir(parents=True, exist_ok=True)
        result.to_csv(target / "daily_overlay.csv", index=False)
        annual_returns(result).to_csv(target / "annual_overlay.csv", index=False)
        for label, key in (("escada (congelada)", "base"), ("escada + overlay intranual", "protegido")):
            rows.append({"perfil": profile, "regime": label,
                         "cagr": summary[key]["cagr"], "vol": summary[key]["annual_volatility"],
                         "drawdown": summary[key]["max_drawdown"],
                         "giro_overlay": float(result.overlay_turnover.sum()) if key == "protegido" else 0.0,
                         "dias_em_estresse": int(result.risk_state.gt(0).sum()) if key == "protegido" else 0})

        for floor, label in ((None, "escada + meta de vol anual"),
                             (EXPOSURE_FLOOR, f"escada + meta de vol com piso {EXPOSURE_FLOOR:.0%}")):
            outcome = _annual_layer(engine, profile, start_year, end_year, floor)
            if outcome is None:
                rows.append({"perfil": profile, "regime": label, "cagr": float("nan"), "vol": float("nan"),
                             "drawdown": float("nan"), "giro_overlay": float("nan"), "dias_em_estresse": -1})
                continue
            results, exposure = outcome
            net = results.net_return
            wealth = (1 + net).cumprod()
            daily = engine.daily_curve
            curve = daily[daily.decision_year.isin(results.decision_year)].strategy
            rows.append({"perfil": profile, "regime": label,
                         "cagr": float(wealth.iloc[-1] ** (1 / len(net)) - 1),
                         "vol": float(net.std(ddof=1)),
                         "drawdown": float((curve / curve.cummax() - 1).min()),
                         "exposicao_media": exposure["exposicao_media"],
                         "share_do_teto": exposure["share_do_teto"]})

    frame = pd.DataFrame(rows)
    frame.to_csv(output / "risk_layers_by_profile.csv", index=False)
    (output / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "exposure_floor": EXPOSURE_FLOOR,
        "limitations": [
            "Both layers were designed after the crises present in the sample.",
            "Intra-year tax on the overlay's realised gains is not modelled.",
            "A profile whose ladder budget disagrees with its registered risk spec is reported as not combinable.",
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the risk layers against the frozen ladder.")
    parser.add_argument("--output", default="artifacts/profile_risk_layers_v1")
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    frame = run(Path(args.output), args.start_year, args.end_year)
    print(frame.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
