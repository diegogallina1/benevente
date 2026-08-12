import pandas as pd
import pytest

from horizon import estimation_window_days
from market_snapshot import MarketSnapshot, load_market_snapshots
from order_builder import build_initial_orders
from price_history import load_price_history
from production_policy import ProductionPolicy
from quality_metrics import apply_quality_metric_overrides, QualityMetricOverride
from fundamentals import FundamentalSnapshot


def snapshot(ticker: str) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker=ticker, as_of_date=pd.Timestamp("2024-12-31"), available_date=pd.Timestamp("2025-02-28"),
        sector="Industrials", market_cap_brl=10_000_000_000, price_to_earnings=8, price_to_book=1.2,
        ev_to_ebit=6, free_cash_flow_yield=0.08, roe=0.15, roic=0.16, debt_to_ebitda=1.1,
        interest_coverage=6.0, operating_margin=0.2, revenue_growth_3y=0.1,
        average_daily_value_brl=100_000_000, source="test fixture",
    )


def test_horizon_window_is_explicit_and_increases_for_longer_mandates():
    assert estimation_window_days(1) == 252
    assert estimation_window_days(2) == 504
    assert estimation_window_days(5) == 756
    assert estimation_window_days(10) == estimation_window_days(15) == 1260
    with pytest.raises(ValueError):
        estimation_window_days(3)


def test_price_history_rejects_future_and_incomplete_input(tmp_path):
    path = tmp_path / "prices.csv"
    pd.DataFrame({
        "date": pd.date_range("2025-01-01", periods=3, freq="D"),
        "PETR4.SA": [30.0, 31.0, 32.0], "TITULO_CDI": [100.0, 100.1, 100.2],
    }).to_csv(path, index=False)
    history = load_price_history(path, pd.Timestamp("2025-01-03"), ["PETR4.SA", "TITULO_CDI"], 2)
    assert list(history.columns) == ["PETR4.SA", "TITULO_CDI"]
    with pytest.raises(ValueError, match="after the decision"):
        load_price_history(path, pd.Timestamp("2025-01-02"), ["PETR4.SA", "TITULO_CDI"], 1)


def test_initial_orders_are_lot_rounded_costed_and_liquidity_limited():
    market = {
        "PETR4.SA": MarketSnapshot(ticker="PETR4.SA", observed_at="2026-08-12", market_cap_brl=1e11,
                                     average_daily_value_brl=1e8, close_price_brl=31.0, lot_size=1,
                                     source="B3 export test"),
    }
    orders, summary = build_initial_orders(
        pd.Series({"PETR4.SA": 0.12, "TITULO_CDI": 0.88}), market, pd.Timestamp("2026-08-12"),
        100_000, 0.05, "pilot",
    )
    assert len(orders) == 1
    assert orders[0].ticker == "PETR4"
    assert orders[0].quantity == 387
    assert orders[0].estimated_cost_brl > 0
    assert summary["cash_after_orders_brl"] > 0
    with pytest.raises(ValueError, match="average daily value"):
        build_initial_orders(pd.Series({"PETR4.SA": 0.12}), market, pd.Timestamp("2026-08-12"),
                             100_000, 0.00001, "pilot")


def test_market_snapshot_and_policy_exclusions_are_enforced(tmp_path):
    path = tmp_path / "market.csv"
    pd.DataFrame([{
        "ticker": "PETR4.SA", "observed_at": "2026-08-12", "market_cap_brl": 1e11,
        "average_daily_value_brl": 1e8, "close_price_brl": 31, "lot_size": 1, "source": "B3 export test",
    }]).to_csv(path, index=False)
    loaded = load_market_snapshots(path, pd.Timestamp("2026-08-12"), 1)
    assert loaded["PETR4.SA"].close_price_brl == 31
    policy = ProductionPolicy(policy_id="pilot", owner="Diego", effective_date="2026-08-12",
                              portfolio_value_brl=100_000, horizon_years=5, maximum_rebalance_cost_brl=500,
                              excluded_tickers=["PETR4.SA"])
    assert policy.excluded_tickers == ["PETR4.SA"]


def test_verified_solvency_override_enables_nonfinancial_screening_fields():
    base = snapshot("PETR4.SA")
    unavailable = base.model_copy(update={"debt_to_ebitda": None, "interest_coverage": None})
    override = QualityMetricOverride(ticker="PETR4.SA", observed_at="2025-02-28", debt_to_ebitda=1.2,
                                     interest_coverage=4.0, source="CVM filing note test")
    updated = apply_quality_metric_overrides([unavailable], {"PETR4.SA": override})[0]
    assert updated.debt_to_ebitda == pytest.approx(1.2)
    assert updated.interest_coverage == pytest.approx(4.0)
