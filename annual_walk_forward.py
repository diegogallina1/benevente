"""Annual point-in-time walk-forward evaluation for Benevente Quant AI.

At the first available trading day of every calendar year the engine freezes a
portfolio from data known on or before that date.  The portfolio is held until
the next annual review.  The following year's returns are *never* used to
choose the current year's assets, weights, or replacement reasons.

This is deliberately an evaluation protocol, not an optimizer that searches
the historical future for the highest return.  A valid long history needs a
dated constituent file and dated fundamental snapshots for every review year.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import argparse
import json
from pathlib import Path

import pandas as pd

from config import SystemConfig
from execution_costs import ClearB3CostModel
from fundamentals import FundamentalSnapshot
from annual_decision_evidence import DecisionEvidence
from annual_input_contract import validate_annual_inputs
from optimizer import MeanVarianceOptimizer
from portfolio_recommendation import PortfolioProposal, ValuePortfolioPlanner


# These are allocation guardrails, not return forecasts. Keeping them here
# makes a research run reproducible from a human risk-profile label, while the
# protocol JSON still contains the exact numerical limits used.
RISK_PROFILE_LIMITS: dict[str, dict[str, float | str]] = {
    "conservador": {"maximum_equity_weight": .35, "maximum_asset_weight": .10, "review_frequency": "trimestral"},
    "moderado": {"maximum_equity_weight": .55, "maximum_asset_weight": .12, "review_frequency": "trimestral"},
    "arrojado": {"maximum_equity_weight": .75, "maximum_asset_weight": .15, "review_frequency": "semestral"},
}


@dataclass(frozen=True)
class BrazilianTaxModel:
    """Personal-investor Brazilian taxation of an annually rebalanced book.

    Equity gains realised in ordinary (non day-trade) trades are taxed at 15%,
    with the monthly exemption for total sales up to twenty thousand reais.
    The defensive sleeve follows the regressive fixed-income table; an annual
    review falls in the 361-to-720-day band at 17.5%.

    The model assumes the rebalanced fraction of each sleeve is realised at the
    review, which is what an annual protocol actually does.  Gains on positions
    that are merely held are deferred, exactly as the law treats them.
    """
    equity_rate: float = .15
    fixed_income_rate: float = .175
    monthly_sale_exemption_brl: float = 20_000.0

    @staticmethod
    def _share(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    def annual_tax_brl(self, equity_gain_brl: float, equity_realised_share: float, equity_sold_brl: float,
                       fixed_income_gain_brl: float, fixed_income_redeemed_share: float) -> float:
        realised_equity_gain = equity_gain_brl * self._share(equity_realised_share)
        equity_tax = (self.equity_rate * realised_equity_gain
                      if realised_equity_gain > 0 and equity_sold_brl > self.monthly_sale_exemption_brl else 0.0)
        realised_fixed_income_gain = fixed_income_gain_brl * self._share(fixed_income_redeemed_share)
        fixed_income_tax = self.fixed_income_rate * realised_fixed_income_gain if realised_fixed_income_gain > 0 else 0.0
        return equity_tax + fixed_income_tax


def unconstrained_long_only_mvo(returns: pd.DataFrame, gamma: float = 10.0) -> pd.Series:
    """Long-only mean-variance optimum over an eligible universe.

    This is the neutral quantitative comparator: it maximises trailing mean
    return net of variance with no alpha signal, no issuer cap and no asset
    count.  It must never be derived from the candidate rule, otherwise the
    published comparison degenerates into the strategy plotted against itself.
    """
    import cvxpy as cp
    import numpy as np

    clean = returns.dropna(axis=1, how="any")
    if clean.empty or clean.shape[1] == 0:
        return pd.Series(dtype=float)
    if clean.shape[1] == 1:
        return pd.Series(1.0, index=clean.columns)
    mean = clean.mean().to_numpy() * 252
    covariance = clean.cov().to_numpy() * 252 + np.eye(clean.shape[1]) * 1e-5
    weights = cp.Variable(clean.shape[1])
    problem = cp.Problem(cp.Maximize(mean @ weights - gamma / 2 * cp.quad_form(weights, cp.psd_wrap(covariance))),
                         [cp.sum(weights) == 1, weights >= 0])
    problem.solve(solver=cp.CLARABEL)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or weights.value is None:
        raise RuntimeError(f"Neutral MVO comparator did not solve: {problem.status}")
    value = np.maximum(weights.value, 0)
    total = float(value.sum())
    if total <= 0:
        return pd.Series(1.0 / clean.shape[1], index=clean.columns)
    return pd.Series(value / total, index=clean.columns)


def realised_returns_with_delisting(prices: pd.DataFrame, cash_column: str = "TITULO_CDI") -> pd.DataFrame:
    """Daily returns where a delisted position is liquidated into cash.

    Dropping every row that contains a missing quote truncated the holding year
    at the first delisting and silently deleted the rest of the period for the
    whole book.  Forward-filling instead froze the price and reported a zero
    return for a name that had stopped existing.  Both understate the cost of
    holding a company that leaves the exchange.

    The realistic treatment is to sell at the last observable price and hold the
    proceeds in the defensive sleeve until the next annual review.
    """
    returns = prices.pct_change()
    cash = returns[cash_column] if cash_column in returns else pd.Series(0.0, index=returns.index)
    for column in returns.columns:
        if column == cash_column:
            continue
        valid = prices[column].last_valid_index()
        if valid is not None and valid < returns.index[-1]:
            after = returns.index > valid
            returns.loc[after, column] = cash.loc[after]
        first = prices[column].first_valid_index()
        if first is not None:
            returns.loc[returns.index < first, column] = 0.0
    return returns.iloc[1:].fillna(0.0)


def _liquidity_map(screen: pd.DataFrame) -> dict[str, float]:
    """Average daily traded value per ticker, as known at the decision date."""
    if screen.empty or "average_daily_value_brl" not in screen:
        return {}
    frame = screen.set_index("ticker") if "ticker" in screen.columns else screen
    return {str(ticker): float(value) for ticker, value in frame.average_daily_value_brl.items()
            if pd.notna(value) and float(value) > 0}


def _execution_cost_brl(target: pd.Series, previous: pd.Series, wealth: float,
                        liquidity: dict[str, float]) -> float:
    """Cost of moving from the drifted book to the target, priced by liquidity.

    Every rebalance now uses the same published B3 fee plus a participation
    dependent slippage term. A flat basis-point charge understates the cost of
    a thinly traded name, which is exactly where a small-cap tilt looks best.
    """
    costs = ClearB3CostModel()
    total = 0.0
    for ticker in set(target.index) | set(previous.index):
        if ticker == "TITULO_CDI":
            continue
        notional = abs(float(target.get(ticker, 0.0)) - float(previous.get(ticker, 0.0))) * wealth
        if notional <= 0:
            continue
        average_daily_value = liquidity.get(ticker)
        if average_daily_value is None or average_daily_value <= 0:
            # Without an observed traded value the conservative assumption is
            # the strategy's own liquidity floor, never a frictionless trade.
            average_daily_value = 1_000_000.0
        total += costs.estimate(notional, average_daily_value).total_brl
    return total


def _price_column_for_ticker(ticker: str, columns: pd.Index) -> str | None:
    """Resolve the B3/CVM ``.SA`` convention against a price panel safely.

    Dated CVM snapshots commonly retain Yahoo's market suffix (``PETR4.SA``),
    whereas public price exports use the canonical B3 code (``PETR4``).  The
    conversion is deterministic and only used at the integration boundary;
    all decision records retain the original snapshot ticker.
    """
    value = str(ticker).upper().strip()
    candidates = (value, value.removesuffix(".SA"), value + ".SA")
    return next((candidate for candidate in candidates if candidate in columns), None)


@dataclass(frozen=True)
class AnnualWalkForwardConfig:
    start_year: int
    end_year: int
    horizon_years: int = 5
    maximum_equity_weight: float = 0.55
    maximum_asset_weight: float = 0.12
    minimum_history_days: int = 252
    factor: str = "value_quality"
    minimum_factor_training_years: int = 3
    top_assets: int = 4
    minimum_average_daily_value_brl: float = 10_000_000
    risk_profile: str | None = None

    def __post_init__(self) -> None:
        if self.end_year <= self.start_year:
            raise ValueError("end_year must be after start_year so at least one holding period can be evaluated.")
        if not 0 <= self.maximum_equity_weight <= 1:
            raise ValueError("maximum_equity_weight must be between 0 and 1.")
        if not 0 < self.maximum_asset_weight <= 1:
            raise ValueError("maximum_asset_weight must be between 0 (exclusive) and 1.")
        if self.top_assets < 1:
            raise ValueError("top_assets must be at least 1.")
        if self.risk_profile is not None and self.risk_profile not in RISK_PROFILE_LIMITS:
            raise ValueError(f"Unsupported risk profile '{self.risk_profile}'.")


def protocol_for_risk_profile(protocol: AnnualWalkForwardConfig, risk_profile: str | None) -> AnnualWalkForwardConfig:
    """Apply pre-declared investor guardrails without changing the signal."""
    if risk_profile is None:
        return protocol
    limits = RISK_PROFILE_LIMITS[risk_profile]
    return replace(protocol, risk_profile=risk_profile,
                   maximum_equity_weight=float(limits["maximum_equity_weight"]),
                   maximum_asset_weight=float(limits["maximum_asset_weight"]))


def _decision_action(old: float, new: float, tolerance: float = 1e-6) -> str:
    """Name the committee action without referring to a future return."""
    if old <= tolerance < new:
        return "entered"
    if old > tolerance >= new:
        return "exited"
    if old > tolerance and new > old + tolerance:
        return "increased"
    if old > tolerance and new < old - tolerance:
        return "reduced"
    if new > tolerance:
        return "maintained"
    return "not_held"


def apply_annual_taxes(results: pd.DataFrame, tax_model: BrazilianTaxModel) -> pd.DataFrame:
    """Charge Brazilian tax to the year whose gain the next review realises.

    A gain is only taxable once the position is sold, so the fraction realised
    for year *t* is the share of the book that the review at the start of year
    *t + 1* actually turns over.  The last evaluated year is charged as a full
    liquidation, which is the conservative terminal assumption rather than an
    indefinite deferral that would flatter the series.
    """
    frame = results.copy()
    for label, gain_column, cash_column, turnover_column, net_column in (
        ("", "equity_gain_rate", "cash_weight", "turnover", "net_return"),
        ("mvo_", "mvo_equity_gain_rate", "mvo_cash_weight", "mvo_turnover", "mvo_eligible_net_return"),
    ):
        if gain_column not in frame:
            continue
        # Turnover counts the buy and the sell leg, so half of it is the share
        # of the book that was actually sold.
        realised = (frame[turnover_column].shift(-1) / 2).clip(upper=1.0)
        realised = realised.fillna(1.0)
        equity_tax = tax_model.equity_rate * frame[gain_column].clip(lower=0) * realised
        cash_gain = frame[cash_column] * frame.cdi_net_return
        cash_tax = tax_model.fixed_income_rate * cash_gain.clip(lower=0) * realised
        frame[f"{label}realised_share_for_tax"] = realised
        frame[f"{label}tax_rate"] = equity_tax + cash_tax
        frame[f"{label}net_return_after_tax"] = frame[net_column] - (equity_tax + cash_tax)
    frame["cdi_net_return_after_tax"] = frame.cdi_net_return - tax_model.fixed_income_rate * frame.cdi_net_return.clip(lower=0)
    return frame


def _annual_benchmark_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Report a stress-test comparison, never a prediction or approval."""
    columns = {
        "Benevente Quant AI": "net_return",
        "Benevente Quant AI (após IR)": "net_return_after_tax",
        "MVO elegível": "mvo_eligible_net_return",
        "MVO elegível (após IR)": "mvo_net_return_after_tax",
        "CDI": "cdi_net_return",
        "CDI (após IR)": "cdi_net_return_after_tax",
    }
    columns.update({f"Referência {name.removeprefix('benchmark_')}": name
                    for name in results.columns if str(name).startswith("benchmark_")})
    columns = {name: column for name, column in columns.items() if column in results.columns}
    rows: list[dict] = []
    for name, column in columns.items():
        series = results[column].dropna()
        wealth = (1 + series).cumprod()
        years = max(len(series), 1)
        rows.append({
            "strategy": name,
            "annual_observations": len(series),
            "cumulative_return": float(wealth.iloc[-1] - 1),
            "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
            "annual_volatility": float(series.std(ddof=1)),
            "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
        })
    benevente = results.net_return
    comparisons = [("CDI", "cdi_net_return"), ("MVO elegível", "mvo_eligible_net_return")]
    comparisons.extend((f"Referência {str(name).removeprefix('benchmark_')}", str(name))
                       for name in results.columns if str(name).startswith("benchmark_"))
    for benchmark, column in comparisons:
        comparison = pd.concat([benevente, results[column]], axis=1).dropna()
        comparison.columns = ["benevente", "benchmark"]
        excess = comparison.benevente - comparison.benchmark
        relative_wealth = (1 + comparison.benevente).cumprod() / (1 + comparison.benchmark).cumprod()
        rows.append({
            "strategy": f"Benevente excess vs {benchmark}",
            "annual_observations": len(excess),
            "cumulative_return": float(relative_wealth.iloc[-1] - 1),
            "cagr": float(relative_wealth.iloc[-1] ** (1 / max(len(relative_wealth), 1)) - 1),
            "annual_volatility": float(excess.std(ddof=1)),
            "max_drawdown": float(relative_wealth.div(relative_wealth.cummax()).sub(1).min()),
            "positive_year_hit_rate": float((excess > 0).mean()),
        })
    return pd.DataFrame(rows)


