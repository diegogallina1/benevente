import numpy as np
import pandas as pd

from profile_intrayear_risk import apply_profile_overlay


def frame() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=50)
    market = pd.Series([100.0] * 20 + [75.0] * 30)
    return pd.DataFrame({
        "date": dates,
        "IBOVESPA": market,
        "strategy_daily_return": .001,
        "cdi_daily_return": .0001,
    })


def test_profile_overlay_is_lagged_and_conservative_reduces_more() -> None:
    source = frame()
    target = pd.Series(.55, index=source.index)
    conservative = apply_profile_overlay(source, target, "conservador")
    aggressive = apply_profile_overlay(source, target, "arrojado")
    shock = 20
    assert conservative.loc[shock, "risk_state"] == 0
    assert conservative.loc[shock + 1, "risk_state"] == 2
    assert conservative.loc[shock + 1, "protected_equity_weight"] < aggressive.loc[shock + 1, "protected_equity_weight"]


def test_no_stress_equals_base_without_overlay_cost() -> None:
    source = frame().iloc[:20].copy()
    target = pd.Series(.55, index=source.index)
    result = apply_profile_overlay(source, target, "equilibrado")
    assert np.allclose(result.protected_return, result.strategy_daily_return)
