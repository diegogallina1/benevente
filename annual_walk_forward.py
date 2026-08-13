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
    "arrojado": {"maximum_equity_weight": .80, "maximum_asset_weight": .15, "review_frequency": "semestral"},
}


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


def _annual_benchmark_summary(results: pd.DataFrame) -> pd.DataFrame:
    """Report a stress-test comparison, never a prediction or approval."""
    columns = {
        "Benevente Quant AI": "net_return",
        "MVO elegível": "mvo_eligible_net_return",
        "CDI": "cdi_net_return",
    }
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
    for benchmark, column in (("CDI", "cdi_net_return"), ("MVO elegível", "mvo_eligible_net_return")):
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
                 decision_evidence: DecisionEvidence | None = None) -> None:
        self.prices = prices.copy().sort_index()
        self.prices.index = pd.to_datetime(self.prices.index)
        self.snapshots = snapshots
        self.config = config
        self.decision_evidence = decision_evidence
        if "TITULO_CDI" not in self.prices:
            raise ValueError("Annual walk-forward requires TITULO_CDI in the price history.")

    @staticmethod
    def factor_scores(history: pd.DataFrame, factor: str) -> dict[str, float] | None:
        """Pre-declared, explainable factor candidates for factor selection.

        These scores are known at the annual decision date. ``None`` retains
        the fundamental value/quality ranking. No realized holding-period
        return enters this function.
        """
        if factor in {"value_quality", "triple_factor"}:
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
                               current_weights: pd.Series, protocol: AnnualWalkForwardConfig, wealth: float) -> PortfolioProposal:
        screen = self.triple_factor_screen(snapshots, history, decision, protocol)
        selected = screen[screen.eligible].sort_values(["factor_score", "ticker"], ascending=[False, True]).head(protocol.top_assets)
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
        yearly_rows: list[dict] = []
        transition_rows: list[dict] = []
        holding_rows: list[dict] = []

        for year in range(protocol.start_year, protocol.end_year):
            decision_factor = (factors_by_year or {}).get(year, protocol.factor)
            decision = _first_trading_day(self.prices, year)
            next_decision = _first_trading_day(self.prices, year + 1)
            if decision is None or next_decision is None:
                continue
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
                                                       decision, previous, protocol, wealth)
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
            # Same historical information and constraints, but no alpha score:
            # a fair annual MVO baseline for the very same eligible universe.
            eligible = set(proposal.screen.loc[proposal.screen.eligible, "ticker"])
            neutral_scores = {ticker: 0.0 for ticker in history.columns}
            neutral_scores["TITULO_CDI"] = 1.0
            # The comparator may only see assets that passed the same dated
            # screen. Restricting the input columns (rather than assigning
            # zero upper bounds to hundreds of ineligible names) also avoids
            # numerical instability in a rank-deficient full-universe
            # covariance matrix.
            mvo_columns = [ticker for ticker in active_columns if ticker == "TITULO_CDI" or ticker in eligible]
            mvo_target = MeanVarianceOptimizer(planner_config).optimize(
                history.loc[:, mvo_columns].tail(protocol.minimum_history_days),
                {ticker: neutral_scores[ticker] for ticker in mvo_columns},
                equity_cap=protocol.maximum_equity_weight, signal_influence=0.0,
                eligible_assets=eligible,
            ).reindex(active_columns, fill_value=0.0)
            realised_slice = self.prices.loc[
                (self.prices.index >= decision) & (self.prices.index < next_decision),
                [*history_source_columns, "TITULO_CDI"],
            ]
            realised_coverage = realised_slice.drop(columns="TITULO_CDI").notna().sum(axis=1)
            realised_threshold = max(1, int(realised_coverage.max() * .80)) if not realised_coverage.empty else 1
            realised_prices = realised_slice.loc[realised_coverage >= realised_threshold].rename(
                columns={ticker_columns[ticker]: ticker for ticker in complete_tickers}
            )
            realised_returns = realised_prices.pct_change().dropna()
            if realised_returns.empty:
                continue
            asset_growth = (1 + realised_returns).prod()
            gross_return = float((1 + realised_returns @ target).prod() - 1)
            cost_rate = proposal.estimated_rebalance_cost_brl / wealth if wealth else 0.0
            net_return = gross_return - cost_rate
            mvo_gross_return = float((1 + realised_returns @ mvo_target).prod() - 1)
            mvo_turnover = float((mvo_target - mvo_previous).abs().sum())
            mvo_net_return = mvo_gross_return - (self.config.transaction_cost + self.config.slippage) * mvo_turnover
            cdi_net_return = float((1 + realised_returns["TITULO_CDI"]).prod() - 1)
            closing_wealth = wealth * (1 + net_return)
            turnover = float((target - previous).abs().sum())
            screen = proposal.screen.set_index("ticker")
            yearly_rows.append({
                "decision_year": year, "decision_date": decision.date().isoformat(),
                "holding_end_exclusive": next_decision.date().isoformat(), "gross_return": gross_return,
                "estimated_cost_brl": proposal.estimated_rebalance_cost_brl, "estimated_cost_rate": cost_rate,
                "net_return": net_return, "opening_wealth_brl": wealth, "closing_wealth_brl": closing_wealth,
                "turnover": turnover, "weights_at_decision": _format_weights(target),
                "known_snapshot_count": len(known_snapshots),
                "factor": decision_factor, "target_equity_weight": float(target.drop(labels="TITULO_CDI").sum()),
                "mvo_eligible_net_return": mvo_net_return,
                "cdi_net_return": cdi_net_return,
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
    parser.add_argument("--factor", choices=["value_quality", "momentum_12m", "low_volatility", "triple_factor"], default="value_quality")
    parser.add_argument("--maximum-equity-weight", type=float, default=.55)
    parser.add_argument("--maximum-asset-weight", type=float, default=.12)
    parser.add_argument("--top-assets", type=int, default=4)
    parser.add_argument("--risk-profile", choices=list(RISK_PROFILE_LIMITS),
                        help="Apply pre-declared investor allocation guardrails; overrides manual equity and issuer caps.")
    parser.add_argument("--training-end-year", type=int, help="Optional factor-selection cutoff; output is then evaluated only after this year.")
    parser.add_argument("--adaptive-factors", action="store_true", help="Select a pre-declared factor from prior years before each next-year decision.")
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
    if args.adaptive_factors:
        results, transitions, holdings, factor_choices = run_adaptive_factor_walk_forward(
            AnnualWalkForwardEngine(prices, snapshots, SystemConfig(), evidence), protocol)
        leaderboard = None
    elif args.training_end_year:
        factor, leaderboard = select_factor_out_of_sample(engine=AnnualWalkForwardEngine(prices, snapshots, SystemConfig(), evidence),
                                                           base=protocol, training_end_year=args.training_end_year)
        protocol = replace(protocol, start_year=args.training_end_year, factor=factor)
        results, transitions, holdings = AnnualWalkForwardEngine(prices, snapshots, SystemConfig(), evidence).run(protocol)
        factor_choices = None
    else:
        leaderboard = None
        results, transitions, holdings = AnnualWalkForwardEngine(prices, snapshots, SystemConfig(), evidence).run(protocol)
        factor_choices = None
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "annual_results.csv", index=False)
    transitions.to_csv(output / "annual_transitions.csv", index=False)
    holdings.to_csv(output / "annual_holdings.csv", index=False)
    _annual_benchmark_summary(results).to_csv(output / "annual_benchmark_summary.csv", index=False)
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
    (output / "protocol.json").write_text(json.dumps(asdict(protocol), indent=2), encoding="utf-8")
    print(results.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
