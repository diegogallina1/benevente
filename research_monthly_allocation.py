"""Monthly predictive allocation between the equity sleeve and the defensive one.

The annual study could not answer the question it was asked. Eight yearly
observations, four of them spent on training, leave four live calls — not enough
to separate a signal from a coin. Rebalancing the split monthly turns the same
history into ninety-six observations, which is the smallest sample where the
question becomes answerable at all.

The weight is continuous. Forcing an all-in or all-out choice throws away most
of the information in a forecast and produces a turnover profile nobody would
trade; every rule here maps its signal onto a weight in ``[0, cap]``.

Four families are tested, all pre-declared and all fitted walk-forward on an
expanding window:

``static``
    The published policy weight. The bar the others have to clear.
``volatility_target``
    Weight inversely proportional to trailing volatility, scaled so the
    training window would have averaged the policy weight. No return forecast.
``mean_variance``
    The Merton ratio: trailing excess return over risk aversion times variance.
``linear_signal``
    A standardised predictor tilts the weight around the policy centre.

Two oracles bound the exercise from above: the best achievable with perfect
monthly foresight, and the best achievable with a continuous weight under
quadratic utility. Those are not results, they are the size of the prize.

Every rule pays a transaction cost on the weight it moves and, in the after-tax
variant, tax on the gains that monthly trading forces it to realise. Ignoring
either is what makes tactical allocation look free.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


# B3 regular fee plus a representative slippage, charged on the fraction of the
# book that actually moves between the sleeves.
COST_PER_UNIT_TRADED = .0008
EQUITY_TAX_RATE = .15
MINIMUM_TRAINING_MONTHS = 36
RISK_AVERSION_GRID = (2.0, 4.0, 8.0, 16.0)
TILT_GRID = (0.0, .10, .20, .30)


def monthly_panel(daily: pd.DataFrame) -> pd.DataFrame:
    """Month-end returns of the equity sleeve, the defensive sleeve and the market."""
    frame = daily.set_index("date").sort_index()
    needed = [column for column in ("equity_sleeve", "cdi", "IBOVESPA", "BOVA11") if column in frame.columns]
    if "equity_sleeve" not in needed or "cdi" not in needed:
        raise ValueError("The daily curve must carry equity_sleeve and cdi levels.")
    monthly = frame[needed].resample("ME").last().dropna(how="any")
    returns = monthly.pct_change().dropna()
    returns.columns = [f"{column}_return" for column in returns.columns]
    panel = returns.rename(columns={"equity_sleeve_return": "equity", "cdi_return": "cash"})
    panel["excess"] = panel.equity - panel.cash
    levels = monthly.equity_sleeve.reindex(panel.index)
    market = monthly.IBOVESPA.reindex(panel.index) if "IBOVESPA" in monthly else levels
    # Every predictor is measured on information available at the close of the
    # month before the one it is used to allocate.
    panel["trailing_12m"] = levels.pct_change(12)
    panel["trailing_volatility"] = panel.equity.rolling(12).std(ddof=1) * (12 ** .5)
    panel["short_volatility"] = panel.equity.rolling(3).std(ddof=1) * (12 ** .5)
    panel["above_trend"] = (levels / levels.rolling(10).mean() - 1)
    panel["drawdown"] = levels / levels.cummax() - 1
    panel["market_trailing_12m"] = market.pct_change(12)
    panel["cash_level"] = panel.cash.rolling(12).sum()
    return panel.shift(0)


def _lagged(panel: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Shift predictors by one month so no weight uses its own outcome."""
    lagged = panel.copy()
    for column in columns:
        lagged[column] = panel[column].shift(1)
    return lagged.dropna(subset=columns)


def _apply(weights: pd.Series, panel: pd.DataFrame, cap: float, taxed: bool) -> pd.DataFrame:
    """Compound a weight path, charging turnover and, optionally, tax."""
    frame = pd.DataFrame({"weight": weights.clip(0, cap)}, index=weights.index)
    frame["equity"] = panel.equity.reindex(frame.index)
    frame["cash"] = panel.cash.reindex(frame.index)
    gross, turnover, previous = [], [], 0.0
    for row in frame.itertuples(index=False):
        drifted = previous
        traded = abs(row.weight - drifted)
        turnover.append(traded)
        month = row.weight * row.equity + (1 - row.weight) * row.cash - traded * COST_PER_UNIT_TRADED
        if taxed and row.weight > 0 and row.equity > 0:
            # Monthly trading realises the equity gain of the fraction sold.
            month -= EQUITY_TAX_RATE * row.weight * row.equity * min(1.0, traded / max(row.weight, 1e-9))
        gross.append(month)
        # Weights drift with the relative performance of the two sleeves.
        end_equity = row.weight * (1 + row.equity)
        end_cash = (1 - row.weight) * (1 + row.cash)
        previous = end_equity / (end_equity + end_cash) if end_equity + end_cash > 0 else row.weight
    frame["net_return"] = gross
    frame["turnover"] = turnover
    return frame


