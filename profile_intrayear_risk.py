"""Apply a fixed, lagged intrayear risk overlay to each investor profile.

Asset selection remains annual.  The overlay may only move a fraction of the
already selected equity sleeve to CDI after stress is observable in the
Ibovespa at the previous close.  It never replaces a stock inside the year.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import math

import numpy as np
import pandas as pd

from benevente2_event_risk import RiskOverlayConfig, observable_stress, reconcile_daily_returns, state_with_hysteresis
from portfolio_risk import risk_profile_spec


# Fixed before this experiment.  There is no parameter grid and no choice made
# from the resulting return.  The rule still remains retrospective because it
# was designed after the historical crises in the sample.
FIXED_OVERLAY = RiskOverlayConfig(
    alert_drawdown=.10,
    severe_drawdown=.20,
    alert_volatility=.30,
    severe_volatility=.50,
    recovery_days=10,
    cost_bps=10.0,
    volatility_window=20,
    peak_window=126,
)


def apply_profile_overlay(
    frame: pd.DataFrame,
    target_equity: pd.Series,
    profile: str,
    config: RiskOverlayConfig = FIXED_OVERLAY,
) -> pd.DataFrame:
    spec = risk_profile_spec(profile)
    stress = observable_stress(frame["IBOVESPA"], config)
    state = state_with_hysteresis(stress.tradable_stress, config.recovery_days)
    multiplier = pd.Series(1.0, index=frame.index)
    multiplier.loc[state.eq(1)] = spec.alert_multiplier
    multiplier.loc[state.eq(2)] = spec.severe_multiplier
    desired = target_equity.astype(float) * multiplier

    strategy_return = frame["strategy_daily_return"].astype(float)
    cdi_return = frame["cdi_daily_return"].astype(float)
    turnover = desired.diff().abs().fillna((target_equity - desired).abs())
    overlay_cost = turnover * config.cost_bps / 10_000
    protected_return = cdi_return + multiplier * (strategy_return - cdi_return) - overlay_cost

    result = frame.copy().join(stress)
    result["risk_state"] = state
    result["risk_multiplier"] = multiplier
    result["base_equity_weight"] = target_equity
    result["protected_equity_weight"] = desired
    result["overlay_turnover"] = turnover
    result["overlay_cost_rate"] = overlay_cost
    result["protected_return"] = protected_return
    result["base_rebased"] = (1 + strategy_return).cumprod()
    result["protected_rebased"] = (1 + protected_return).cumprod()
    result["cdi_rebased"] = (1 + cdi_return).cumprod()
    return result


def metrics(returns: pd.Series, dates: pd.Series) -> dict:
    clean = returns.fillna(0.0)
    wealth = (1 + clean).cumprod()
    years = max(int(dates.dt.year.nunique()), 1)
    return {
        "years": years,
        "cumulative_return": float(wealth.iloc[-1] - 1),
        "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "annual_volatility": float(clean.std(ddof=1) * math.sqrt(252)),
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
    }


def annual_returns(result: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year, group in result.groupby(result.date.dt.year):
        rows.append({
            "decision_year": int(year),
            "base_return": float((1 + group.strategy_daily_return).prod() - 1),
            "protected_return": float((1 + group.protected_return).prod() - 1),
            "cdi_return": float((1 + group.cdi_daily_return).prod() - 1),
            "days_alert": int(group.risk_state.eq(1).sum()),
            "days_severe": int(group.risk_state.eq(2).sum()),
            "overlay_turnover": float(group.overlay_turnover.sum()),
            "overlay_cost_rate": float(group.overlay_cost_rate.sum()),
            "minimum_equity_weight": float(group.protected_equity_weight.min()),
        })
    return pd.DataFrame(rows)


def run_profile(profile: str, source: Path, output: Path) -> dict:
    curve = pd.read_csv(source / "daily_curve.csv", parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    annual = pd.read_csv(source / "annual_results.csv").set_index("decision_year")
    curve["strategy_daily_return"] = reconcile_daily_returns(curve.strategy, curve.decision_year, annual.net_return)
    curve["cdi_daily_return"] = reconcile_daily_returns(curve.cdi, curve.decision_year, annual.cdi_net_return)
    target_equity = curve.decision_year.map(annual.target_equity_weight)
    if target_equity.isna().any():
        raise ValueError("Every daily row must map to an annual target equity weight")
    result = apply_profile_overlay(curve, target_equity, profile)
    annual_result = annual_returns(result)
    holdout = result[result.date.dt.year >= 2019]
    summary = {
        "profile": profile,
        "status": "retrospective_fixed_overlay_not_prospective_validation",
        "configuration": {
            "alert_drawdown": FIXED_OVERLAY.alert_drawdown,
            "severe_drawdown": FIXED_OVERLAY.severe_drawdown,
            "alert_volatility": FIXED_OVERLAY.alert_volatility,
            "severe_volatility": FIXED_OVERLAY.severe_volatility,
            "recovery_days": FIXED_OVERLAY.recovery_days,
            "cost_bps": FIXED_OVERLAY.cost_bps,
            "profile_alert_multiplier": risk_profile_spec(profile).alert_multiplier,
            "profile_severe_multiplier": risk_profile_spec(profile).severe_multiplier,
            "signal_lag_sessions": 1,
        },
        "full_period": {
            "base": metrics(result.strategy_daily_return, result.date),
            "protected": metrics(result.protected_return, result.date),
            "CDI": metrics(result.cdi_daily_return, result.date),
        },
        "holdout_2019_2025": {
            "base": metrics(holdout.strategy_daily_return, holdout.date),
            "protected": metrics(holdout.protected_return, holdout.date),
            "CDI": metrics(holdout.cdi_daily_return, holdout.date),
        },
        "overlay_turnover": float(result.overlay_turnover.sum()),
        "overlay_cost_rate_sum": float(result.overlay_cost_rate.sum()),
        "limitations": [
            "The overlay was designed after crises visible in the sample.",
            "Intrayear tax consequences are not yet included.",
            "The signal reacts to price stress; it does not forecast the cause of the crisis.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    result.to_csv(output / "daily_overlay.csv", index=False)
    annual_result.to_csv(output / "annual_overlay.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed profile-specific intrayear risk overlay.")
    parser.add_argument("--profiles-root", default="artifacts/risk_profiles_v1")
    args = parser.parse_args()
    root = Path(args.profiles_root)
    payload = {}
    for profile in ("conservador", "equilibrado", "arrojado"):
        payload[profile] = run_profile(profile, root / profile, root / f"{profile}_intrayear")
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
