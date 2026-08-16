"""Re-read the unrestricted signal grid with the trial count made explicit.

The grid ran 73 candidates, selected one on a training score, and then reported
the holdout. The rule that was published on the site is not the rule that won
that training score: it is the rule that won the holdout. This script states
that in numbers, and applies the deflated Sharpe ratio and the probability of
backtest overfitting to the full trial matrix.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from multiple_testing import deflated_sharpe, probability_of_backtest_overfitting


def load_trial_returns(grid_dir: Path) -> pd.DataFrame:
    """One column per candidate, one row per decision year."""
    series: dict[str, pd.Series] = {}
    for path in sorted(grid_dir.glob("*_annual.csv")):
        frame = pd.read_csv(path)
        if {"year", "net_return"} - set(frame.columns):
            continue
        series[path.stem.removesuffix("_annual")] = frame.set_index("year").net_return
    if not series:
        raise ValueError(f"No candidate annual files found in {grid_dir}")
    return pd.DataFrame(series).sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply multiple-testing corrections to the signal grid.")
    parser.add_argument("--grid-dir", default="artifacts/unrestricted_signal_grid_20260813")
    parser.add_argument("--published-candidate", default="momentum_w252_e20_v10")
    parser.add_argument("--output", default="artifacts/inference_audit/signal_grid_inference.json")
    parser.add_argument("--subsets", type=int, default=4)
    args = parser.parse_args()

    grid = Path(args.grid_dir)
    trials = load_trial_returns(grid)
    combined = pd.read_csv(grid / "combined.csv")
    ranked_train = combined.sort_values("train_score", ascending=False).reset_index(drop=True)
    ranked_holdout = combined.sort_values("holdout_excess_cdi", ascending=False).reset_index(drop=True)
    published = args.published_candidate

    selection = {
        "candidates": int(len(combined)),
        "published_candidate": published,
        "rank_by_declared_training_score": int(ranked_train.index[ranked_train.name.eq(published)][0]) + 1,
        "rank_by_holdout_excess_over_cdi": int(ranked_holdout.index[ranked_holdout.name.eq(published)][0]) + 1,
        "declared_training_winner": str(ranked_train.iloc[0]["name"]),
        "declared_training_winner_holdout_excess": float(ranked_train.iloc[0]["holdout_excess_cdi"]),
        "candidates_with_positive_holdout_excess": int((combined.holdout_excess_cdi > 0).sum()),
        "verdict": ("The published candidate was not selected by the declared training criterion. Its rank improves "
                    "from the training set to the holdout, which is only possible if the holdout was consulted. The "
                    "holdout is therefore consumed and its excess return is an in-sample statistic."),
    }

    sharpes = (trials.mean() / trials.std(ddof=1).replace(0, np.nan)).dropna()
    published_returns = trials[published].dropna()
    dsr = deflated_sharpe(published_returns, sharpes.to_numpy())
    pbo = probability_of_backtest_overfitting(trials, subsets=args.subsets)
    pbo_summary = {key: value for key, value in pbo.items() if key != "detail"}

    payload = {
        "selection": selection,
        "deflated_sharpe": dsr.as_dict(),
        "backtest_overfitting": pbo_summary,
        "reading": (
            "A deflated Sharpe probability below 0.95 means the candidate's Sharpe ratio is not distinguishable from "
            "the best of {trials} unskilled trials on {years} annual observations. An overfitting probability above "
            "0.5 means the in-sample winner more often than not lands in the weaker half out of sample."
        ).format(trials=len(sharpes), years=len(published_returns)),
        "power_caveat": (
            "Only {splits} combinatorial splits fit in {years} annual observations, so the overfitting probability "
            "is coarse: its resolution is one part in {splits}. It cannot exonerate the selection, and the deflated "
            "Sharpe result does not depend on it."
        ).format(splits=pbo_summary["splits_evaluated"], years=len(published_returns)),
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(pbo["detail"]).to_csv(output.with_name("cscv_splits.csv"), index=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