def _metrics(returns: pd.Series, cash: pd.Series) -> dict:
    wealth = (1 + returns).cumprod()
    years = len(returns) / 12
    excess = returns - cash.reindex(returns.index)
    deviation = float(returns.std(ddof=1))
    return {
        "months": int(len(returns)),
        "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "annual_volatility": float(deviation * (12 ** .5)),
        "sharpe_vs_cash": float(excess.mean() / excess.std(ddof=1) * (12 ** .5)) if excess.std(ddof=1) else float("nan"),
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        "months_beating_cash": int((returns > cash.reindex(returns.index)).sum()),
    }


def build_rules(panel: pd.DataFrame, cap: float, policy_weight: float,
                predictors: list[str], training_months: int = MINIMUM_TRAINING_MONTHS) -> dict[str, pd.Series]:
    """Weight paths, each fitted only on months that had already closed."""
    MINIMUM_TRAINING_MONTHS = training_months  # noqa: N806 - local override of the module default
    lagged = _lagged(panel, ["trailing_12m", "trailing_volatility", "short_volatility",
                             "above_trend", "drawdown", "market_trailing_12m"])
    index = lagged.index[MINIMUM_TRAINING_MONTHS:]
    paths: dict[str, list[float]] = {"static": [], "volatility_target": [], "mean_variance": []}
    for predictor in predictors:
        paths[f"linear_{predictor}"] = []
    for position, date in enumerate(index, start=MINIMUM_TRAINING_MONTHS):
        history = lagged.iloc[:position]
        current = lagged.iloc[position]
        paths["static"].append(policy_weight)

        # Volatility targeting: the scale is whatever would have averaged the
        # policy weight over the training window, so the rule adds timing, not
        # a higher average exposure.
        volatility = float(current.trailing_volatility)
        scale = float((history.trailing_volatility.replace(0, np.nan)).median()) * policy_weight
        paths["volatility_target"].append(scale / volatility if volatility > 0 else policy_weight)

        # Merton ratio with risk aversion chosen from a small pre-declared grid
        # on the training window alone.
        expected = float(history.excess.mean())
        variance = float(history.excess.var(ddof=1))
        best_gamma, best_score = RISK_AVERSION_GRID[0], -np.inf
        for gamma in RISK_AVERSION_GRID:
            trial = np.clip(expected / (gamma * variance), 0, cap) if variance > 0 else policy_weight
            realised = trial * history.equity + (1 - trial) * history.cash
            score = realised.mean() / realised.std(ddof=1) if realised.std(ddof=1) else -np.inf
            if score > best_score:
                best_gamma, best_score = gamma, score
        current_expected = float(history.excess.tail(24).mean())
        current_variance = float(history.excess.tail(24).var(ddof=1))
        paths["mean_variance"].append(
            current_expected / (best_gamma * current_variance) if current_variance > 0 else policy_weight)

        for predictor in predictors:
            series = history[predictor].dropna()
            centre, spread = float(series.mean()), float(series.std(ddof=1))
            value = float(current[predictor])
            z = (value - centre) / spread if spread > 0 else 0.0
            best_tilt, best_tilt_score = TILT_GRID[0], -np.inf
            for tilt in TILT_GRID:
                trained_z = ((history[predictor] - centre) / spread).fillna(0) if spread > 0 else history[predictor] * 0
                trial = (policy_weight + tilt * trained_z).clip(0, cap)
                realised = trial * history.equity + (1 - trial) * history.cash
                score = realised.mean() / realised.std(ddof=1) if realised.std(ddof=1) else -np.inf
                if score > best_tilt_score:
                    best_tilt, best_tilt_score = tilt, score
            paths[f"linear_{predictor}"].append(policy_weight + best_tilt * z)
    return {name: pd.Series(values, index=index) for name, values in paths.items()}


def oracles(panel: pd.DataFrame, index: pd.Index, cap: float) -> dict[str, pd.Series]:
    """Upper bounds. Not results: the size of what perfect timing would win."""
    window = panel.loc[index]
    binary = (window.excess > 0).astype(float) * cap
    # Continuous oracle under quadratic utility, using the month's own outcome.
    variance = float(window.excess.var(ddof=1))
    continuous = (window.excess / (4 * variance)).clip(0, cap) if variance > 0 else binary
    return {"oracle_binary": binary, "oracle_continuous": continuous}


