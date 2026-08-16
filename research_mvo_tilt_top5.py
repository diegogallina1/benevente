"""Train/holdout test for a five-stock, turnover-aware MVO active tilt.

The asset set is selected by the archived triple-factor screen at each January
decision.  Both candidates therefore use the exact same five dated assets,
the same CDI sleeve, constraints and costs.  The reference is a neutral MVO
rebuilt with the *same* exposure and risk-aversion parameters in each trial;
only the expected-return tilt and its turnover penalty differ. Parameters are
selected on 2015--2020 only.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd

from config import SystemConfig
from optimizer import MeanVarianceOptimizer

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "mvo_tilt_top5_20260813"
COST = 0.0015


def cagr(values: pd.Series) -> float:
    return float((1 + values).prod() ** (1 / len(values)) - 1)


def run(prices: pd.DataFrame, holdings: pd.DataFrame, results: pd.DataFrame,
        influence: float, penalty: float, equity_cap: float, gamma: float) -> pd.DataFrame:
    previous_active = pd.Series(dtype=float)
    previous_neutral = pd.Series(dtype=float)
    rows: list[dict] = []
    for item in results.itertuples(index=False):
        year = int(item.decision_year)
        decision, end = pd.Timestamp(item.decision_date), pd.Timestamp(item.holding_end_exclusive)
        names = holdings[(holdings.decision_year == year) & (holdings.ticker != "TITULO_CDI")].copy()
        names["ticker"] = names.ticker.str.removesuffix(".SA")
        assets = names.ticker.tolist() + ["TITULO_CDI"]
        history = prices.loc[prices.index < decision, assets].tail(253).pct_change().dropna()
        realised = prices.loc[(prices.index >= decision) & (prices.index < end), assets].pct_change().dropna()
        if len(names) != 5 or history.empty or realised.empty:
            continue
        score = names.set_index("ticker").value_quality_score.fillna(0).to_dict()
        score["TITULO_CDI"] = 0.0
        # At five names, equal caps would make 100% equity impossible. A
        # 20% ceiling preserves the minimum diversification rule.
        config = SystemConfig(max_asset_weight=.20, risk_aversion_gamma=gamma)
        optimizer = MeanVarianceOptimizer(config)
        weights = optimizer.optimize(
            history, score, equity_cap=equity_cap, signal_influence=influence,
            eligible_assets=set(names.ticker), previous_weights=previous_active,
            turnover_penalty=penalty, minimum_selected_weight=.02,
        )
        # Fair benchmark: identical investable names, equity cap, weight floor,
        # risk aversion and trading-cost convention; no predictive signal.
        neutral = optimizer.optimize(
            history, {asset: 0.0 for asset in assets}, equity_cap=equity_cap,
            signal_influence=0.0, eligible_assets=set(names.ticker),
            previous_weights=previous_neutral, turnover_penalty=0.0,
            minimum_selected_weight=.02,
        )
        growth = (1 + realised).prod()
        gross = float((1 + realised @ weights).prod() - 1)
        turnover = float((weights - previous_active.reindex(weights.index, fill_value=0)).abs().sum())
        neutral_gross = float((1 + realised @ neutral).prod() - 1)
        neutral_turnover = float((neutral - previous_neutral.reindex(neutral.index, fill_value=0)).abs().sum())
        rows.append({"year": year, "net_return": gross - COST * turnover,
                     "turnover": turnover, "cdi_return": float(item.cdi_net_return),
                     "reference_mvo_return": neutral_gross - COST * neutral_turnover})
        previous_active = weights * growth
        previous_active /= previous_active.sum()
        previous_neutral = neutral * growth
        previous_neutral /= previous_neutral.sum()
    return pd.DataFrame(rows)


def metrics(frame: pd.DataFrame) -> dict[str, float]:
    wealth = (1 + frame.net_return).cumprod()
    return {
        "cagr": cagr(frame.net_return), "cdi_cagr": cagr(frame.cdi_return),
        "reference_mvo_cagr": cagr(frame.reference_mvo_return),
        "excess_cdi": cagr(frame.net_return) - cagr(frame.cdi_return),
        "excess_reference_mvo": cagr(frame.net_return) - cagr(frame.reference_mvo_return),
        "hit_cdi": float((frame.net_return > frame.cdi_return).mean()),
        "hit_reference_mvo": float((frame.net_return > frame.reference_mvo_return).mean()),
        "drawdown": float((wealth / wealth.cummax() - 1).min()),
        "turnover": float(frame.turnover.mean()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices = pd.read_csv(ROOT / "data" / "prices_yahoo_adjusted_total_return_2013_2025.csv", parse_dates=["date"]).set_index("date").sort_index()
    root = ROOT / "artifacts" / "benevente_equilibrado_top5"
    holdings = pd.read_csv(root / "annual_holdings.csv")
    results = pd.read_csv(root / "annual_results.csv")
    report: list[dict] = []
    for influence, penalty, equity_cap, gamma in itertools.product(
        (0.0, .10, .25, .40, .60), (0.0, .01, .03, .06), (.55, .75, 1.0), (1.0, 2.5, 5.0)
    ):
        annual = run(prices, holdings, results, influence, penalty, equity_cap, gamma)
        name = f"tilt_{influence}_turnover_{penalty}_equity_{equity_cap}_gamma_{gamma}"
        annual.to_csv(OUT / f"{name}.csv", index=False)
        for split, data in (("train", annual[annual.year <= 2020]), ("holdout", annual[annual.year >= 2021])):
            report.append({"name": name, "influence": influence, "penalty": penalty, "equity_cap": equity_cap, "gamma": gamma, "split": split, **metrics(data)})
    grid = pd.DataFrame(report)
    train = grid[grid.split.eq("train")].set_index("name")
    holdout = grid[grid.split.eq("holdout")].set_index("name")
    combined = train.add_prefix("train_").join(holdout.add_prefix("holdout_"))
    combined["train_score"] = combined.train_excess_cdi + combined.train_excess_reference_mvo - .1 * combined.train_turnover
    combined.sort_values("train_score", ascending=False, inplace=True)
    combined.to_csv(OUT / "summary.csv")
    best = combined.iloc[0].to_dict()
    conclusion = {"variants": len(combined), "selection": "2015-2020 only", "holdout": "2021-2025", "winner": best,
                  "passes_holdout_both": bool(best["holdout_excess_cdi"] > 0 and best["holdout_excess_reference_mvo"] > 0)}
    (OUT / "conclusion.json").write_text(json.dumps(conclusion, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(json.dumps(conclusion, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    main()
