"""Annual, long-only tests with no fundamental or position-size filters.

The only eligibility condition is observable tradability: an instrument must
have a quoted total-return level on all 252 sessions before the January
decision.  Every eligible instrument receives a non-zero weight in each
candidate.  There is no screen for quality, valuation, liquidity, issuer,
sector, asset count, or maximum position size.

This is an intentionally permissive research diagnostic, not an endorsement
of unrestricted live trading.  Missing prices during the holding year are
forward-filled from the last observed quote, avoiding use of future data to
remove a security from the already-frozen portfolio.  Delisting proceeds are
not reconstructed by this public panel and are therefore a known limitation.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import cvxpy as cp

from total_return_adapter import load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "unrestricted_universe_20260813"
LOOKBACK = 252
ANNUAL_COST_RATE = 0.0015  # 10 bps transaction cost + 5 bps slippage per unit turnover


def first_day(prices: pd.DataFrame, year: int) -> pd.Timestamp:
    return prices.index[(prices.index.year == year)][0]


def score_weights(history: pd.DataFrame, method: str) -> pd.Series:
    returns = history.pct_change().dropna()
    momentum = (1 + returns).prod() - 1
    volatility = returns.std(ddof=1).replace(0, np.nan)
    if method == "equal_weight":
        raw = pd.Series(1.0, index=history.columns)
    elif method == "inverse_volatility":
        raw = 1 / volatility
    elif method == "momentum_all":
        # All names remain invested.  The minimum rank avoids implicit
        # exclusion of negative-momentum instruments.
        raw = momentum.rank(method="first", pct=True)
    elif method == "reversal_all":
        raw = (-momentum).rank(method="first", pct=True)
    elif method == "momentum_inverse_volatility":
        raw = momentum.rank(method="first", pct=True) / volatility
    elif method == "minimum_variance_diagonal":
        raw = 1 / volatility.pow(2)
    else:
        raise ValueError(method)
    raw = raw.replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)
    return raw / raw.sum()


def unrestricted_mvo_weights(history: pd.DataFrame, gamma: float) -> pd.Series:
    """No screen, no cap, no equity limit: the allocator may use every name."""
    returns = history.pct_change().dropna()
    assets = list(returns.columns)
    # At the beginning of the panel only one eligible instrument may exist;
    # cvxpy represents a 1x1 covariance as a scalar, so the unconstrained
    # long-only solution is trivially that single instrument.
    if len(assets) == 1:
        return pd.Series(1.0, index=assets)
    mu = returns.mean().to_numpy() * 252
    covariance = returns.cov().to_numpy() * 252 + np.eye(len(assets)) * 1e-5
    weights = cp.Variable(len(assets))
    objective = cp.Maximize(mu @ weights - gamma / 2 * cp.quad_form(weights, cp.psd_wrap(covariance)))
    problem = cp.Problem(objective, [cp.sum(weights) == 1, weights >= 0])
    problem.solve(solver=cp.CLARABEL)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or weights.value is None:
        raise RuntimeError(f"Unrestricted MVO failed: {problem.status}")
    solution = np.maximum(weights.value, 0)
    return pd.Series(solution / solution.sum(), index=assets)


def evaluate(prices: pd.DataFrame, method: str, cost_multiplier: float = 1.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    assets = prices.columns.drop("TITULO_CDI")
    previous = pd.Series(dtype=float)
    rows: list[dict[str, object]] = []
    holdings: list[dict[str, object]] = []
    for year in range(2015, 2026):
        decision = first_day(prices, year)
        next_date = first_day(prices, year + 1) if year < 2025 else prices.index[-1] + pd.Timedelta(days=1)
        prior = prices.loc[prices.index < decision, assets]
        # The public panel contains some calendar rows with little or no B3
        # activity.  Retain broad market sessions only, then demand a complete
        # 252-session history from every individual candidate.
        coverage = prior.notna().sum(axis=1)
        sessions = prior.loc[coverage >= max(1, int(coverage.max() * .80))]
        if len(sessions) < LOOKBACK + 1:
            continue
        history = sessions.tail(LOOKBACK + 1)
        eligible = history.columns[history.notna().all()].tolist()
        history = history.loc[:, eligible]
        if method.startswith("mvo_gamma_"):
            weights = unrestricted_mvo_weights(history, float(method.removeprefix("mvo_gamma_")))
        else:
            weights = score_weights(history, method)
        realised = prices.loc[(prices.index >= decision) & (prices.index < next_date), eligible].copy()
        # This is an ex-post price observation convention, not a selection
        # rule: after a quote gap, retain the last observable mark.  No asset
        # is removed during the holding year.
        realised = realised.ffill()
        realised_returns = realised.pct_change().dropna(how="all").fillna(0.0)
        asset_growth = (1 + realised_returns).prod()
        gross = float((1 + realised_returns @ weights).prod() - 1)
        previous_aligned = previous.reindex(weights.index, fill_value=0.0)
        turnover = float((weights - previous_aligned).abs().sum())
        net = gross - ANNUAL_COST_RATE * cost_multiplier * turnover
        cdi_levels = prices.loc[(prices.index >= decision) & (prices.index < next_date), "TITULO_CDI"]
        cdi = float(cdi_levels.iloc[-1] / cdi_levels.iloc[0] - 1)
        rows.append({"method": method, "decision_year": year, "decision_date": decision.date().isoformat(),
                     "eligible_assets": len(eligible), "gross_return": gross, "turnover": turnover,
                     "cost_rate": ANNUAL_COST_RATE * cost_multiplier * turnover, "net_return": net, "cdi_return": cdi})
        holdings.extend({"method": method, "decision_year": year, "ticker": ticker, "weight": float(weight)}
                        for ticker, weight in weights.items())
        previous = weights * asset_growth
        previous = previous / previous.sum()
    return pd.DataFrame(rows), pd.DataFrame(holdings)


def metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    def calc(column: str) -> float:
        return float((1 + frame[column]).prod()) ** (1 / len(frame)) - 1
    wealth = (1 + frame.net_return).cumprod()
    return {"years": len(frame), "cagr": calc("net_return"), "cdi_cagr": calc("cdi_return"),
            "excess_cdi": calc("net_return") - calc("cdi_return"), "worst_year": float(frame.net_return.min()),
            "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
            "average_turnover": float(frame.turnover.mean()), "average_universe": float(frame.eligible_assets.mean())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loaded, _ = load_total_return_export(ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv", ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    prices = loaded.set_index("date").sort_index()
    summary: list[dict[str, object]] = []
    methods = ("equal_weight", "inverse_volatility", "minimum_variance_diagonal", "momentum_all", "reversal_all", "momentum_inverse_volatility",
               "mvo_gamma_0.25", "mvo_gamma_1.0", "mvo_gamma_2.5", "mvo_gamma_5.0", "mvo_gamma_10.0")
    for method in methods:
        annual, holdings = evaluate(prices, method)
        annual.to_csv(OUT / f"{method}_annual.csv", index=False)
        holdings.to_csv(OUT / f"{method}_holdings.csv", index=False)
        summary.append({"method": method, "cost_multiple": 1, **metrics(annual)})
    # Only the apparent unrestricted winner receives explicit cost stress;
    # adding cost multiplier is not a selection signal.
    for multiplier in (2, 4, 8):
        annual, _ = evaluate(prices, "mvo_gamma_10.0", multiplier)
        annual.to_csv(OUT / f"mvo_gamma_10.0_cost{multiplier}_annual.csv", index=False)
        summary.append({"method": "mvo_gamma_10.0", "cost_multiple": multiplier, **metrics(annual)})
    report = pd.DataFrame(summary).sort_values("cagr", ascending=False)
    report.to_csv(OUT / "summary.csv", index=False)
    (OUT / "methodology.json").write_text(json.dumps({
        "lookback_sessions": LOOKBACK, "cost_rate_per_unit_turnover": ANNUAL_COST_RATE,
        "selection": "all instruments with complete 252-session history; no fundamental, liquidity, issuer, sector, position or asset-count filters",
        "known_limitation": "holding-period quote gaps are marked at the prior observed total-return value; delisting proceeds are not separately reconstructed",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report.to_string(index=False))


if __name__ == "__main__":
    main()
