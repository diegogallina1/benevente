from config import SystemConfig
from data_loader import PointInTimeDataLoader
from backtest_engine import BacktestEngine


def test_offline_pipeline_generates_valid_metrics():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2023-01-01", "2025-06-30", offline=True)
    result = BacktestEngine(prices, config).run()
    metrics = BacktestEngine.metrics(result, config.risk_free_rate_annual)
    assert not result.empty
    assert result.turnover.ge(0).all()
    assert set(metrics) == {"cumulative_return", "cagr", "annual_volatility", "sharpe", "max_drawdown", "average_turnover"}

