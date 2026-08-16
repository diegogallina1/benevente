"""Nested yearly selection across unrestricted rules, without future returns.

All component strategies are the 73 annual portfolios exported by
``research_unrestricted_signal_grid.py``.  For decision year t, a policy may
only inspect component returns ending in t-1, choose one component, and then
receive that component's recorded return in t.  This is a genuine meta-rule,
not selection of the best full-period backtest.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parent
INPUT = ROOT / "artifacts" / "unrestricted_signal_grid_20260813"
OUT = ROOT / "artifacts" / "unrestricted_regime_selection_20260813"


def cagr(values: pd.Series) -> float:
    return float((1 + values).prod()) ** (1 / len(values)) - 1


def rank_score(history: pd.DataFrame, objective: str, window: int | None) -> pd.Series:
    sample = history if window is None else history.tail(window)
    grouped = sample.groupby("name")
    if objective == "return":
        return grouped.net_return.apply(cagr)
    excess = sample.net_return - sample.cdi_return
    if objective == "excess_return":
        return grouped.apply(lambda x: cagr(x.net_return) - cagr(x.cdi_return), include_groups=False)
    if objective == "hit_rate":
        return grouped.apply(lambda x: float((x.net_return > x.cdi_return).mean()), include_groups=False)
    if objective == "information_ratio":
        return grouped.apply(lambda x: float((x.net_return - x.cdi_return).mean() /
                                               (x.net_return - x.cdi_return).std(ddof=1))
                                           if len(x) > 1 and (x.net_return - x.cdi_return).std(ddof=1) > 0 else -np.inf,
                             include_groups=False)
    raise ValueError(objective)


def evaluate(annual: pd.DataFrame, objective: str, window: int | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    decisions: list[dict[str, object]] = []
    for year in range(2018, 2026):
        past = annual[annual.year < year]
        scores = rank_score(past, objective, window).sort_values(ascending=False)
        selected = str(scores.index[0])
        realised = annual[(annual.name == selected) & (annual.year == year)].iloc[0]
        decisions.append({"decision_year": year, "selected_rule": selected, "objective": objective,
                          "window": "expanding" if window is None else window,
                          "score_at_decision": float(scores.iloc[0]),
                          "net_return": float(realised.net_return), "cdi_return": float(realised.cdi_return),
                          "turnover": float(realised.turnover), "eligible_assets": int(realised.eligible_assets)})
    result = pd.DataFrame(decisions)
    return result, result[["decision_year", "selected_rule", "score_at_decision"]]


def summary(frame: pd.DataFrame) -> dict[str, float | int]:
    wealth = (1 + frame.net_return).cumprod()
    return {"years": len(frame), "cagr": cagr(frame.net_return), "cdi_cagr": cagr(frame.cdi_return),
            "excess_cdi": cagr(frame.net_return) - cagr(frame.cdi_return),
            "cdi_hit_rate": float((frame.net_return > frame.cdi_return).mean()),
            "worst_year": float(frame.net_return.min()),
            "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
            "average_turnover": float(frame.turnover.mean()),
            "unique_rules_used": int(frame.selected_rule.nunique())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    annual_files = list(INPUT.glob("*_annual.csv"))
    annual = pd.concat([pd.read_csv(path) for path in annual_files], ignore_index=True)
    annual = annual.loc[annual.name.ne("equal_w21_e10_v00") | annual.index.notna()].copy()
    rows: list[dict[str, object]] = []
    policies = [(objective, window) for objective in ("return", "excess_return", "hit_rate", "information_ratio")
                for window in (None, 2, 3, 5)]
    for objective, window in policies:
        result, _ = evaluate(annual, objective, window)
        label = f"{objective}_{'expanding' if window is None else f'{window}y'}"
        result.to_csv(OUT / f"{label}_annual.csv", index=False)
        rows.append({"policy": label, "objective": objective, "window": "expanding" if window is None else window,
                     **summary(result)})
    report = pd.DataFrame(rows).sort_values("excess_cdi", ascending=False)
    report.to_csv(OUT / "summary.csv", index=False)
    # Last three years are a distinct recent diagnostic, not used to select policy.
    recent = []
    for policy in report.policy:
        results = pd.read_csv(OUT / f"{policy}_annual.csv")
        recent.append({"policy": policy, **{f"recent_{k}": v for k, v in summary(results[results.decision_year >= 2023]).items()}})
    result = report.merge(pd.DataFrame(recent), on="policy")
    result.to_csv(OUT / "summary_with_recent.csv", index=False)
    (OUT / "methodology.json").write_text(json.dumps({
        "component_rules": int(annual.name.nunique()), "first_decision": 2018,
        "rule": "At January t, select from prior realised annual observations only; no current or later-year return is read.",
        "warning": "Selecting a meta-policy after observing this report would itself require independent validation.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(result.to_string(index=False))


if __name__ == "__main__":
    main()
