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
from fundamentals import FundamentalSnapshot
from optimizer import MeanVarianceOptimizer
from portfolio_recommendation import ValuePortfolioPlanner


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


class AnnualWalkForwardEngine:
    """Freeze, hold, review: a portfolio process a committee can audit."""
    def __init__(self, prices: pd.DataFrame, snapshots: list[FundamentalSnapshot], config: SystemConfig) -> None:
        self.prices = prices.copy().sort_index()
        self.prices.index = pd.to_datetime(self.prices.index)
        self.snapshots = snapshots
        self.config = config
        if "TITULO_CDI" not in self.prices:
            raise ValueError("Annual walk-forward requires TITULO_CDI in the price history.")

    @staticmethod
    def factor_scores(history: pd.DataFrame, factor: str) -> dict[str, float] | None:
        """Pre-declared, explainable factor candidates for factor selection.

        These scores are known at the annual decision date. ``None`` retains
        the fundamental value/quality ranking. No realized holding-period
        return enters this function.
        """
        if factor == "value_quality":
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

    def run(self, protocol: AnnualWalkForwardConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if protocol.end_year <= protocol.start_year:
            raise ValueError("end_year must be after start_year so at least one holding period can be evaluated.")
        wealth = float(self.config.initial_portfolio_value_brl)
        previous = pd.Series(0.0, index=self.prices.columns)
        mvo_previous = pd.Series(0.0, index=self.prices.columns)
        previous_screen: pd.DataFrame | None = None
        yearly_rows: list[dict] = []
        transition_rows: list[dict] = []
        holding_rows: list[dict] = []

        for year in range(protocol.start_year, protocol.end_year):
            decision = _first_trading_day(self.prices, year)
            next_decision = _first_trading_day(self.prices, year + 1)
            if decision is None or next_decision is None:
                continue
            history = self.prices.loc[self.prices.index < decision].pct_change().dropna()
            if len(history) < protocol.minimum_history_days:
                continue
            known_snapshots = [item for item in self.snapshots if pd.Timestamp(item.available_date) <= decision]
            if not known_snapshots:
                # Do not infer a fundamental screen from a future filing. This
                # year is omitted and the final no-decision error makes the
                # missing evidence visible to the caller.
                continue
            # The selector itself rejects snapshots filed after the decision.
            planner_config = replace(self.config, initial_portfolio_value_brl=wealth,
                                     rolling_window_days=protocol.minimum_history_days,
                                     max_asset_weight=protocol.maximum_asset_weight)
            factor_signal = self.factor_scores(history, protocol.factor)
            proposal = ValuePortfolioPlanner(planner_config).propose(
                history.tail(protocol.minimum_history_days), known_snapshots, decision,
                current_weights=previous, horizon_years=protocol.horizon_years,
                maximum_equity_weight=protocol.maximum_equity_weight,
                maximum_asset_weight=protocol.maximum_asset_weight,
                scores_override=factor_signal,
            )
            target = proposal.weights.reindex(self.prices.columns, fill_value=0.0)
            # Same historical information and constraints, but no alpha score:
            # a fair annual MVO baseline for the very same eligible universe.
            eligible = set(proposal.screen.loc[proposal.screen.eligible, "ticker"])
            neutral_scores = {ticker: 0.0 for ticker in history.columns}
            neutral_scores["TITULO_CDI"] = 1.0
            mvo_target = MeanVarianceOptimizer(planner_config).optimize(
                history.tail(protocol.minimum_history_days), neutral_scores,
                equity_cap=protocol.maximum_equity_weight, signal_influence=0.0,
                eligible_assets=eligible,
            ).reindex(self.prices.columns, fill_value=0.0)
            realised_prices = self.prices.loc[(self.prices.index >= decision) & (self.prices.index < next_decision)]
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
                "factor": protocol.factor,
                "mvo_eligible_net_return": mvo_net_return,
                "cdi_net_return": cdi_net_return,
            })
            for ticker in self.prices.columns:
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
                                        "factor": protocol.factor})
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
                                         "factor": protocol.factor,
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
    result_frames: list[pd.DataFrame] = []
    transition_frames: list[pd.DataFrame] = []
    holding_frames: list[pd.DataFrame] = []
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
        year_protocol = replace(base, start_year=decision_year, end_year=decision_year + 1, factor=factor)
        try:
            yearly, transitions, holdings = engine.run(year_protocol)
        except ValueError:
            continue
        result_frames.append(yearly); transition_frames.append(transitions); holding_frames.append(holdings)
        choices.append({"decision_year": decision_year, "selected_factor": factor,
                        "selection_end_year_exclusive": selection_end,
                        "training_observations": int(board.iloc[0].training_years) if not board.empty else 0,
                        "selection_status": "selected_from_prior_years" if not board.empty else "baseline_retained_missing_training"})
    if not result_frames:
        raise ValueError("No adaptive annual decisions were produced. Review dated price and fundamental coverage.")
    return (pd.concat(result_frames, ignore_index=True), pd.concat(transition_frames, ignore_index=True),
            pd.concat(holding_frames, ignore_index=True), pd.DataFrame(choices))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run annual no-look-ahead Benevente walk-forward evaluation.")
    parser.add_argument("--prices", required=True, help="CSV with date, assets, and TITULO_CDI columns.")
    parser.add_argument("--fundamentals", required=True, help="CSV with FundamentalSnapshot fields and availability dates.")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True, help="First year not held; e.g. 2026 evaluates through 2025.")
    parser.add_argument("--output", default="artifacts/annual_walk_forward")
    parser.add_argument("--factor", choices=["value_quality", "momentum_12m", "low_volatility"], default="value_quality")
    parser.add_argument("--training-end-year", type=int, help="Optional factor-selection cutoff; output is then evaluated only after this year.")
    parser.add_argument("--adaptive-factors", action="store_true", help="Select a pre-declared factor from prior years before each next-year decision.")
    args = parser.parse_args()
    from advisor import snapshots_from_frame
    prices = pd.read_csv(args.prices, parse_dates=["date"]).set_index("date")
    snapshots = snapshots_from_frame(pd.read_csv(args.fundamentals, parse_dates=["as_of_date", "available_date"]))
    protocol = AnnualWalkForwardConfig(args.start_year, args.end_year, factor=args.factor)
    if args.adaptive_factors:
        results, transitions, holdings, factor_choices = run_adaptive_factor_walk_forward(
            AnnualWalkForwardEngine(prices, snapshots, SystemConfig()), protocol)
        leaderboard = None
    elif args.training_end_year:
        factor, leaderboard = select_factor_out_of_sample(engine=AnnualWalkForwardEngine(prices, snapshots, SystemConfig()),
                                                           base=protocol, training_end_year=args.training_end_year)
        protocol = replace(protocol, start_year=args.training_end_year, factor=factor)
        results, transitions, holdings = AnnualWalkForwardEngine(prices, snapshots, SystemConfig()).run(protocol)
        factor_choices = None
    else:
        leaderboard = None
        results, transitions, holdings = AnnualWalkForwardEngine(prices, snapshots, SystemConfig()).run(protocol)
        factor_choices = None
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    results.to_csv(output / "annual_results.csv", index=False)
    transitions.to_csv(output / "annual_transitions.csv", index=False)
    holdings.to_csv(output / "annual_holdings.csv", index=False)
    _annual_benchmark_summary(results).to_csv(output / "annual_benchmark_summary.csv", index=False)
    if leaderboard is not None:
        leaderboard.to_csv(output / "factor_training_leaderboard.csv", index=False)
    if factor_choices is not None:
        factor_choices.to_csv(output / "adaptive_factor_choices.csv", index=False)
    (output / "protocol.json").write_text(json.dumps(asdict(protocol), indent=2), encoding="utf-8")
    print(results.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
