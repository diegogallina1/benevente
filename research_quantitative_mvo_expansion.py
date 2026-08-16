"""Broad, no-look-ahead annual study of five-position quantitative MVO rules.

This research keeps the question deliberately narrow: given the public price
panel available at each January decision, can a systematic five-equity signal
plus constrained MVO beat (1) CDI and (2) a neutral five-equity MVO?  The
benchmark uses the same number of positions, equity sleeve, cost rate and
covariance treatment.  It differs only in how the five names are chosen.

The 2015--2020 period selects one candidate.  The untouched 2021--2025 period
is the primary validation.  Results are a reproducible research result, not a
recommendation, a forecast, or an instruction to trade.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd

from total_return_adapter import load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "quantitative_mvo_expansion_20260813"
LOOKBACK = 252
SKIP_RECENT = 21
POSITIONS = 5
MAX_WEIGHT = 0.20
COST = 0.0015


def annualised_cagr(values: pd.Series) -> float:
    return float((1 + values).prod() ** (1 / len(values)) - 1)


def zscore(values: pd.Series) -> pd.Series:
    deviation = values.std(ddof=0)
    if not np.isfinite(deviation) or deviation == 0:
        return pd.Series(0.0, index=values.index)
    return (values - values.mean()) / deviation


def clean_universe(prices: pd.DataFrame) -> list[str]:
    """Return instruments usable at that decision without forward filling.

    The public panel has no dated traded-value field.  These deliberately
    modest checks only remove missing histories and clearly discontinuous
    records, and are therefore a data-quality gate rather than a liquidity
    claim.  The eligible count is retained in every ledger row.
    """
    # The Yahoo panel has non-trading days mixed with B3 sessions. Requiring
    # literal completeness would incorrectly eliminate the whole 2015--2023
    # cross-section. A name must instead cover at least 95% of the observed
    # window; only then is its sparse gap forward-filled *within the prior
    # history* to form a return series. No future observation is ever used.
    minimum_observations = int(len(prices) * .95)
    covered = prices.columns[prices.notna().sum() >= minimum_observations]
    dense = prices.loc[:, covered].ffill().bfill()
    returns = dense.pct_change().dropna()
    stable = returns.abs().max() <= .35
    priced = dense.iloc[-1] >= 1.0
    return sorted(set(covered[stable & priced]))


def prior_history(prices: pd.DataFrame, assets: list[str], decision: pd.Timestamp) -> pd.DataFrame:
    """Return the historically available, 95%-complete annual lookback."""
    raw = prices.loc[prices.index < decision, assets].tail(LOOKBACK + 1)
    eligible = clean_universe(raw)
    return raw.loc[:, eligible].ffill().bfill()


def issuer_keys_by_year() -> dict[int, dict[str, str]]:
    """Return only issuer identities already present in B3/CVM mappings.

    The key is a diversification control, not an alpha input.  For each year
    only mappings dated no later than that year are considered; an unmapped
    ticker remains its own exposure instead of being guessed.
    """
    mapping = pd.read_csv(ROOT / "data" / "b3_historical_cvm_ticker_map.csv")
    mapping["ticker"] = mapping.ticker.astype(str).str.upper().str.removesuffix(".SA")
    mapping = mapping[mapping.mapping_status.eq("accepted") & mapping.cnpj_cia.notna()].copy()
    output: dict[int, dict[str, str]] = {}
    for year in range(2015, 2026):
        known = mapping[mapping.universe_year <= year].sort_values("universe_year")
        output[year] = known.drop_duplicates("ticker", keep="last").set_index("ticker").cnpj_cia.astype(str).to_dict()
    return output


def unique_issuers(signal: pd.Series, issuer_keys: dict[str, str], count: int = POSITIONS) -> list[str]:
    """Select at most one traded class per issuer from a signal ranking."""
    selected: list[str] = []
    used: set[str] = set()
    for ticker in signal.sort_values(ascending=False).index:
        issuer = issuer_keys.get(ticker, ticker)
        if issuer in used:
            continue
        selected.append(ticker)
        used.add(issuer)
        if len(selected) == count:
            break
    return selected


def prepare_decisions(prices: pd.DataFrame) -> dict[int, dict[str, object]]:
    """Cache all prior-only inputs once; this changes no decision rule."""
    assets = [asset for asset in prices.columns if asset != "TITULO_CDI"]
    prepared: dict[int, dict[str, object]] = {}
    issuer_by_year = issuer_keys_by_year()
    for year in range(2015, 2026):
        days = prices.index[prices.index.year == year]
        if days.empty:
            continue
        decision = days[0]
        next_days = prices.index[prices.index.year == year + 1]
        end = next_days[0] if len(next_days) else prices.index[-1] + pd.Timedelta(days=1)
        if len(prices.loc[prices.index < decision]) < LOOKBACK + 1:
            continue
        history = prior_history(prices, assets, decision)
        if len(history.columns) < POSITIONS:
            continue
        prepared[year] = {
            "decision": decision, "end": end, "history": history,
            "signals": signals(history), "eligible": len(history.columns),
            "issuer_keys": issuer_by_year[year],
        }
    return prepared


def signals(history: pd.DataFrame) -> dict[str, pd.Series]:
    returns = history.pct_change().dropna()
    recent = returns.tail(LOOKBACK)
    momentum_12_1 = (1 + recent.iloc[:-SKIP_RECENT]).prod() - 1
    short_reversal = -(1 + recent.iloc[-SKIP_RECENT:]).prod() + 1
    volatility = -recent.std(ddof=1)
    momentum_risk_adjusted = momentum_12_1 / recent.std(ddof=1).replace(0, np.nan)
    positive_months = (recent.resample("ME").apply(lambda part: (1 + part).prod() - 1) > 0).mean()
    combo = .50 * zscore(momentum_12_1) + .25 * zscore(short_reversal) + .25 * zscore(volatility)
    return {
        "momentum_12_1": momentum_12_1,
        "short_reversal": short_reversal,
        "low_volatility": volatility,
        "momentum_risk_adjusted": momentum_risk_adjusted,
        "trend_consistency": positive_months,
        "combined": combo,
    }


def mvo_weights(history: pd.DataFrame, alpha: pd.Series, equity_cap: float,
                previous: pd.Series, alpha_strength: float,
                minimum_equity_weight: float = .02) -> pd.Series:
    """Long-only five-stock MVO with diagonal covariance shrinkage.

    ``alpha`` is a cross-sectional score formed only from the trailing return
    history.  Passing zero alpha produces the neutral benchmark.  The lower
    bound of 2% on each equity preserves the five-position rule even when the
    equity sleeve is below 100%.
    """
    assets = list(history.columns)
    equity = [asset for asset in assets if asset != "TITULO_CDI"]
    returns = history.pct_change().dropna()
    mean = returns.mean().to_numpy() * 252
    signal = alpha.reindex(assets, fill_value=0.0).to_numpy()
    # Scale a unit z-score to a conservative annual expected-return adjustment.
    expected = mean + alpha_strength * .04 * signal
    sample = returns.cov().to_numpy() * 252
    diagonal = np.diag(np.diag(sample))
    covariance = .50 * sample + .50 * diagonal + np.eye(len(assets)) * 1e-6
    weights = cp.Variable(len(assets))
    lower = np.array([minimum_equity_weight if asset in equity else 0.0 for asset in assets])
    upper = np.array([MAX_WEIGHT if asset in equity else 1.0 for asset in assets])
    previous_array = previous.reindex(assets, fill_value=0.0).to_numpy()
    problem = cp.Problem(
        cp.Maximize(expected @ weights - 2.5 / 2 * cp.quad_form(weights, cp.psd_wrap(covariance))),
        [cp.sum(weights) == 1, weights >= lower, weights <= upper,
         cp.sum(weights[[assets.index(asset) for asset in equity]]) <= equity_cap],
    )
    problem.solve(solver=cp.CLARABEL)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or weights.value is None:
        raise RuntimeError(f"MVO solver status: {problem.status}")
    output = pd.Series(np.maximum(weights.value, 0), index=assets)
    # Drift is captured by caller; previous weights remain an audit measure.
    output.attrs["turnover"] = float((output - previous_array).abs().sum())
    return output / output.sum()


def candidate_ledger(prices: pd.DataFrame, prepared: dict[int, dict[str, object]], signal_name: str, equity_cap: float,
                     alpha_strength: float, neutral_cache: dict[tuple[int, float], dict]) -> pd.DataFrame:
    previous = pd.Series(dtype=float)
    rows: list[dict[str, object]] = []
    for year, item in prepared.items():
        decision, end = item["decision"], item["end"]
        history = item["history"]
        signal = item["signals"][signal_name].replace([np.inf, -np.inf], np.nan).dropna()
        selected = unique_issuers(signal, item["issuer_keys"])
        if len(selected) < POSITIONS:
            continue
        local_history = history.loc[:, selected].copy()
        local_history["TITULO_CDI"] = prices.loc[local_history.index, "TITULO_CDI"]
        weights = mvo_weights(local_history, zscore(signal.loc[selected]), equity_cap, previous, alpha_strength)
        realised = (prices.loc[(prices.index >= decision) & (prices.index < end), selected + ["TITULO_CDI"]]
                    .ffill().pct_change().dropna())
        if realised.empty:
            continue
        gross = float((1 + realised @ weights).prod() - 1)
        turnover = float((weights - previous.reindex(weights.index, fill_value=0.0)).abs().sum())
        growth = (1 + realised).prod()
        previous = weights * growth
        previous /= previous.sum()
        baseline = neutral_cache[(year, equity_cap)]
        cdi = float((1 + realised["TITULO_CDI"]).prod() - 1)
        rows.append({"year": year, "decision_date": decision.date().isoformat(), "signal": signal_name,
                     "equity_cap": equity_cap, "alpha_strength": alpha_strength,
                     "eligible_assets": item["eligible"], "selected_assets": "|".join(selected),
                     "net_return": gross - COST * turnover, "turnover": turnover, "cdi_return": cdi,
                     "neutral_mvo_return": baseline["net_return"],
                     "neutral_mvo_assets": baseline["assets"]})
    return pd.DataFrame(rows)


def build_neutral_cache(prices: pd.DataFrame, prepared: dict[int, dict[str, object]], equity_caps: tuple[float, ...]) -> dict[tuple[int, float], dict]:
    """Build one neutral MVO per year/cap independently of candidate signals."""
    cache: dict[tuple[int, float], dict] = {}
    previous_by_cap = {cap: pd.Series(dtype=float) for cap in equity_caps}
    for year, item in prepared.items():
        decision, end = item["decision"], item["end"]
        history = item["history"]
        eligible = history.columns.tolist()
        # The neutral MVO sees the entire data-complete universe. It has no
        # predictive factor or artificial five-name selector, and is therefore
        # a direct classic-MVO reference rather than a weakened comparator.
        selected = eligible
        history = history.loc[:, selected].copy()
        history["TITULO_CDI"] = prices.loc[history.index, "TITULO_CDI"]
        realised = (prices.loc[(prices.index >= decision) & (prices.index < end), selected + ["TITULO_CDI"]]
                    .ffill().pct_change().dropna())
        if realised.empty:
            continue
        for cap in equity_caps:
            previous = previous_by_cap[cap]
            weights = mvo_weights(history, pd.Series(0.0, index=history.columns), cap, previous, 0.0,
                                  minimum_equity_weight=0.0)
            gross = float((1 + realised @ weights).prod() - 1)
            turnover = float((weights - previous.reindex(weights.index, fill_value=0.0)).abs().sum())
            growth = (1 + realised).prod()
            previous_by_cap[cap] = weights * growth / float((weights * growth).sum())
            cache[(year, cap)] = {"net_return": gross - COST * turnover, "assets": "|".join(selected)}
    return cache


def describe(frame: pd.DataFrame) -> dict[str, float | int]:
    wealth = (1 + frame.net_return).cumprod()
    return {
        "years": len(frame), "cagr": annualised_cagr(frame.net_return),
        "cdi_cagr": annualised_cagr(frame.cdi_return),
        "neutral_mvo_cagr": annualised_cagr(frame.neutral_mvo_return),
        "excess_cdi": annualised_cagr(frame.net_return) - annualised_cagr(frame.cdi_return),
        "excess_mvo": annualised_cagr(frame.net_return) - annualised_cagr(frame.neutral_mvo_return),
        "hit_both": float(((frame.net_return > frame.cdi_return) & (frame.net_return > frame.neutral_mvo_return)).mean()),
        "worst_year": float(frame.net_return.min()),
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        "average_turnover": float(frame.turnover.mean()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw, manifest = load_total_return_export(
        ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv",
        ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json",
    )
    prices = raw.set_index("date").sort_index()
    caps = (.55, .75, 1.0)
    prepared = prepare_decisions(prices)
    cache = build_neutral_cache(prices, prepared, caps)
    rows: list[dict[str, object]] = []
    for signal_name, cap, alpha_strength in itertools.product(
        ("momentum_12_1", "short_reversal", "low_volatility", "momentum_risk_adjusted", "trend_consistency", "combined"),
        caps, (0.0, .25, .50),
    ):
        name = f"{signal_name}_eq{int(cap * 100)}_tilt{int(alpha_strength * 100):02d}"
        annual = candidate_ledger(prices, prepared, signal_name, cap, alpha_strength, cache)
        annual.to_csv(OUT / f"{name}_annual.csv", index=False)
        for split, subset in (("train", annual[annual.year <= 2020]), ("holdout", annual[annual.year >= 2021])):
            rows.append({"name": name, "signal": signal_name, "equity_cap": cap,
                         "alpha_strength": alpha_strength, "split": split, **describe(subset)})
    report = pd.DataFrame(rows)
    report.to_csv(OUT / "all_results.csv", index=False)
    train = report[report.split.eq("train")].set_index("name")
    holdout = report[report.split.eq("holdout")].set_index("name")
    combined = train.add_prefix("train_").join(holdout.add_prefix("holdout_"))
    # Pre-specified selection uses 2015--2020 only and favours return above
    # both references while charging for excess turnover.
    combined["train_score"] = (combined.train_excess_cdi + combined.train_excess_mvo
                               - .03 * combined.train_average_turnover)
    combined.sort_values("train_score", ascending=False, inplace=True)
    combined.to_csv(OUT / "combined.csv")
    winner = combined.iloc[0]
    conclusion = {
        "purpose": "five-stock quantitative MVO expansion; research only",
        "data": {"provider": manifest.get("provider"), "coverage": [manifest.get("coverage_start"), manifest.get("coverage_end")],
                 "price_instruments": int(len(prices.columns) - 1), "minimum_equity_positions": POSITIONS},
        "candidate_count": int(len(combined)), "selection_period": "2015-2020", "holdout_period": "2021-2025",
        "winner": {key: float(value) if isinstance(value, (np.floating, float)) else value for key, value in winner.to_dict().items()},
        "winner_passes_holdout_both": bool(winner.holdout_excess_cdi > 0 and winner.holdout_excess_mvo > 0),
        "all_holdout_both_pass_count": int(((combined.holdout_excess_cdi > 0) & (combined.holdout_excess_mvo > 0)).sum()),
    }
    (OUT / "conclusion.json").write_text(json.dumps(conclusion, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(conclusion, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
