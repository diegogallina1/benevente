"""Systematic unrestricted factor grid with an annual no-look-ahead protocol.

No fundamental, issuer, liquidity, sector, position, or asset-count screen is
applied. At each January decision, every instrument with a complete trailing
price history receives a strictly positive allocation. The grid enumerates
momentum/reversal lookbacks, volatility scaling and rank concentration. It is
explicitly an exploratory multiple-testing exercise: holdout results are
reported but must not be used to retroactively select a live rule.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from total_return_adapter import load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "unrestricted_signal_grid_20260813"
LOOKBACK = 252
COST = 0.0015


def market_sessions(prior: pd.DataFrame) -> pd.DataFrame:
    coverage = prior.notna().sum(axis=1)
    return prior.loc[coverage >= max(1, int(coverage.max() * .80))]


def make_weights(history: pd.DataFrame, kind: str, lookback: int, exponent: float, volatility_power: float) -> pd.Series:
    returns = history.pct_change().dropna()
    recent = returns.tail(lookback)
    if kind == "equal":
        signal = pd.Series(1.0, index=history.columns)
    else:
        raw = (1 + recent).prod() - 1
        if kind == "reversal":
            raw = -raw
        elif kind != "momentum":
            raise ValueError(kind)
        signal = raw.rank(method="first", pct=True)
    volatility = returns.tail(lookback).std(ddof=1).replace(0, np.nan)
    weights = signal.pow(exponent) / volatility.pow(volatility_power)
    # Every eligible name has strictly positive weight, including the lowest
    # rank. No implicit top-N selection is allowed in this diagnostic.
    weights = weights.replace([np.inf, -np.inf], np.nan).fillna(1e-12).clip(lower=1e-12)
    return weights / weights.sum()


def evaluate(prices: pd.DataFrame, name: str, kind: str, lookback: int, exponent: float, volatility_power: float) -> pd.DataFrame:
    assets = prices.columns.drop("TITULO_CDI")
    previous = pd.Series(dtype=float)
    rows: list[dict[str, object]] = []
    for year in range(2015, 2026):
        decision_days = prices.index[prices.index.year == year]
        if decision_days.empty:
            continue
        decision = decision_days[0]
        next_days = prices.index[prices.index.year == year + 1]
        end = next_days[0] if not next_days.empty else prices.index[-1] + pd.Timedelta(days=1)
        prior = market_sessions(prices.loc[prices.index < decision, assets])
        if len(prior) < LOOKBACK + 1:
            continue
        history = prior.tail(LOOKBACK + 1)
        eligible = history.columns[history.notna().all()].tolist()
        weights = make_weights(history.loc[:, eligible], kind, lookback, exponent, volatility_power)
        realised = prices.loc[(prices.index >= decision) & (prices.index < end), eligible].ffill()
        returns = realised.pct_change().dropna(how="all").fillna(0.0)
        gross = float((1 + returns @ weights).prod() - 1)
        old = previous.reindex(weights.index, fill_value=0.0)
        turnover = float((weights - old).abs().sum())
        cdi = prices.loc[(prices.index >= decision) & (prices.index < end), "TITULO_CDI"]
        rows.append({"name": name, "year": year, "eligible_assets": len(eligible), "gross_return": gross,
                     "turnover": turnover, "net_return": gross - COST * turnover,
                     "cdi_return": float(cdi.iloc[-1] / cdi.iloc[0] - 1)})
        growth = (1 + returns).prod()
        previous = weights * growth
        previous = previous / previous.sum()
    return pd.DataFrame(rows)


def metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    def cagr(column: str) -> float:
        return float((1 + frame[column]).prod()) ** (1 / len(frame)) - 1
    wealth = (1 + frame.net_return).cumprod()
    return {"years": len(frame), "cagr": cagr("net_return"), "cdi_cagr": cagr("cdi_return"),
            "excess_cdi": cagr("net_return") - cagr("cdi_return"), "worst_year": float(frame.net_return.min()),
            "max_drawdown": float((wealth / wealth.cummax() - 1).min()), "average_turnover": float(frame.turnover.mean())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loaded, _ = load_total_return_export(ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv", ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    prices = loaded.set_index("date").sort_index()
    candidates = [("equal", 21, 1.0, 0.0)]
    candidates.extend(itertools.product(("momentum", "reversal"), (21, 63, 126, 252), (.5, 1.0, 2.0), (0.0, .5, 1.0)))
    report: list[dict[str, object]] = []
    for index, (kind, window, exponent, vol_power) in enumerate(candidates):
        name = f"{kind}_w{window}_e{str(exponent).replace('.', '')}_v{str(vol_power).replace('.', '')}"
        annual = evaluate(prices, name, kind, window, exponent, vol_power)
        annual.to_csv(OUT / f"{name}_annual.csv", index=False)
        for split, subset in (("train", annual[annual.year <= 2020]), ("holdout", annual[annual.year >= 2021])):
            report.append({"name": name, "kind": kind, "lookback": window, "exponent": exponent,
                           "volatility_power": vol_power, "split": split, **metrics(subset)})
    summary = pd.DataFrame(report)
    train = summary[summary.split.eq("train")].set_index("name")
    holdout = summary[summary.split.eq("holdout")].set_index("name")
    combined = train.add_prefix("train_").join(holdout.add_prefix("holdout_"))
    # Pre-declared train objective. It only determines a candidate to be
    # evaluated once in holdout; it is not a live allocation rule.
    combined["train_score"] = combined.train_excess_cdi - .20 * combined.train_max_drawdown.abs() - .05 * combined.train_average_turnover
    combined = combined.sort_values("train_score", ascending=False)
    combined.to_csv(OUT / "combined.csv")
    winner = combined.iloc[0]
    conclusion = {"candidate_count": len(candidates), "selection": "highest train score only",
                  "winner": {key: float(value) if isinstance(value, (np.floating, float)) else value for key, value in winner.to_dict().items()},
                  "winner_passes_holdout_cdi": bool(winner.holdout_excess_cdi > 0),
                  "holdout_positive_count": int((combined.holdout_excess_cdi > 0).sum())}
    (OUT / "conclusion.json").write_text(json.dumps(conclusion, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(conclusion, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