def _first_trading_day(prices: pd.DataFrame, year: int) -> pd.Timestamp | None:
    rows = prices.loc[(prices.index >= pd.Timestamp(year=year, month=1, day=1)) &
                      (prices.index < pd.Timestamp(year=year + 1, month=1, day=1))]
    return None if rows.empty else pd.Timestamp(rows.index[0])


def _format_weights(weights: pd.Series) -> str:
    entries = [f"{ticker}:{weight:.2%}" for ticker, weight in weights.items() if weight > 1e-6]
    return " | ".join(entries)


def _recent_market_sessions(prices: pd.DataFrame, decision: pd.Timestamp,
                            minimum_history_days: int) -> pd.DatetimeIndex:
    """Identify recent B3 sessions from broad panel coverage, not calendar days.

    Yahoo emits rows for Brazilian holidays when a minority of instruments
    traded (or their calendar differs). Requiring every asset to have a quote
    on every one of those rows would reject liquid issuers such as PETR4.  A
    session is therefore a date with at least 80% of the panel's peak equity
    coverage. Individual names must still have a real quote on all selected
    sessions; nothing is forward-filled.
    """
    prior = prices.loc[prices.index < decision].drop(columns="TITULO_CDI", errors="ignore")
    coverage = prior.notna().sum(axis=1)
    if coverage.empty:
        return pd.DatetimeIndex([])
    threshold = max(1, int(coverage.max() * .80))
    sessions = coverage.index[coverage >= threshold]
    return pd.DatetimeIndex(sessions[-(minimum_history_days + 1):])