def main() -> None:
    parser = argparse.ArgumentParser(description="Monthly continuous allocation between equity and the defensive sleeve.")
    parser.add_argument("--daily", default="artifacts/published_nested/daily_curve.csv")
    parser.add_argument("--cap", type=float, default=.95)
    parser.add_argument("--policy-weight", type=float, default=.55)
    parser.add_argument("--output", default="artifacts/monthly_allocation")
    parser.add_argument("--training-months", type=int, default=MINIMUM_TRAINING_MONTHS,
                        help="Months of history each fit may use before the first live allocation. "
                             "Shorter windows buy live observations at the cost of a weaker fit; run several.")
    args = parser.parse_args()

    daily = pd.read_csv(args.daily, parse_dates=["date"])
    panel = monthly_panel(daily)
    predictors = ["trailing_12m", "above_trend", "drawdown", "market_trailing_12m", "short_volatility"]
    rules = build_rules(panel, args.cap, args.policy_weight, predictors, args.training_months)
    index = next(iter(rules.values())).index
    rules.update(oracles(panel, index, args.cap))

    cash = panel.cash.reindex(index)
    rows, curves = [], {}
    static_returns = None
    for name, weights in rules.items():
        applied = _apply(weights, panel, args.cap, taxed=False)
        after_tax = _apply(weights, panel, args.cap, taxed=True)
        if name == "static":
            static_returns = applied.net_return
        record = {"rule": name, "average_weight": float(weights.clip(0, args.cap).mean()),
                  "average_turnover": float(applied.turnover.mean()),
                  **_metrics(applied.net_return, cash),
                  "cagr_after_tax": _metrics(after_tax.net_return, cash)["cagr"]}
        rows.append(record)
        curves[name] = applied.net_return
    table = pd.DataFrame(rows).set_index("rule")
    # Is any rule's advantage over the published static policy distinguishable
    # from noise? With ninety-six months a paired test finally has something to
    # work with.
    for name, series in curves.items():
        if name == "static":
            continue
        difference = (series - static_returns).dropna()
        statistic, p_value = stats.ttest_1samp(difference, 0.0)
        table.loc[name, "excess_vs_static_annual"] = float(difference.mean() * 12)
        table.loc[name, "excess_p_value"] = float(p_value)

    for reference in ("IBOVESPA_return", "BOVA11_return"):
        if reference in panel.columns:
            series = panel[reference].reindex(index)
            table.loc[f"reference_{reference.replace('_return', '')}"] = {
                **_metrics(series, cash), "average_weight": 1.0, "average_turnover": 0.0,
                "cagr_after_tax": np.nan, "excess_vs_static_annual": np.nan, "excess_p_value": np.nan}
    table.loc["reference_CDI"] = {**_metrics(cash, cash), "average_weight": 0.0, "average_turnover": 0.0,
                                  "cagr_after_tax": np.nan, "excess_vs_static_annual": np.nan, "excess_p_value": np.nan}

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    table.sort_values("cagr", ascending=False).to_csv(output / "monthly_allocation_rules.csv")
    pd.DataFrame(rules).to_csv(output / "weight_paths.csv")
    panel.to_csv(output / "monthly_panel.csv")
    candidates = table.drop(index=[name for name in table.index if name.startswith(("oracle", "reference", "static"))])
    significant = candidates[candidates.excess_p_value < .05] if "excess_p_value" in candidates else candidates.iloc[0:0]
    summary = {
        "months_evaluated": int(len(index)),
        "evaluation_window": f"{index[0].date()} a {index[-1].date()}",
        "rules_tested": int(len(candidates)),
        "static_cagr": float(table.loc["static", "cagr"]),
        "oracle_binary_cagr": float(table.loc["oracle_binary", "cagr"]),
        "prize_for_perfect_monthly_timing": float(table.loc["oracle_binary", "cagr"] - table.loc["static", "cagr"]),
        "best_rule": str(candidates.cagr.idxmax()) if len(candidates) else None,
        "best_rule_cagr": float(candidates.cagr.max()) if len(candidates) else None,
        "rules_beating_static_significantly": sorted(significant.index.tolist()),
        "reading": ("A rule only counts if its advantage over the published static weight survives a paired test "
                    "across the whole window. Five rules were tried, so a single p-value near five per cent is not "
                    "yet evidence; it is one draw from five."),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table.sort_values("cagr", ascending=False).to_string(float_format=lambda value: f"{value:.4f}"))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
