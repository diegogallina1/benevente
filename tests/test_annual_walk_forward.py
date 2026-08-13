import pandas as pd
import pytest

from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 RISK_PROFILE_LIMITS, protocol_for_risk_profile,
                                 run_adaptive_factor_walk_forward,
                                 select_factor_out_of_sample)
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from fundamentals import FundamentalSnapshot
from annual_decision_evidence import build_decision_evidence


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


def test_last_available_year_is_held_to_the_observed_market_cutoff():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2021-12-30", offline=True)
    results, _, _ = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(
        AnnualWalkForwardConfig(2020, 2022)
    )
    terminal = results.iloc[-1]
    assert terminal.decision_year == 2021
    assert terminal.decision_date == "2021-01-01"
    assert terminal.holding_end_exclusive == "2021-12-31"
    assert terminal.net_return == pytest.approx(terminal.net_return)


def test_annual_walk_forward_uses_only_newest_available_filing_per_ticker():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    older = old_snapshot()
    newer = old_snapshot().model_copy(update={"as_of_date": pd.Timestamp("2019-09-30"),
                                              "available_date": pd.Timestamp("2019-11-01"), "roe": .20})
    results, _, _ = AnnualWalkForwardEngine(prices, [older, newer], config).run(AnnualWalkForwardConfig(2020, 2022))
    assert results.known_snapshot_count.eq(1).all()


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
    assert results.opening_wealth_brl.iloc[1] == pytest.approx(results.closing_wealth_brl.iloc[0])


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


def test_decision_evidence_blocks_a_snapshot_missing_from_the_dated_b3_universe():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    universe = pd.DataFrame([{"decision_date": "2020-01-01", "universe_year": 2020,
                              "ticker": "VALE3.SA", "asset_class": "equity"}])
    mapping = pd.DataFrame([{"universe_year": 2020, "ticker": "VALE3.SA", "mapping_status": "accepted"}])
    evidence, _ = build_decision_evidence(universe, mapping)
    with pytest.raises(ValueError, match="No annual decisions"):
        AnnualWalkForwardEngine(prices, [old_snapshot()], config, evidence).run(AnnualWalkForwardConfig(2020, 2021))


def test_turnover_uses_drifted_weights_after_the_holding_year():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    base, _, _ = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2023))
    changed_prices = prices.copy()
    changed_prices.loc[(changed_prices.index >= "2020-01-02") & (changed_prices.index < "2021-01-01"), "PETR4.SA"] *= 2
    changed, _, _ = AnnualWalkForwardEngine(changed_prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2023))
    assert base.loc[base.decision_year == 2021, "turnover"].item() != changed.loc[changed.decision_year == 2021, "turnover"].item()


def test_triple_factor_keeps_primary_quality_asset_when_secondary_solvency_is_unavailable():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    snapshot = old_snapshot().model_copy(update={"debt_to_ebitda": None, "interest_coverage": None})
    engine = AnnualWalkForwardEngine(prices, [snapshot], config)
    protocol = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", maximum_equity_weight=.55,
                                       maximum_asset_weight=.12, top_assets=4)
    results, _, holdings = engine.run(protocol)
    assert results.factor.eq("triple_factor").all()
    assert results.target_equity_weight.eq(.12).all()
    assert holdings.loc[holdings.ticker.eq("PETR4.SA"), "eligible_at_decision"].all()


def test_triple_factor_never_exceeds_equity_or_issuer_policy_cap():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    snapshots = [old_snapshot(), old_snapshot().model_copy(update={"ticker": "VALE3.SA"})]
    engine = AnnualWalkForwardEngine(prices, snapshots, config)
    protocol = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", maximum_equity_weight=.60,
                                       maximum_asset_weight=.15, top_assets=4)
    results, _, holdings = engine.run(protocol)
    assert results.target_equity_weight.le(.30 + 1e-8).all()
    equity_holdings = holdings[holdings.ticker.ne("TITULO_CDI")]
    assert equity_holdings.weight.le(.15 + 1e-8).all()


def test_named_risk_profile_sets_guardrails_without_changing_factor_or_asset_count():
    base = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", top_assets=4)
    protocol = protocol_for_risk_profile(base, "conservador")
    assert protocol.risk_profile == "conservador"
    assert protocol.maximum_equity_weight == RISK_PROFILE_LIMITS["conservador"]["maximum_equity_weight"]
    assert protocol.maximum_asset_weight == RISK_PROFILE_LIMITS["conservador"]["maximum_asset_weight"]
    assert protocol.factor == "triple_factor"
    assert protocol.top_assets == 4


def test_cli_requires_a_hashed_manifest_for_total_return_inputs(monkeypatch):
    import annual_walk_forward
    monkeypatch.setattr("sys.argv", ["annual_walk_forward.py", "--prices", "prices.csv", "--fundamentals", "fundamentals.csv",
                                      "--start-year", "2020", "--end-year", "2022", "--price-basis", "total_return"])
    with pytest.raises(SystemExit, match="2"):
        annual_walk_forward.main()


def test_price_column_resolution_accepts_cvm_suffix_and_canonical_b3_code():
    from annual_walk_forward import _price_column_for_ticker
    columns = pd.Index(["PETR4", "TITULO_CDI"])
    assert _price_column_for_ticker("PETR4.SA", columns) == "PETR4"
    assert _price_column_for_ticker("PETR4", columns) == "PETR4"


def test_walk_forward_matches_cvm_snapshot_ticker_to_canonical_b3_price_column():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    prices = prices.rename(columns={"PETR4.SA": "PETR4"})
    results, _, holdings = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(
        AnnualWalkForwardConfig(2020, 2022)
    )
    assert not results.empty
    assert holdings.ticker.eq("PETR4.SA").any()


def test_recent_market_sessions_ignores_sparse_holiday_rows_without_filling_prices():
    from annual_walk_forward import _recent_market_sessions
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.DataFrame({"AAA3": [1, 2, None, 3, 4], "BBB3": [1, 2, None, 3, 4],
                           "CCC3": [1, 2, 1, 3, 4], "TITULO_CDI": [1, 1, 1, 1, 1]}, index=dates)
    sessions = _recent_market_sessions(prices, pd.Timestamp("2020-01-06"), minimum_history_days=3)
    assert pd.Timestamp("2020-01-03") not in sessions
    assert sessions.tolist() == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02"),
                                 pd.Timestamp("2020-01-04"), pd.Timestamp("2020-01-05")]


def test_mvo_comparator_receives_only_assets_that_pass_the_same_screen(monkeypatch):
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    seen: list[set[str]] = []
    import annual_walk_forward
    original = annual_walk_forward.MeanVarianceOptimizer.optimize
    def capture(self, historical_returns, *args, **kwargs):
        seen.append(set(historical_returns.columns))
        return original(self, historical_returns, *args, **kwargs)
    monkeypatch.setattr(annual_walk_forward.MeanVarianceOptimizer, "optimize", capture)
    AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2022))
    assert seen and all(columns == {"PETR4.SA", "TITULO_CDI"} for columns in seen)