class AnnualWalkForwardEngine:
    """Freeze, hold, review: a portfolio process a committee can audit."""
    def __init__(self, prices: pd.DataFrame, snapshots: list[FundamentalSnapshot], config: SystemConfig,
                 decision_evidence: DecisionEvidence | None = None,
                 benchmarks: pd.DataFrame | None = None,
                 tax_model: BrazilianTaxModel | None = None) -> None:
        self.prices = prices.copy().sort_index()
        self.prices.index = pd.to_datetime(self.prices.index)
        self.snapshots = snapshots
        self.config = config
        self.decision_evidence = decision_evidence
        self.tax_model = tax_model or BrazilianTaxModel()
        self.daily_curve = pd.DataFrame()
        # External market references (Ibovespa, an index ETF) are evaluated on
        # the same decision dates so the comparison never mixes windows.
        self.benchmarks = None
        if benchmarks is not None and not benchmarks.empty:
            self.benchmarks = benchmarks.copy().sort_index()
            self.benchmarks.index = pd.to_datetime(self.benchmarks.index)
        if "TITULO_CDI" not in self.prices:
            raise ValueError("Annual walk-forward requires TITULO_CDI in the price history.")

    def _daily_path(self, realised_returns: pd.DataFrame, target: pd.Series, mvo_target: pd.Series,
                    cost_rate: float, mvo_cost_rate: float, decision: pd.Timestamp, next_decision: pd.Timestamp,
                    level: dict[str, float], benchmark_levels: dict[str, float]) -> list[dict]:
        """Exact daily value of a book that is bought in January and held.

        Weights are fixed for the year, so compounding each asset separately and
        summing the weighted paths reproduces the buy-and-hold value on every
        session. Rebalancing cost is charged on the first day, which is when the
        trades happen.
        """
        growth = (1 + realised_returns).cumprod()
        rows: list[dict] = []

        def sleeve(weights: pd.Series, charge: float) -> pd.Series:
            aligned = weights.reindex(growth.columns).fillna(0.0)
            return growth.mul(aligned, axis=1).sum(axis=1) - charge

        strategy_path = sleeve(target, cost_rate)
        mvo_path = sleeve(mvo_target, mvo_cost_rate)
        cdi_path = growth["TITULO_CDI"] if "TITULO_CDI" in growth else pd.Series(1.0, index=growth.index)
        # The equity sleeve on its own, renormalised to a full allocation. A
        # study of how much to hold in equities needs the return of holding
        # only equities, not the blended book.
        equity_weights = target.drop(labels="TITULO_CDI", errors="ignore")
        equity_total = float(equity_weights.sum())
        equity_path = (sleeve(equity_weights / equity_total, 0.0) if equity_total > 0
                       else pd.Series(1.0, index=growth.index))
        level.setdefault("equity_sleeve", 100.0)
        opening = dict(level)
        window = None
        if self.benchmarks is not None:
            window = self.benchmarks.loc[(self.benchmarks.index >= decision) & (self.benchmarks.index < next_decision)]
        for date in growth.index:
            row = {
                "date": date.date().isoformat(),
                "decision_year": int(decision.year),
                "strategy": round(opening["strategy"] * float(strategy_path.loc[date]), 6),
                "mvo": round(opening["mvo"] * float(mvo_path.loc[date]), 6),
                "cdi": round(opening["cdi"] * float(cdi_path.loc[date]), 6),
                "equity_sleeve": round(opening["equity_sleeve"] * float(equity_path.loc[date]), 6),
            }
            if window is not None and not window.empty:
                for column in window.columns:
                    series = window[column].dropna()
                    if series.empty or date not in series.index:
                        continue
                    opening_level = benchmark_levels.setdefault(str(column), 100.0)
                    row[str(column)] = round(opening_level * float(series.loc[date] / series.iloc[0]), 6)
            rows.append(row)
        if rows:
            for key in ("strategy", "mvo", "cdi", "equity_sleeve"):
                level[key] = rows[-1][key]
            for key in list(benchmark_levels):
                if key in rows[-1]:
                    benchmark_levels[key] = rows[-1][key]
        return rows

    def _benchmark_returns(self, decision: pd.Timestamp, next_decision: pd.Timestamp) -> dict[str, float]:
        """Holding-period return of each external reference, same window."""
        if self.benchmarks is None:
            return {}
        window = self.benchmarks.loc[(self.benchmarks.index >= decision) & (self.benchmarks.index < next_decision)]
        result: dict[str, float] = {}
        for column in window.columns:
            series = window[column].dropna()
            if len(series) >= 2 and float(series.iloc[0]) > 0:
                result[str(column)] = float(series.iloc[-1] / series.iloc[0] - 1)
        return result

    @staticmethod
    def factor_scores(history: pd.DataFrame, factor: str) -> dict[str, float] | None:
        """Pre-declared, explainable factor candidates for factor selection.

        These scores are known at the annual decision date. ``None`` retains
        the fundamental value/quality ranking. No realized holding-period
        return enters this function.
        """
        if factor in {"value_quality", "triple_factor", "mvo_neutral", "mvo_low_volatility", "mvo_risk_adjusted"}:
            return None
        equities = [ticker for ticker in history.columns if ticker != "TITULO_CDI"]
        if not equities:
            return None
        if factor == "momentum_12m":
            period = history.tail(252)
            raw = (1 + period[equities]).prod() - 1
        elif factor == "low_volatility":
            raw = -history.tail(252)[equities].std(ddof=1)
        else:
            raise ValueError(f"Unsupported factor '{factor}'.")
        ranks = raw.rank(pct=True)
        return {ticker: float(2 * rank - 1) for ticker, rank in ranks.items()}

    @staticmethod
    def _zscore(series: pd.Series) -> pd.Series:
        """Cross-sectional z-score with deterministic zero-variance handling."""
        deviation = float(series.std(ddof=0))
        return pd.Series(0.0, index=series.index) if deviation == 0 else (series - series.mean()) / deviation

    def triple_factor_screen(self, snapshots: list[FundamentalSnapshot], history: pd.DataFrame,
                              decision: pd.Timestamp, protocol: AnnualWalkForwardConfig) -> pd.DataFrame:
        """Pre-registered quality + value + 12-month momentum screen.

        This deliberately requires only the primary quality signal (ROIC for
        operating companies and ROE for financials), positive earnings and
        minimum liquidity.  A missing debt/interest field is reported but is
        *not* treated as evidence of distress; that was the source of the
        baseline's accidental financial-sector concentration.  No later price
        or filing is read here.
        """
        from fundamentals import snapshots_available_on

        current = snapshots_available_on(snapshots, decision)
        rows: list[dict] = []
        for ticker, item in current.items():
            reasons: list[str] = []
            if ticker not in history.columns:
                reasons.append("missing_price_history")
            if item.average_daily_value_brl < protocol.minimum_average_daily_value_brl:
                reasons.append("minimum_liquidity")
            quality = item.roe if item.is_financial else item.roic
            if quality is None or quality < (self.config.min_roe if item.is_financial else self.config.min_roic):
                reasons.append("primary_quality")
            if item.price_to_earnings is None or item.price_to_earnings <= 0:
                reasons.append("positive_earnings")
            row = {**item.model_dump(), "eligible": not reasons, "rejection_reasons": ",".join(reasons),
                   "quality_signal": quality, "earnings_yield": None if item.price_to_earnings is None else 1 / item.price_to_earnings,
                   "momentum_12m": None, "factor_score": 0.0, "value_quality_score": 0.0, "selection_rank": None}
            if ticker in history.columns and len(history):
                row["momentum_12m"] = float((1 + history[ticker].tail(protocol.minimum_history_days)).prod() - 1)
            rows.append(row)
        screen = pd.DataFrame(rows)
        eligible = screen[screen.eligible].copy()
        if eligible.empty:
            return screen
        eligible["factor_score"] = (
            .40 * self._zscore(eligible.quality_signal) +
            .40 * self._zscore(eligible.earnings_yield) +
            .20 * self._zscore(eligible.momentum_12m)
        )
        eligible = eligible.sort_values(["factor_score", "ticker"], ascending=[False, True])
        eligible["selection_rank"] = range(1, len(eligible) + 1)
        # Preserve the established output column while making its meaning
        # explicit in the factor column and protocol.json.
        eligible["value_quality_score"] = eligible.factor_score.rank(pct=True)
        return screen.merge(eligible[["ticker", "factor_score", "value_quality_score", "selection_rank"]], on="ticker", how="left", suffixes=("", "_scored")).assign(
            factor_score=lambda frame: frame.factor_score_scored.fillna(frame.factor_score),
            value_quality_score=lambda frame: frame.value_quality_score_scored.fillna(frame.value_quality_score),
            selection_rank=lambda frame: frame.selection_rank_scored.fillna(frame.selection_rank),
        ).drop(columns=["factor_score_scored", "value_quality_score_scored", "selection_rank_scored"])

    @staticmethod
    def _confidence_weights(scores: pd.Series, total_equity: float, maximum_asset_weight: float) -> pd.Series:
        """Allocate by factor confidence while respecting every issuer cap."""
        if scores.empty or total_equity <= 0:
            return pd.Series(dtype=float)
        raw = scores - scores.min() + .25
        weights = raw / raw.sum() * total_equity
        # Water-fill any cap excess among the remaining names; a cap is never
        # relaxed merely to reach the requested equity allocation.
        for _ in range(len(weights) + 1):
            capped = weights >= maximum_asset_weight - 1e-12
            excess = float(weights[capped].sum() - maximum_asset_weight * capped.sum())
            weights.loc[capped] = maximum_asset_weight
            available = ~capped
            if excess <= 1e-12 or not available.any():
                break
            weights.loc[available] += excess * (raw[available] / raw[available].sum())
        return weights.clip(upper=maximum_asset_weight)

    def triple_factor_proposal(self, history: pd.DataFrame, snapshots: list[FundamentalSnapshot], decision: pd.Timestamp,
                               current_weights: pd.Series, protocol: AnnualWalkForwardConfig, wealth: float,
                               issuer_ids: dict[str, str] | None = None) -> PortfolioProposal:
        screen = self.triple_factor_screen(snapshots, history, decision, protocol)
        eligible = screen[screen.eligible].copy()
        # Multiple share classes are one economic exposure.  Select the
        # highest-ranked liquid class, rather than reporting artificial
        # diversification through two tickers of the same issuer.
        eligible["issuer_id"] = eligible.ticker.map(issuer_ids or {}).fillna(eligible.ticker)
        selected = (eligible.sort_values(["factor_score", "average_daily_value_brl", "ticker"], ascending=[False, False, True])
                    .drop_duplicates("issuer_id", keep="first")
                    .head(protocol.top_assets))
        if selected.empty:
            raise ValueError("No eligible assets under the triple-factor point-in-time screen.")
        attainable_equity = min(protocol.maximum_equity_weight, protocol.maximum_asset_weight * len(selected))
        selected_weights = self._confidence_weights(selected.set_index("ticker").factor_score, attainable_equity, protocol.maximum_asset_weight)
        weights = pd.Series(0.0, index=history.columns)
        weights.loc[selected_weights.index] = selected_weights
        weights["TITULO_CDI"] = 1 - float(weights.drop(labels="TITULO_CDI").sum())
        liquidity = selected.set_index("ticker").average_daily_value_brl.to_dict()
        costs = ClearB3CostModel()
        estimated_cost = sum(
            costs.estimate(wealth * abs(weights[ticker] - current_weights.get(ticker, 0.0)), liquidity[ticker]).total_brl
            for ticker in selected_weights.index
        )
        return PortfolioProposal(decision, protocol.horizon_years, weights, screen, estimated_cost)

    def run(self, protocol: AnnualWalkForwardConfig,
            factors_by_year: dict[int, str] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        wealth = float(self.config.initial_portfolio_value_brl)
        previous = pd.Series(0.0, index=self.prices.columns)
        mvo_previous = pd.Series(0.0, index=self.prices.columns)
        previous_screen: pd.DataFrame | None = None
        # A chart built from eleven January points cannot show a drawdown, a
        # recovery or when a year actually turned. The book is held fixed
        # inside each year, so the daily path is exact rather than interpolated.
        daily_rows: list[dict] = []
        daily_level = {"strategy": 100.0, "mvo": 100.0, "cdi": 100.0}
        benchmark_levels: dict[str, float] = {}
        yearly_rows: list[dict] = []
        transition_rows: list[dict] = []
        holding_rows: list[dict] = []

        for year in range(protocol.start_year, protocol.end_year):
            decision_factor = (factors_by_year or {}).get(year, protocol.factor)
            decision = _first_trading_day(self.prices, year)
            # A Jan-2025 decision can be evaluated through the last available
            # 2025 session even when the local total-return panel stops before
            # Jan-2026.  This preserves the no-look-ahead decision while
            # clearly marking the close as an observed-data cutoff.
            if decision is None:
                continue
            next_decision = _first_trading_day(self.prices, year + 1)
            if next_decision is None:
                observed = self.prices.index[self.prices.index >= decision]
                if observed.empty:
                    continue
                # Keep the public record semantically clear: the field is
                # exclusive, therefore it is the calendar day after the last
                # observed market session.
                next_decision = pd.Timestamp(observed[-1]).normalize() + pd.Timedelta(days=1)
            # A historical panel has one fundamental snapshot per ticker per
            # annual decision. The decision may see several older filings, but
            # only the newest filing actually available at that date may enter
            # the screen; retaining all older records duplicates a ticker and
            # can accidentally turn its price history into a DataFrame.
            from fundamentals import snapshots_available_on
            known_snapshots = list(snapshots_available_on(self.snapshots, decision).values())
            if self.decision_evidence is not None:
                permitted = self.decision_evidence.allowed(decision)
                known_snapshots = [item for item in known_snapshots if item.ticker in permitted]
            if not known_snapshots:
                # Do not infer a fundamental screen from a future filing. This
                # year is omitted and the final no-decision error makes the
                # missing evidence visible to the caller.
                continue
            # A full B3 panel contains listings, delistings and infrequently
            # traded shares. Evaluate only the dated candidates that have a
            # complete trailing price window; do not forward-fill a gap or
            # discard every other asset because one ticker is unavailable.
            prior_prices = self.prices.loc[self.prices.index < decision]
            ticker_columns = {item.ticker: _price_column_for_ticker(item.ticker, prior_prices.columns)
                              for item in known_snapshots}
            recent_sessions = _recent_market_sessions(self.prices, decision, protocol.minimum_history_days)
            if len(recent_sessions) < protocol.minimum_history_days + 1:
                continue
            complete_tickers = [ticker for ticker, column in ticker_columns.items()
                                if column is not None and prior_prices.loc[recent_sessions, column].notna().all()]
            known_snapshots = [item for item in known_snapshots if item.ticker in complete_tickers]
            if not known_snapshots:
                continue
            # Rename only the local history slice to the dated fundamental
            # identifiers. This prevents price-source syntax from changing the
            # selection universe or the audit trail.
            history_source_columns = [ticker_columns[ticker] for ticker in complete_tickers]
            history = prior_prices.loc[recent_sessions, [*history_source_columns, "TITULO_CDI"]].rename(
                columns={ticker_columns[ticker]: ticker for ticker in complete_tickers}
            ).pct_change().dropna()
            if len(history) < protocol.minimum_history_days:
                continue
            # The selector itself rejects snapshots filed after the decision.
            planner_config = replace(self.config, initial_portfolio_value_brl=wealth,
                                     rolling_window_days=protocol.minimum_history_days,
                                     max_asset_weight=protocol.maximum_asset_weight)
            factor_signal = self.factor_scores(history, decision_factor)
            if decision_factor == "triple_factor":
                proposal = self.triple_factor_proposal(history.tail(protocol.minimum_history_days), known_snapshots,
                                                       decision, previous, protocol, wealth,
                                                       self.decision_evidence.issuer_ids(decision) if self.decision_evidence else None)
            else:
                proposal = ValuePortfolioPlanner(planner_config).propose(
                    history.tail(protocol.minimum_history_days), known_snapshots, decision,
                    current_weights=previous, horizon_years=protocol.horizon_years,
                    maximum_equity_weight=protocol.maximum_equity_weight,
                    maximum_asset_weight=protocol.maximum_asset_weight,
                    scores_override=factor_signal,
                )
            active_columns = list(history.columns)
            target = proposal.weights.reindex(active_columns, fill_value=0.0)
            # The canonical MVO rule selects five unique issuers solely by
            # trailing expected return, then optimises their weights with no
            # predictive alpha. It is deliberately isolated from the legacy
            # comparator so other historical protocols remain reproducible.
            eligible = set(proposal.screen.loc[proposal.screen.eligible, "ticker"])
            neutral_scores = {ticker: 0.0 for ticker in history.columns}
            neutral_scores["TITULO_CDI"] = 1.0
            if decision_factor.startswith("mvo_"):
                issuer_ids = self.decision_evidence.issuer_ids(decision) if self.decision_evidence else {}
                mvo_history = history.loc[:, [ticker for ticker in active_columns if ticker in eligible]]
                expected_returns = mvo_history.mean() * 252
                volatility = mvo_history.std(ddof=1).replace(0, pd.NA) * (252 ** .5)

                def select_five_unique_issuers(signal: pd.Series) -> list[str]:
                    ranked = signal.fillna(float("-inf")).sort_values(ascending=False)
                    selected: list[str] = []
                    selected_issuers: set[str] = set()
                    for ticker in ranked.index:
                        issuer = issuer_ids.get(ticker, ticker)
                        if issuer not in selected_issuers:
                            selected.append(ticker)
                            selected_issuers.add(issuer)
                        if len(selected) == 5:
                            break
                    return selected

                if decision_factor == "mvo_low_volatility":
                    candidate_signal = -volatility
                elif decision_factor == "mvo_risk_adjusted":
                    candidate_signal = expected_returns / volatility
                else:
                    candidate_signal = expected_returns
                candidate_selected = select_five_unique_issuers(candidate_signal)
                if len(candidate_selected) < 5:
                    continue
                candidate_columns = [*candidate_selected, "TITULO_CDI"]
                target = MeanVarianceOptimizer(planner_config).optimize(
                    history.loc[:, candidate_columns].tail(protocol.minimum_history_days),
                    {ticker: neutral_scores[ticker] for ticker in candidate_columns},
                    equity_cap=protocol.maximum_equity_weight, signal_influence=0.0,
                    eligible_assets=set(candidate_selected), previous_weights=previous,
                    minimum_selected_weight=.02,
                ).reindex(active_columns, fill_value=0.0)
                proposal = replace(proposal, weights=target)
            # The neutral comparator is built from the eligible universe by an
            # unconstrained long-only mean-variance optimisation. It shares no
            # step with the candidate rule, so an ``mvo_`` candidate can no
            # longer end up compared against a copy of itself.
            mvo_universe = [ticker for ticker in active_columns if ticker in eligible or ticker == "TITULO_CDI"]
            neutral_weights = unconstrained_long_only_mvo(
                history.loc[:, mvo_universe].tail(protocol.minimum_history_days),
                gamma=self.config.risk_aversion_gamma * 4,
            )
            if neutral_weights.empty:
                continue
            mvo_target = neutral_weights.reindex(active_columns, fill_value=0.0)
            realised_slice = self.prices.loc[
                (self.prices.index >= decision) & (self.prices.index < next_decision),
                [*history_source_columns, "TITULO_CDI"],
            ]
            realised_coverage = realised_slice.drop(columns="TITULO_CDI").notna().sum(axis=1)
            realised_threshold = max(1, int(realised_coverage.max() * .80)) if not realised_coverage.empty else 1
            realised_prices = realised_slice.loc[realised_coverage >= realised_threshold].rename(
                columns={ticker_columns[ticker]: ticker for ticker in complete_tickers}
            )
            if len(realised_prices) < 2:
                continue
            realised_returns = realised_returns_with_delisting(realised_prices)
            if realised_returns.empty:
                continue
            # Buy and hold. Compounding ``returns @ weights`` daily would
            # silently rebalance the book to fixed weights every session, free
            # of cost, which is not the annual protocol being evaluated.
            asset_growth = (1 + realised_returns).prod()
            gross_return = float((target * asset_growth.reindex(target.index).fillna(1.0)).sum() - 1)
            liquidity = _liquidity_map(proposal.screen)
            cost_brl = _execution_cost_brl(target, previous, wealth, liquidity)
            cost_rate = cost_brl / wealth if wealth else 0.0
            net_return = gross_return - cost_rate
            mvo_gross_return = float((mvo_target * asset_growth.reindex(mvo_target.index).fillna(1.0)).sum() - 1)
            mvo_cost_rate = _execution_cost_brl(mvo_target, mvo_previous, wealth, liquidity) / wealth if wealth else 0.0
            mvo_net_return = mvo_gross_return - mvo_cost_rate
            cdi_net_return = float(asset_growth.get("TITULO_CDI", 1.0) - 1)
            closing_wealth = wealth * (1 + net_return)
            turnover = float((target - previous).abs().sum())
            benchmark_returns = self._benchmark_returns(decision, next_decision)
            daily_rows.extend(self._daily_path(realised_returns, target, mvo_target, cost_rate, mvo_cost_rate,
                                               decision, next_decision, daily_level, benchmark_levels))
            equity_weight = float(target.drop(labels="TITULO_CDI").sum())
            equity_growth = target.drop(labels="TITULO_CDI") * asset_growth.reindex(target.index).drop(labels="TITULO_CDI").fillna(1.0)
            equity_gain_rate = float(equity_growth.sum()) - equity_weight
            mvo_equity_weight = float(mvo_target.drop(labels="TITULO_CDI").sum())
            mvo_equity_gain_rate = float((mvo_target.drop(labels="TITULO_CDI") *
                                          asset_growth.reindex(mvo_target.index).drop(labels="TITULO_CDI").fillna(1.0)).sum()) - mvo_equity_weight
            screen = proposal.screen.set_index("ticker")
            yearly_rows.append({
                "decision_year": year, "decision_date": decision.date().isoformat(),
                "holding_end_exclusive": next_decision.date().isoformat(), "gross_return": gross_return,
                "estimated_cost_brl": proposal.estimated_rebalance_cost_brl, "estimated_cost_rate": cost_rate,
                "net_return": net_return, "opening_wealth_brl": wealth, "closing_wealth_brl": closing_wealth,
                "turnover": turnover, "weights_at_decision": _format_weights(target),
                "known_snapshot_count": len(known_snapshots),
                "factor": decision_factor, "target_equity_weight": equity_weight,
                "mvo_eligible_net_return": mvo_net_return,
                "mvo_turnover": float((mvo_target - mvo_previous).abs().sum()),
                "mvo_equity_gain_rate": mvo_equity_gain_rate,
                "mvo_cash_weight": float(mvo_target.get("TITULO_CDI", 0.0)),
                "equity_gain_rate": equity_gain_rate,
                "cash_weight": float(target.get("TITULO_CDI", 0.0)),
                "cdi_net_return": cdi_net_return,
                "eligible_universe_size": len(eligible),
                "priced_universe_size": len(complete_tickers),
                **{f"benchmark_{name}": value for name, value in benchmark_returns.items()},
            })
            for ticker in active_columns:
                old, new = float(previous.get(ticker, 0.0)), float(target.get(ticker, 0.0))
                if abs(old - new) <= 1e-6:
                    continue
                if ticker == "TITULO_CDI":
                    reason = "defensive_residual_adjustment"
                elif ticker not in screen.index or not bool(screen.loc[ticker, "eligible"]):
                    reason = "removed_or_blocked_by_eligibility"
                elif old <= 1e-6:
                    reason = "entered_after_point_in_time_screen"
                elif new <= 1e-6:
                    reason = "removed_by_constrained_allocator"
                else:
                    reason = "rebalanced_after_point_in_time_review"
                transition_rows.append({"decision_year": year, "decision_date": decision.date().isoformat(),
                                        "ticker": ticker, "previous_weight": old, "new_weight": new, "reason": reason,
                                        "decision_action": _decision_action(old, new),
                                        "factor": decision_factor})
            for ticker, weight in target.items():
                if weight > 1e-6:
                    item = screen.loc[ticker] if ticker in screen.index else None
                    old_weight = float(previous.get(ticker, 0.0))
                    if ticker == "TITULO_CDI":
                        rationale = "Defensive residual after equity, issuer and eligibility constraints."
                        score = None
                        eligible_status = True
                    else:
                        score = float(item.value_quality_score)
                        eligible_status = bool(item.eligible)
                        twelve_month_return = float((1 + history[ticker].tail(252)).prod() - 1)
                        trailing_volatility = float(history[ticker].tail(252).std(ddof=1) * (252 ** .5))
                        selected_signal = None if factor_signal is None else factor_signal.get(ticker)
                        rationale = (
                            "Maintained because it remained eligible under the point-in-time screen and its constrained allocation remained positive."
                            if old_weight > 1e-6 else
                            "Entered because it passed the point-in-time screen and the constrained allocator assigned weight."
                        )
                    if ticker == "TITULO_CDI":
                        twelve_month_return = trailing_volatility = selected_signal = None
                    holding_rows.append({"decision_year": year, "decision_date": decision.date().isoformat(),
                                         "ticker": ticker, "weight": weight,
                                         "previous_weight": old_weight,
                                         "decision_action": _decision_action(old_weight, float(weight)),
                                         "factor": decision_factor,
                                         "value_quality_score": score,
                                         "factor_signal_at_decision": selected_signal,
                                         "trailing_12m_return_at_decision": twelve_month_return,
                                         "trailing_12m_volatility_at_decision": trailing_volatility,
                                         "eligible_at_decision": eligible_status,
                                         "fundamental_status": "CDI residual" if ticker == "TITULO_CDI" else "eligible_on_decision_date",
                                         "decision_rationale": rationale,
                                         "realised_next_year_return": float((1 + realised_returns[ticker]).prod() - 1)})
            # At the following January, turnover is computed from the weights
            # that actually drifted during the holding year, not the stale
            # target weights chosen a year before.
            previous = (target * asset_growth).div(float((target * asset_growth).sum()))
            mvo_previous = (mvo_target * asset_growth).div(float((mvo_target * asset_growth).sum()))
            previous_screen, wealth = screen, closing_wealth
        results = pd.DataFrame(yearly_rows)
        if results.empty:
            raise ValueError("No annual decisions were produced. Supply at least 252 prior prices and snapshots available before each review date.")
        results = apply_annual_taxes(results, self.tax_model)
        # Kept on the engine rather than returned so the three-tuple contract
        # every existing caller relies on stays unchanged.
        self.daily_curve = pd.DataFrame(daily_rows)
        return results, pd.DataFrame(transition_rows), pd.DataFrame(holding_rows)


def select_factor_out_of_sample(engine: AnnualWalkForwardEngine, base: AnnualWalkForwardConfig,
                                training_end_year: int, factors: tuple[str, ...] = ("value_quality", "momentum_12m", "low_volatility")) -> tuple[str, pd.DataFrame]:
    """Choose one pre-declared factor only on the training years.

    The caller must then run the returned factor on years after
    ``training_end_year``. This makes the comparison a genuine holdout instead
    of an annual search for whichever factor won after the fact.
    """
    if training_end_year <= base.start_year or training_end_year >= base.end_year:
        raise ValueError("training_end_year must fall inside the annual protocol range.")
    rows: list[dict] = []
    for factor in factors:
        train, _, _ = engine.run(replace(base, end_year=training_end_year, factor=factor))
        wealth_path = (1 + train.net_return).cumprod()
        wealth = float(wealth_path.iloc[-1])
        drawdown = float((wealth_path / wealth_path.cummax() - 1).min())
        turnover = float(train.turnover.mean())
        # Pre-declared selection statistic: net cumulative return penalised by
        # annual drawdown and turnover. It is intentionally not a search for
        # the factor with the single highest historical return.
        score = wealth - 1 - .50 * abs(drawdown) - .10 * turnover
        rows.append({"factor": factor, "training_years": len(train), "training_cumulative_return": wealth - 1,
                     "training_max_drawdown": drawdown, "training_average_turnover": turnover,
                     "training_selection_score": score})
    leaderboard = pd.DataFrame(rows).sort_values(["training_selection_score", "training_max_drawdown"], ascending=[False, False]).reset_index(drop=True)
    return str(leaderboard.iloc[0].factor), leaderboard


def run_adaptive_factor_walk_forward(engine: AnnualWalkForwardEngine, base: AnnualWalkForwardConfig,
                                     factors: tuple[str, ...] = ("value_quality", "momentum_12m", "low_volatility")) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Nested annual walk-forward: select on past annual periods, then hold one unseen year.

    For decision year *t*, the factor is selected using only the evaluations
    from ``start_year`` through ``t - 1``. The portfolio for year *t* is then
    frozen and evaluated once. This is the production-like training protocol,
    rather than re-fitting on the final full sample.
    """
    choices: list[dict] = []
    for decision_year in range(base.start_year + base.minimum_factor_training_years, base.end_year):
        selection_end = decision_year
        try:
            # The selector trims its own training run at ``selection_end``.
            # Passing a pre-truncated protocol would make every selection
            # invalid and silently retain the baseline.
            factor, board = select_factor_out_of_sample(engine, base, selection_end, factors)
        except ValueError:
            # If a historical gap makes factor comparison impossible, retain
            # the pre-registered value/quality baseline rather than guessing.
            factor, board = "value_quality", pd.DataFrame()
        choices.append({"decision_year": decision_year, "selected_factor": factor,
                        "selection_end_year_exclusive": selection_end,
                        "training_observations": int(board.iloc[0].training_years) if not board.empty else 0,
                        "selection_status": "selected_from_prior_years" if not board.empty else "baseline_retained_missing_training"})
    if not choices:
        raise ValueError("No adaptive annual decisions were produced. Review dated price and fundamental coverage.")
    # Selection happens with only prior outcomes above.  Evaluation then runs
    # once, continuously, so drifted weights, wealth and transaction costs
    # from each holding year become the starting state of the next one.
    factor_map = {int(row["decision_year"]): str(row["selected_factor"]) for row in choices}
    first_decision = min(factor_map)
    results, transitions, holdings = engine.run(replace(base, start_year=first_decision), factors_by_year=factor_map)
    results = results.loc[results.decision_year.isin(factor_map)].reset_index(drop=True)
    transitions = transitions.loc[transitions.decision_year.isin(factor_map)].reset_index(drop=True)
    holdings = holdings.loc[holdings.decision_year.isin(factor_map)].reset_index(drop=True)
    return results, transitions, holdings, pd.DataFrame(choices)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run annual no-look-ahead Benevente walk-forward evaluation.")
    parser.add_argument("--prices", required=True, help="CSV with date, assets, and TITULO_CDI columns.")
    parser.add_argument("--fundamentals", required=True, help="CSV with FundamentalSnapshot fields and availability dates.")
    parser.add_argument("--universe", help="Dated B3 universe CSV; must be supplied with --mapping to enable the identifier gate.")
    parser.add_argument("--mapping", help="Dated B3/CVM mapping CSV; must be supplied with --universe.")
    parser.add_argument("--price-basis", choices=["total_return", "price_return_only"], default="total_return",
                        help="Only total_return may be used to calculate annual performance.")
    parser.add_argument("--total-return-manifest",
                        help="Required with total_return: source metadata and SHA-256 for the return-index export.")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True, help="First year not held; e.g. 2026 evaluates through 2025.")
    parser.add_argument("--output", default="artifacts/annual_walk_forward")
    parser.add_argument("--factor", choices=["value_quality", "momentum_12m", "low_volatility", "triple_factor", "mvo_neutral", "mvo_low_volatility", "mvo_risk_adjusted"], default="value_quality")
    parser.add_argument("--maximum-equity-weight", type=float, default=.55)
    parser.add_argument("--maximum-asset-weight", type=float, default=.12)
    parser.add_argument("--top-assets", type=int, default=4)
    parser.add_argument("--risk-profile", choices=list(RISK_PROFILE_LIMITS),
                        help="Apply pre-declared investor allocation guardrails; overrides manual equity and issuer caps.")
    parser.add_argument("--benchmarks", help="CSV with date and one column per external market reference index level.")
    parser.add_argument("--training-end-year", type=int, help="Optional factor-selection cutoff; output is then evaluated only after this year.")
    parser.add_argument("--adaptive-factors", action="store_true", help="Select a pre-declared factor from prior years before each next-year decision.")
    parser.add_argument("--factor-family", default="value_quality,momentum_12m,low_volatility",
                        help="Comma-separated candidates the nested selection may choose from. Declare it before "
                             "running; widening it after seeing a result is another trial.")
    args = parser.parse_args()
    if bool(args.universe) != bool(args.mapping):
        parser.error("--universe and --mapping must be supplied together.")
    from advisor import snapshots_from_frame
    if args.price_basis == "total_return" and not args.total_return_manifest:
        parser.error("--total-return-manifest is required with --price-basis total_return.")
    if args.price_basis == "price_return_only" and args.total_return_manifest:
        parser.error("--total-return-manifest cannot accompany --price-basis price_return_only.")
    if args.price_basis == "total_return":
        from total_return_adapter import institutional_performance_verified, load_total_return_export
        price_frame, return_source_manifest = load_total_return_export(args.prices, args.total_return_manifest)
    else:
        price_frame = pd.read_csv(args.prices, parse_dates=["date"])
        return_source_manifest = {}
    fundamental_frame = pd.read_csv(args.fundamentals, parse_dates=["as_of_date", "available_date"])
    input_manifest = validate_annual_inputs(price_frame, fundamental_frame, args.price_basis)
    if not input_manifest.performance_permitted:
        raise ValueError("Annual performance blocked: " + ", ".join(input_manifest.reasons))
    prices = price_frame.set_index("date")
    snapshots = snapshots_from_frame(fundamental_frame)
    evidence = None
    evidence_manifest = None
    if args.universe:
        from annual_decision_evidence import load_decision_evidence
        evidence, evidence_manifest = load_decision_evidence(args.universe, args.mapping)
    protocol = AnnualWalkForwardConfig(args.start_year, args.end_year, factor=args.factor,
                                       maximum_equity_weight=args.maximum_equity_weight,
                                       maximum_asset_weight=args.maximum_asset_weight,
                                       top_assets=args.top_assets)
    protocol = protocol_for_risk_profile(protocol, args.risk_profile)
    benchmarks = None
    if args.benchmarks:
        benchmarks = pd.read_csv(args.benchmarks, parse_dates=["date"]).set_index("date")

    # One engine instance so the daily curve of the final evaluation run is
    # still available after any training passes have overwritten it.
    engine = AnnualWalkForwardEngine(prices, snapshots, SystemConfig(), evidence, benchmarks)

    def build_engine() -> AnnualWalkForwardEngine:
        return engine

    family = tuple(item.strip() for item in args.factor_family.split(",") if item.strip())
    if not family:
        parser.error("--factor-family must name at least one candidate.")
    if args.adaptive_factors:
        results, transitions, holdings, factor_choices = run_adaptive_factor_walk_forward(build_engine(), protocol, family)
        leaderboard = None
    elif args.training_end_year:
        factor, leaderboard = select_factor_out_of_sample(engine=build_engine(), base=protocol,
                                                          training_end_year=args.training_end_year, factors=family)
        protocol = replace(protocol, start_year=args.training_end_year, factor=factor)
        results, transitions, holdings = build_engine().run(protocol)
        factor_choices = None
    else:
        leaderboard = None
        results, transitions, holdings = build_engine().run(protocol)
        factor_choices = None
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "annual_results.csv", index=False)
    transitions.to_csv(output / "annual_transitions.csv", index=False)
    holdings.to_csv(output / "annual_holdings.csv", index=False)
    _annual_benchmark_summary(results).to_csv(output / "annual_benchmark_summary.csv", index=False)
    if not engine.daily_curve.empty:
        daily = engine.daily_curve
        daily = daily[daily.decision_year.isin(results.decision_year)]
        daily.to_csv(output / "daily_curve.csv", index=False)
    input_manifest_payload = input_manifest.as_dict()
    input_manifest_payload["total_return_source_tier"] = return_source_manifest.get("source_tier", "unclassified")
    input_manifest_payload["institutional_performance_verified"] = (
        institutional_performance_verified(return_source_manifest) if args.price_basis == "total_return" else False
    )
    (output / "input_manifest.json").write_text(json.dumps(input_manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    if evidence_manifest is not None:
        evidence_manifest.to_csv(output / "decision_evidence_manifest.csv", index=False)
    if leaderboard is not None:
        leaderboard.to_csv(output / "factor_training_leaderboard.csv", index=False)
    if factor_choices is not None:
        factor_choices.to_csv(output / "adaptive_factor_choices.csv", index=False)
    protocol_payload = asdict(protocol)
    if args.adaptive_factors:
        # The published protocol has to name the whole candidate set, not only
        # the factor that happened to win. A reader cannot judge a selection
        # without knowing how many options it ranged over.
        protocol_payload["factor"] = "nested_annual_selection"
        protocol_payload["factor_family"] = list(family)
        protocol_payload["selection_rule"] = (
            "For decision year t the factor is ranked on years start_year..t-1 only, by net cumulative return "
            "penalised by drawdown and turnover. Year t is then evaluated once. No year informs its own selection."
        )
    (output / "protocol.json").write_text(json.dumps(protocol_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(results.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
