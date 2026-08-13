import pandas as pd
import pytest

from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 run_adaptive_factor_walk_forward,
                                 select_factor_out_of_sample)
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from fundamentals import FundamentalSnapshot


def old_snapshot() -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker="PETR4.SA", as_of_date="2018-12-31", available_date="2019-03-31", sector="Energy",
        is_financial=False, market_cap_brl=10_000_000_000, price_to_earnings=8, price_to_book=1,
        ev_to_ebit=6, free_cash_flow_yield=.08, roe=.16, roic=.15, debt_to_ebitda=1,
        interest_coverage=5, operating_margin=.2, revenue_growth_3y=.1,
        average_daily_value_brl=100_000_000, source="test PIT snapshot",
    )


def test_annual_walk_forward_freezes_then_holds_each_year_without_future_filing():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    results, transitions, holdings = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(
        AnnualWalkForwardConfig(2020, 2023)
    )
    assert results.decision_year.tolist() == [2020, 2021, 2022]
    assert (pd.to_datetime(results.decision_date) < pd.to_datetime(results.holding_end_exclusive)).all()
    assert results.known_snapshot_count.eq(1).all()
    assert not holdings.empty
    assert not transitions.empty
    assert results.net_return.notna().all()
    assert {"mvo_eligible_net_return", "cdi_net_return"}.issubset(results.columns)
    assert {"decision_action", "decision_rationale", "realised_next_year_return", "factor_signal_at_decision", "trailing_12m_return_at_decision"}.issubset(holdings.columns)
    petr4 = holdings[holdings.ticker == "PETR4.SA"]
    assert petr4.decision_rationale.str.contains("point-in-time").all()


def test_annual_walk_forward_rejects_a_period_without_prior_fundamental_evidence():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    future = old_snapshot().model_copy(update={"available_date": pd.Timestamp("2021-12-31")})
    with pytest.raises(ValueError, match="No annual decisions"):
        AnnualWalkForwardEngine(prices, [future], config).run(AnnualWalkForwardConfig(2020, 2021))


def test_factor_selection_uses_only_years_before_the_holdout_cutoff():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    engine = AnnualWalkForwardEngine(prices, [old_snapshot()], config)
    protocol = AnnualWalkForwardConfig(2020, 2024, minimum_factor_training_years=1)
    factor, leaderboard = select_factor_out_of_sample(engine, protocol, training_end_year=2022)
    assert factor in {"value_quality", "momentum_12m", "low_volatility"}
    assert leaderboard.training_years.max() <= 2
    assert set(leaderboard.factor) == {"value_quality", "momentum_12m", "low_volatility"}


def test_adaptive_factor_walk_forward_selects_before_each_unseen_year():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    protocol = AnnualWalkForwardConfig(2020, 2024, minimum_factor_training_years=1)
    results, transitions, holdings, choices = run_adaptive_factor_walk_forward(
        AnnualWalkForwardEngine(prices, [old_snapshot()], config), protocol
    )
    assert results.decision_year.tolist() == [2021, 2022, 2023]
    assert choices.decision_year.tolist() == [2021, 2022, 2023]
    assert choices.selection_end_year_exclusive.tolist() == [2021, 2022, 2023]
    assert not transitions.empty
    assert not holdings.empty


def test_future_prices_do_not_change_an_earlier_january_portfolio():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    protocol = AnnualWalkForwardConfig(2020, 2023)
    engine = AnnualWalkForwardEngine(prices, [old_snapshot()], config)
    original, _, original_holdings = engine.run(protocol)
    altered = prices.copy()
    altered.loc[altered.index >= pd.Timestamp("2021-01-01"), "PETR4.SA"] *= 4
    changed, _, changed_holdings = AnnualWalkForwardEngine(altered, [old_snapshot()], config).run(protocol)
    first_original = original_holdings[original_holdings.decision_year == 2020][["ticker", "weight"]].reset_index(drop=True)
    first_changed = changed_holdings[changed_holdings.decision_year == 2020][["ticker", "weight"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(first_original, first_changed)
    assert original.loc[original.decision_year == 2020, "net_return"].item() == changed.loc[changed.decision_year == 2020, "net_return"].item()


def test_turnover_uses_drifted_weights_after_the_holding_year():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    base, _, _ = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2023))
    changed_prices = prices.copy()
    changed_prices.loc[(changed_prices.index >= "2020-01-02") & (changed_prices.index < "2021-01-01"), "PETR4.SA"] *= 2
    changed, _, _ = AnnualWalkForwardEngine(changed_prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2023))
    assert base.loc[base.decision_year == 2021, "turnover"].item() != changed.loc[changed.decision_year == 2021, "turnover"].item()
