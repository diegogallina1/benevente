"""Correct a backtest Sharpe ratio for the number of trials that produced it.

A grid that evaluates dozens of rules and reports the best one is not reporting
a discovery, it is reporting an order statistic.  The published candidate in
this project ranked 57th of 73 on its own pre-declared training criterion and
1st on the holdout, which is the signature of a rule chosen after the answer was
visible.  Nothing downstream of that choice can be read as out-of-sample.

Two standard corrections are implemented:

Deflated Sharpe ratio
    Bailey and Lopez de Prado (2014).  The observed Sharpe is compared against
    the Sharpe the *best of N independent trials* would reach under a null of no
    skill, and the comparison is adjusted for the non-normality and the short
    length of the return sample.

Probability of backtest overfitting
    Bailey, Borwein, Lopez de Prado and Zhu (2015), combinatorially symmetric
    cross-validation.  The trial matrix is split into subsets; for every way of
    dividing them into an in-sample and an out-of-sample half, the rule that won
    in sample is ranked out of sample.  The probability that the winner lands in
    the bottom half is the overfitting probability.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import combinations
from math import comb, e, log, sqrt

import numpy as np
import pandas as pd
from scipy import stats


EULER_MASCHERONI = 0.5772156649015329


@dataclass(frozen=True)
class DeflatedSharpe:
    observed_sharpe: float
    expected_maximum_sharpe_under_null: float
    trials: int
    observations: int
    skewness: float
    kurtosis: float
    deflated_sharpe_probability: float
    significant_at_95: bool

    def as_dict(self) -> dict:
        return asdict(self)


def expected_maximum_sharpe(trial_sharpes: np.ndarray) -> float:
    """Sharpe the best of N unskilled trials is expected to reach.

    The dispersion of the trial Sharpes carries the information: a grid whose
    candidates disagree wildly will throw up a high maximum by chance alone.
    """
    trials = len(trial_sharpes)
    if trials < 2:
        return 0.0
    dispersion = float(np.std(trial_sharpes, ddof=1))
    if dispersion == 0:
        return 0.0
    upper = stats.norm.ppf(1 - 1 / trials)
    second = stats.norm.ppf(1 - 1 / (trials * e))
    return dispersion * ((1 - EULER_MASCHERONI) * upper + EULER_MASCHERONI * second)


def deflated_sharpe(returns: pd.Series, trial_sharpes: np.ndarray) -> DeflatedSharpe:
    """Probability that the selected rule's Sharpe survives the trial count."""
    sample = pd.Series(returns).dropna().astype(float)
    observations = len(sample)
    if observations < 3:
        raise ValueError("A deflated Sharpe ratio needs at least three return observations.")
    deviation = float(sample.std(ddof=1))
    observed = float(sample.mean() / deviation) if deviation > 0 else 0.0
    skewness = float(stats.skew(sample, bias=False))
    kurtosis = float(stats.kurtosis(sample, fisher=False, bias=False))
    threshold = expected_maximum_sharpe(np.asarray(trial_sharpes, dtype=float))
    denominator = 1 - skewness * observed + (kurtosis - 1) / 4 * observed ** 2
    if denominator <= 0:
        # A degenerate higher-moment term cannot support an inference; report
        # the null rather than a number that looks like evidence.
        probability = 0.0
    else:
        statistic = (observed - threshold) * sqrt(observations - 1) / sqrt(denominator)
        probability = float(stats.norm.cdf(statistic))
    return DeflatedSharpe(observed, threshold, int(len(trial_sharpes)), observations,
                          skewness, kurtosis, probability, probability > .95)


def probability_of_backtest_overfitting(trial_returns: pd.DataFrame, subsets: int = 4) -> dict:
    """CSCV probability that the in-sample winner underperforms out of sample.

    ``trial_returns`` has one column per candidate rule and one row per period.
    Every candidate must be evaluated on the same periods, otherwise the ranks
    are not comparable.
    """
    frame = trial_returns.dropna(axis=1, how="any")
    periods, candidates = frame.shape
    if candidates < 2:
        raise ValueError("Backtest overfitting needs at least two candidate rules.")
    if subsets % 2 or subsets < 2:
        raise ValueError("subsets must be an even number of at least two.")
    if periods < subsets * 2:
        raise ValueError(f"{periods} periods cannot be split into {subsets} usable subsets.")
    blocks = np.array_split(np.arange(periods), subsets)
    logits: list[float] = []
    records: list[dict] = []
    for chosen in combinations(range(subsets), subsets // 2):
        in_rows = np.concatenate([blocks[index] for index in chosen])
        out_rows = np.concatenate([blocks[index] for index in range(subsets) if index not in chosen])
        in_sample, out_sample = frame.iloc[in_rows], frame.iloc[out_rows]
        in_sharpe = in_sample.mean() / in_sample.std(ddof=1).replace(0, np.nan)
        out_sharpe = out_sample.mean() / out_sample.std(ddof=1).replace(0, np.nan)
        if in_sharpe.isna().all() or out_sharpe.isna().all():
            continue
        winner = in_sharpe.idxmax()
        ranks = out_sharpe.rank(pct=True)
        relative = float(ranks.get(winner, np.nan))
        if not np.isfinite(relative):
            continue
        # Guard the logit at the boundaries so a single perfect or worst rank
        # does not make the average infinite.
        bounded = min(max(relative, 1 / (candidates + 1)), 1 - 1 / (candidates + 1))
        logits.append(log(bounded / (1 - bounded)))
        records.append({"in_sample_winner": str(winner), "out_of_sample_percentile": relative})
    if not logits:
        raise ValueError("No usable CSCV split; check for constant or missing trial returns.")
    array = np.asarray(logits)
    return {
        "probability_of_backtest_overfitting": float((array <= 0).mean()),
        "splits_evaluated": int(len(array)),
        "expected_splits": int(comb(subsets, subsets // 2)),
        "candidates": int(candidates),
        "periods": int(periods),
        "median_out_of_sample_percentile": float(np.median([item["out_of_sample_percentile"] for item in records])),
        "detail": records,
    }
