import pandas as pd
import numpy as np
import pytest

from benevente2_event_risk import (
    RiskOverlayConfig,
    apply_overlay,
    estimate_intrayear_tax,
    observable_stress,
    reconcile_daily_returns,
)


def sample_frame(periods: int = 40) -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=periods)
    market = pd.Series([100.0] * 20 + [80.0] * (periods - 20))
    return pd.DataFrame({
        "date": dates,
        "decision_year": dates.year,
        "strategy": (1.01 ** pd.Series(range(periods))).to_numpy(),
        "cdi": (1.001 ** pd.Series(range(periods))).to_numpy(),
        "IBOVESPA": market,
        "mvo": (1.005 ** pd.Series(range(periods))).to_numpy(),
        "phase": "evaluated",
    })


def test_market_shock_only_changes_tradable_signal_next_session() -> None:
    frame = sample_frame()
    signal = observable_stress(frame.IBOVESPA, RiskOverlayConfig(volatility_window=5, peak_window=20))
    shock = 20
    assert signal.loc[shock, "stress_at_close"] == 2
    assert signal.loc[shock, "tradable_stress"] == 0
    assert signal.loc[shock + 1, "tradable_stress"] == 2


def test_overlay_moves_excess_return_toward_cdi_when_stressed() -> None:
    frame = sample_frame()
    config = RiskOverlayConfig(volatility_window=5, peak_window=20, recovery_days=10, cost_bps=0)
    result = apply_overlay(frame, pd.Series(0.95, index=frame.index), config)
    stressed = result.risk_state.eq(2)
    assert stressed.any()
    assert np.allclose(result.loc[stressed, "benevente2_equity_weight"], 0.25)
    base_excess = result.loc[stressed, "benevente1_return"] - result.loc[stressed, "cdi_return"]
    protected_excess = result.loc[stressed, "benevente2_return"] - result.loc[stressed, "cdi_return"]
    assert (protected_excess.abs() < base_excess.abs()).all()


def test_no_stress_reproduces_benevente1_without_overlay_cost() -> None:
    frame = sample_frame(20)
    config = RiskOverlayConfig(volatility_window=5, peak_window=20, cost_bps=0)
    result = apply_overlay(frame, pd.Series(0.55, index=frame.index), config)
    assert result.benevente2_return.tolist() == pytest.approx(result.benevente1_return.tolist())


def test_daily_reconciliation_matches_declared_annual_endpoint() -> None:
    level = pd.Series([100.0, 110.0, 121.0, 133.1])
    years = pd.Series([2020, 2020, 2021, 2021])
    targets = pd.Series({2020: 0.05, 2021: 0.20})
    returns = reconcile_daily_returns(level, years, targets)
    assert (1 + returns[years.eq(2020)]).prod() - 1 == pytest.approx(0.05)
    assert (1 + returns[years.eq(2021)]).prod() - 1 == pytest.approx(0.20)


def test_intrayear_tax_depends_on_capital_and_respects_monthly_exemption() -> None:
    frame = sample_frame(60)
    frame["benevente1_daily_return"] = 0.002
    frame["cdi_daily_return"] = 0.0002
    config = RiskOverlayConfig(volatility_window=5, peak_window=20, recovery_days=10, cost_bps=0)
    result = apply_overlay(frame, pd.Series(0.95, index=frame.index), config)
    small = estimate_intrayear_tax(result, 20_000)
    large = estimate_intrayear_tax(result, 1_000_000)
    assert small["estimated_incremental_tax_brl"] == pytest.approx(0.0)
    assert large["estimated_incremental_tax_brl"] >= 0
    assert large["estimated_terminal_wealth_after_incremental_tax_brl"] <= large["gross_terminal_wealth_brl"]
    assert large["monthly_sales_exemption_brl"] == 20_000
