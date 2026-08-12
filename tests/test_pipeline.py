import pandas as pd
import pytest
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from backtest_engine import BacktestEngine
from execution_costs import ClearB3CostModel
from fundamentals import FundamentalSnapshot
from portfolio_recommendation import ValuePortfolioPlanner
from production_policy import ProductionPolicy
from pilot_tracker import build_performance
from shadow_portfolio import ExecutedOrder, ProposedOrder, reconcile
from value_quality import ValueQualitySelector


def test_offline_pipeline_generates_valid_metrics():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2023-01-01", "2025-06-30", offline=True)
    result = BacktestEngine(prices, config).run()
    metrics = BacktestEngine.metrics(result, config.risk_free_rate_annual)
    assert not result.empty
    assert result.turnover.ge(0).all()
    assert set(metrics) == {"cumulative_return", "cagr", "annual_volatility", "sharpe", "max_drawdown", "average_turnover"}


def test_classic_mvo_has_no_signal_dependency():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2023-01-01", "2025-06-30", offline=True)
    result = BacktestEngine(prices, config).run(use_signals=False)
    assert not result.empty
    assert result.equity_cap.eq(0.60).all()


def snapshot(ticker: str, financial: bool = False, fcf_yield: float = 0.08) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker=ticker, as_of_date=pd.Timestamp("2024-12-31"), available_date=pd.Timestamp("2025-02-28"),
        sector="Financials" if financial else "Industrials", is_financial=financial, market_cap_brl=10_000_000_000,
        price_to_earnings=8, price_to_book=1.2, ev_to_ebit=6, free_cash_flow_yield=fcf_yield,
        roe=0.15, roic=None if financial else 0.16, debt_to_ebitda=None if financial else 1.1,
        interest_coverage=None if financial else 6.0, operating_margin=0.2, revenue_growth_3y=0.1,
        average_daily_value_brl=100_000_000, source="test",
    )


def test_value_quality_filters_only_publicly_available_fundamentals():
    selector = ValueQualitySelector(SystemConfig())
    good = snapshot("PETR4.SA")
    bad = snapshot("VALE3.SA", fcf_yield=-0.02)
    assert selector.score([good, bad], pd.Timestamp("2025-02-27")).empty
    scored = selector.score([good, bad], pd.Timestamp("2025-02-28"))
    assert set(scored.loc[scored.eligible, "ticker"]) == {"PETR4.SA"}
    assert scored.loc[scored.ticker.eq("VALE3.SA"), "rejection_reasons"].iloc[0] == "free_cash_flow_yield"


def test_clear_b3_cost_and_shadow_reconciliation():
    cost = ClearB3CostModel().estimate(100_000, 10_000_000)
    assert cost.clear_brokerage_brl == 0
    assert cost.b3_fees_brl == pytest.approx(30.0)
    expected = ProposedOrder("2026-01-02", "PETR4.SA", "BUY", 100, 30.0, 35.0, "thesis-1", "reviewer")
    executed = ExecutedOrder("note-1", "2026-01-03", "PETR4.SA", "BUY", 100, 30.2, 38.0)
    report = reconcile(expected, executed)
    assert report["execution_slippage_brl"] == pytest.approx(20.0)
    assert report["cost_estimation_error_brl"] == pytest.approx(3.0)


def test_value_planner_only_allocates_eligible_assets():
    config = SystemConfig(rolling_window_days=100)
    prices = PointInTimeDataLoader(config).fetch_prices("2023-01-01", "2025-06-30", offline=True)
    returns = prices.pct_change().dropna().iloc[-100:]
    proposal = ValuePortfolioPlanner(config).propose(returns, [snapshot("PETR4.SA")], pd.Timestamp("2025-02-28"), horizon_years=5)
    assert proposal.required_human_approval
    assert proposal.weights["PETR4.SA"] > 0
    assert proposal.weights.drop(labels=["PETR4.SA", "TITULO_CDI"]).sum() == pytest.approx(0.0, abs=1e-7)


def test_value_backtest_uses_screen_and_clear_cost_model():
    config = SystemConfig(rolling_window_days=100, rebalance_days=21)
    prices = PointInTimeDataLoader(config).fetch_prices("2023-01-01", "2025-06-30", offline=True)
    result = BacktestEngine(prices, config).run(
        fundamental_snapshots=[snapshot("PETR4.SA")], cost_model=ClearB3CostModel(),
    )
    assert not result.empty
    assert result.friction_cost.ge(0).all()


def test_production_policy_requires_human_acknowledgement():
    policy = ProductionPolicy(
        policy_id="test-policy", owner="Diego", effective_date="2026-08-12", portfolio_value_brl=100_000,
        horizon_years=5, maximum_equity_weight=0.7, maximum_asset_weight=0.15,
        maximum_rebalance_cost_brl=500, maximum_drawdown_tolerance=0.25,
        acknowledged_not_investment_advice=False,
    )
    with pytest.raises(ValueError, match="Acknowledgement"):
        policy.validate_for_live_proposal()


def test_profile_policy_applies_defaults_and_accepts_long_horizon():
    policy = ProductionPolicy(
        policy_id="pilot-100k", owner="Diego", effective_date="2026-08-12", portfolio_value_brl=100_000,
        risk_profile="moderate", horizon_years=15, maximum_rebalance_cost_brl=500,
    )
    assert policy.maximum_equity_weight == pytest.approx(0.55)
    assert policy.maximum_asset_weight == pytest.approx(0.12)
    assert policy.review_interval_months == 3


def test_custom_policy_requires_advanced_constraints():
    with pytest.raises(ValueError, match="Custom policy"):
        ProductionPolicy(
            policy_id="custom-100k", owner="Diego", effective_date="2026-08-12", portfolio_value_brl=100_000,
            risk_profile="custom", horizon_years=1, maximum_rebalance_cost_brl=500,
        )


def test_shadow_pilot_reports_returns_and_drawdown():
    policy = ProductionPolicy(
        policy_id="pilot-100k", owner="Diego", effective_date="2026-08-12", portfolio_value_brl=100_000,
        risk_profile="moderate", horizon_years=5, maximum_rebalance_cost_brl=500,
    )
    nav = pd.DataFrame([
        {"date": "2026-08-12", "portfolio_value_brl": 100_000, "cdi_value_brl": 100_000, "ibovespa_value_brl": 100_000, "notes": "baseline"},
        {"date": "2026-09-12", "portfolio_value_brl": 98_000, "cdi_value_brl": 101_000, "ibovespa_value_brl": 99_000, "notes": "month one"},
    ])
    performance, summary = build_performance(policy, nav)
    assert summary["portfolio_return"] == pytest.approx(-0.02)
    assert summary["maximum_drawdown"] == pytest.approx(-0.02)
    assert performance.portfolio_drawdown.iloc[-1] == pytest.approx(-0.02)
