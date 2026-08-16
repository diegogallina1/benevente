"""Pre-declared robust-MVO grid with a strict 2015–2020 / 2021–2025 split.

The aim is to improve the *estimation* of a long-only MVO, not to choose a
model after knowing its future. Each variant changes only covariance shrinkage,
risk aversion and a bounded momentum prior, all derived before the annual
decision. The winner is selected from 2015–2020 only.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd

from research_unrestricted_signal_grid import COST, LOOKBACK, market_sessions
from total_return_adapter import load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "enhanced_mvo_20260813"


def robust_mvo(history: pd.DataFrame, gamma: float, shrinkage: float, momentum_prior: float) -> pd.Series:
    returns = history.pct_change().dropna()
    assets = returns.columns
    if len(assets) == 1:
        return pd.Series(1.0, index=assets)
    historical_mean = returns.mean().to_numpy() * 252
    momentum = ((1 + returns.tail(252)).prod() - 1).rank(pct=True).to_numpy() - .5
    mean = historical_mean + momentum_prior * momentum
    sample = returns.cov().to_numpy() * 252
    diagonal = np.diag(np.diag(sample))
    covariance = (1 - shrinkage) * sample + shrinkage * diagonal + np.eye(len(assets)) * 1e-5
    weights = cp.Variable(len(assets))
    problem = cp.Problem(cp.Maximize(mean @ weights - gamma / 2 * cp.quad_form(weights, cp.psd_wrap(covariance))),
                         [cp.sum(weights) == 1, weights >= 0])
    problem.solve(solver=cp.CLARABEL)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or weights.value is None:
        raise RuntimeError(f"solver status {problem.status}")
    solution = np.maximum(weights.value, 0)
    return pd.Series(solution / solution.sum(), index=assets)


def evaluate(prices: pd.DataFrame, gamma: float, shrinkage: float, momentum_prior: float) -> pd.DataFrame:
    assets = prices.columns.drop("TITULO_CDI")
    previous = pd.Series(dtype=float)
    rows: list[dict] = []
    for year in range(2015, 2026):
        decision = prices.index[prices.index.year == year][0]
        next_days = prices.index[prices.index.year == year + 1]
        end = next_days[0] if not next_days.empty else prices.index[-1] + pd.Timedelta(days=1)
        history = market_sessions(prices.loc[prices.index < decision, assets])
        if len(history) < LOOKBACK + 1:
            continue
        history = history.tail(LOOKBACK + 1)
        eligible = history.columns[history.notna().all()].tolist()
        history = history.loc[:, eligible]
        weights = robust_mvo(history, gamma, shrinkage, momentum_prior)
        realised = prices.loc[(prices.index >= decision) & (prices.index < end), eligible].ffill()
        returns = realised.pct_change().dropna(how="all").fillna(0.0)
        gross = float((1 + returns @ weights).prod() - 1)
        turnover = float((weights - previous.reindex(weights.index, fill_value=0)).abs().sum())
        cdi = prices.loc[(prices.index >= decision) & (prices.index < end), "TITULO_CDI"]
        rows.append({"year": year, "net_return": gross - COST * turnover, "gross_return": gross, "turnover": turnover,
                     "cdi_return": float(cdi.iloc[-1] / cdi.iloc[0] - 1), "eligible_assets": len(eligible)})
        growth = (1 + returns).prod(); previous = weights * growth; previous /= previous.sum()
    return pd.DataFrame(rows)


def cagr(values: pd.Series) -> float:
    return float((1 + values).prod()) ** (1 / len(values)) - 1


def summary(frame: pd.DataFrame) -> dict[str, float | int]:
    wealth = (1 + frame.net_return).cumprod()
    baseline_cagr = cagr(frame.baseline_mvo_return)
    return {"years": len(frame), "cagr": cagr(frame.net_return), "cdi_cagr": cagr(frame.cdi_return),
            "excess_cdi": cagr(frame.net_return) - cagr(frame.cdi_return),
            "baseline_mvo_cagr": baseline_cagr,
            "excess_baseline_mvo": cagr(frame.net_return) - baseline_cagr,
            "cdi_hit_rate": float((frame.net_return > frame.cdi_return).mean()),
            "baseline_mvo_hit_rate": float((frame.net_return > frame.baseline_mvo_return).mean()),
            "worst_year": float(frame.net_return.min()), "drawdown": float((wealth / wealth.cummax() - 1).min()),
            "turnover": float(frame.turnover.mean())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw, _ = load_total_return_export(ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv", ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    prices = raw.set_index("date").sort_index()
    baseline = pd.read_csv(ROOT / "data/shadow_retro_momentum_2015_2025/annual_ledger.csv")
    baseline = baseline.loc[:, ["decision_year", "mvo_net_return"]].rename(columns={"decision_year": "year", "mvo_net_return": "baseline_mvo_return"})
    rows: list[dict] = []
    for gamma, shrinkage, prior in itertools.product((2.5, 5.0, 10.0, 20.0), (0.0, .25, .50, .75), (0.0, .10, .25)):
        name = f"mvo_g{gamma}_s{shrinkage}_p{prior}"
        annual = evaluate(prices, gamma, shrinkage, prior).merge(baseline, on="year", how="left", validate="one_to_one")
        if annual.baseline_mvo_return.isna().any():
            raise RuntimeError("MVO-base ausente em um ou mais anos")
        annual.to_csv(OUT / f"{name}_annual.csv", index=False)
        for split, data in (("train", annual[annual.year <= 2020]), ("holdout", annual[annual.year >= 2021])):
            rows.append({"name": name, "gamma": gamma, "shrinkage": shrinkage, "momentum_prior": prior, "split": split, **summary(data)})
    report = pd.DataFrame(rows)
    train = report[report.split.eq("train")].set_index("name")
    holdout = report[report.split.eq("holdout")].set_index("name")
    combined = train.add_prefix("train_").join(holdout.add_prefix("holdout_"))
    combined["train_score"] = (combined.train_excess_cdi + combined.train_excess_baseline_mvo
                               - .20 * combined.train_drawdown.abs() - .05 * combined.train_turnover)
    combined = combined.sort_values("train_score", ascending=False)
    combined.to_csv(OUT / "combined.csv")
    winner = combined.iloc[0]
    result = {"candidates": len(combined), "selection_period": "2015-2020", "holdout_period": "2021-2025",
              "winner": winner.to_dict(),
              "passes_holdout_cdi": bool(winner.holdout_excess_cdi > 0),
              "passes_holdout_baseline_mvo": bool(winner.holdout_excess_baseline_mvo > 0),
              "passes_holdout_both": bool(winner.holdout_excess_cdi > 0 and winner.holdout_excess_baseline_mvo > 0)}
    (OUT / "conclusion.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    main()
