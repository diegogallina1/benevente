"""Ask whether January can tell you what the year will reward.

The intuition behind a dynamic allocation is easy to state: some years reward
equity, some years reward the defensive sleeve, and if the pattern were legible
you would tilt accordingly. The trap is that the pattern is only visible after
the year closes. Recording that 2020 wanted cash is a description of 2020, not a
rule you could have run in January 2020.

So the question is split in two.

First, the oracle. For each year, given the basket the strategy actually held,
the ideal equity weight is one hundred per cent when the equity sleeve beat CDI
and zero when it did not. That is the target a perfect forecaster would hit, and
it is recorded here purely as a benchmark for how much is at stake.

Second, the forecast. Every predictor used here is observable on the first
trading session of the year: the CDI level, the trailing return and volatility
of the market, how far the index sits below its own peak, and the earnings yield
of the eligible universe against CDI. The relation between predictor and oracle
is then tested walk-forward — the sign rule for year *t* is fitted only on years
before *t* — because a relation fitted on the whole sample and reported on the
whole sample proves nothing.

With roughly a decade of annual observations this study is underpowered by
construction, and the output says so. It is designed to tell you honestly
whether a signal is there, not to manufacture one.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


MINIMUM_TRAINING_YEARS = 4


def oracle_table(annual: pd.DataFrame) -> pd.DataFrame:
    """Equity sleeve versus CDI, and the ideal weight with hindsight."""
    frame = annual.copy()
    weight = frame.target_equity_weight.replace(0, np.nan)
    frame["equity_sleeve_return"] = frame.equity_gain_rate / weight
    frame["equity_beat_cdi"] = frame.equity_sleeve_return > frame.cdi_net_return
    frame["oracle_equity_weight"] = frame.equity_beat_cdi.map({True: 1.0, False: 0.0})
    frame["oracle_return"] = np.where(frame.equity_beat_cdi, frame.equity_sleeve_return, frame.cdi_net_return)
    frame["spread_equity_minus_cdi"] = frame.equity_sleeve_return - frame.cdi_net_return
    return frame


def january_predictors(annual: pd.DataFrame, benchmarks: pd.DataFrame,
                       fundamentals: pd.DataFrame) -> pd.DataFrame:
    """State variables a committee could read on the decision date itself."""
    rows: list[dict] = []
    index = benchmarks.IBOVESPA.dropna()
    for item in annual.itertuples(index=False):
        decision = pd.Timestamp(item.decision_date)
        history = index.loc[index.index < decision]
        if len(history) < 260:
            continue
        trailing = history.tail(252)
        row = {
            "decision_year": int(item.decision_year),
            "cdi_level_at_january": float(item.cdi_net_return),
            "market_trailing_12m_return": float(trailing.iloc[-1] / trailing.iloc[0] - 1),
            "market_trailing_volatility": float(trailing.pct_change().std(ddof=1) * (252 ** .5)),
            "market_drawdown_from_peak": float(history.iloc[-1] / history.cummax().iloc[-1] - 1),
        }
        available = fundamentals[(fundamentals.available_date <= decision)
                                 & (fundamentals.decision_date == decision.date().isoformat())]
        earnings_yield = (1 / available.price_to_earnings.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
        row["universe_earnings_yield"] = float(earnings_yield.median()) if len(earnings_yield) else np.nan
        rows.append(row)
    frame = pd.DataFrame(rows)
    if "universe_earnings_yield" in frame:
        # The classic equity-versus-cash gauge: what the eligible universe earns
        # per unit of price, against what cash pays.
        frame["earnings_yield_minus_cdi"] = frame.universe_earnings_yield - frame.cdi_level_at_january
    return frame


def walk_forward_rule(merged: pd.DataFrame, predictor: str,
                      minimum_training_years: int = MINIMUM_TRAINING_YEARS) -> dict:
    """Fit the sign of a one-variable rule on prior years, apply it once.

    Only the direction is fitted, not a threshold and not a coefficient. One
    binary degree of freedom is the most a decade of annual observations can
    support without the fit becoming the result.
    """
    calls: list[dict] = []
    for position in range(len(merged)):
        if position < minimum_training_years:
            continue
        history = merged.iloc[:position]
        current = merged.iloc[position]
        if not np.isfinite(current[predictor]):
            continue
        centre = float(history[predictor].median())
        above = history[history[predictor] > centre].equity_beat_cdi
        below = history[history[predictor] <= centre].equity_beat_cdi
        if above.empty or below.empty:
            continue
        # Direction is whichever side of the median hosted more equity-favouring
        # years in the training window.
        direction = 1 if above.mean() >= below.mean() else -1
        signal = (current[predictor] > centre) if direction == 1 else (current[predictor] <= centre)
        calls.append({
            "decision_year": int(current.decision_year),
            "predictor": predictor,
            "predictor_value": float(current[predictor]),
            "training_median": centre,
            "fitted_direction": direction,
            "predicted_equity_year": bool(signal),
            "actual_equity_year": bool(current.equity_beat_cdi),
            "correct": bool(signal == current.equity_beat_cdi),
            "equity_sleeve_return": float(current.equity_sleeve_return),
            "cdi_net_return": float(current.cdi_net_return),
            "rule_return": float(current.equity_sleeve_return if signal else current.cdi_net_return),
        })
    if not calls:
        return {"predictor": predictor, "calls": 0, "usable": False}
    frame = pd.DataFrame(calls)
    hits = int(frame.correct.sum())
    total = int(len(frame))
    # Probability of getting at least this many right by coin flip.
    from math import comb
    p_value = sum(comb(total, k) for k in range(hits, total + 1)) / 2 ** total
    def cagr(series: pd.Series) -> float:
        return float((1 + series).prod() ** (1 / len(series)) - 1)
    return {
        "predictor": predictor,
        "calls": total,
        "usable": True,
        "hit_rate": hits / total,
        "hits": hits,
        "coin_flip_p_value": float(p_value),
        "rule_cagr": cagr(frame.rule_return),
        "always_equity_cagr": cagr(frame.equity_sleeve_return),
        "always_cdi_cagr": cagr(frame.cdi_net_return),
        "detail": calls,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Test whether January-observable state predicts the year's winner.")
    parser.add_argument("--annual", default="artifacts/published_nested/annual_results.csv")
    parser.add_argument("--benchmarks", default="data/benchmarks_market_2013_2025.csv")
    parser.add_argument("--fundamentals", default="data/fundamentals_b3_cvm_full_2013_2025_v2.csv")
    parser.add_argument("--output", default="artifacts/allocation_regime")
    args = parser.parse_args()

    annual = pd.read_csv(args.annual)
    benchmarks = pd.read_csv(args.benchmarks, parse_dates=["date"]).set_index("date")
    fundamentals = pd.read_csv(args.fundamentals, parse_dates=["available_date"])
    oracle = oracle_table(annual)
    predictors = january_predictors(oracle, benchmarks, fundamentals)
    merged = oracle.merge(predictors, on="decision_year", how="inner").sort_values("decision_year").reset_index(drop=True)

    candidates = [column for column in ("earnings_yield_minus_cdi", "cdi_level_at_january",
                                        "market_trailing_12m_return", "market_trailing_volatility",
                                        "market_drawdown_from_peak")
                  if column in merged.columns and merged[column].notna().sum() >= MINIMUM_TRAINING_YEARS + 1]
    results = [walk_forward_rule(merged, predictor) for predictor in candidates]
    usable = [item for item in results if item.get("usable")]

    def cagr(series: pd.Series) -> float:
        return float((1 + series).prod() ** (1 / len(series)) - 1)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output / "oracle_and_predictors.csv", index=False)
    pd.DataFrame([{key: value for key, value in item.items() if key != "detail"} for item in results]).to_csv(
        output / "walk_forward_rules.csv", index=False)
    for item in usable:
        pd.DataFrame(item["detail"]).to_csv(output / f"calls_{item['predictor']}.csv", index=False)
    summary = {
        "years": int(len(merged)),
        "equity_years": int(merged.equity_beat_cdi.sum()),
        "cash_years": int((~merged.equity_beat_cdi).sum()),
        "oracle_cagr": cagr(merged.oracle_return),
        "always_equity_cagr": cagr(merged.equity_sleeve_return),
        "always_cdi_cagr": cagr(merged.cdi_net_return),
        "prize_for_perfect_timing": cagr(merged.oracle_return) - cagr(merged.equity_sleeve_return),
        "best_walk_forward_rule": max(usable, key=lambda item: item["hit_rate"])["predictor"] if usable else None,
        "best_hit_rate": max((item["hit_rate"] for item in usable), default=None),
        "power_warning": (
            f"{len(merged)} annual observations. A rule needs roughly nine of eleven calls right before a coin flip "
            "becomes an implausible explanation. Read the p-values, not the returns."
        ),
        "rules": [{key: value for key, value in item.items() if key != "detail"} for item in results],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
