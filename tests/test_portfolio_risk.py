import numpy as np
import pandas as pd
import pytest

from portfolio_risk import apply_annual_risk_policy, risk_profile_spec


def history(volatility: float, periods: int = 252) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-02", periods=periods)
    return pd.DataFrame(
        {f"A{i}": rng.normal(.0003, volatility / np.sqrt(252), periods) for i in range(1, 7)},
        index=dates,
    )


def target() -> pd.Series:
    return pd.Series({"A1": .45, "A2": .10, "A3": 0.0, "A4": 0.0, "A5": 0.0, "A6": 0.0, "TITULO_CDI": .45})


def test_profile_layer_enforces_five_positions_without_increasing_equity() -> None:
    adjusted, report = apply_annual_risk_policy(
        target(), history(.10), ["A1", "A2", "A3", "A4", "A5", "A6"], "equilibrado",
        decision_date=pd.Timestamp("2025-01-02"),
    )
    assert (adjusted.drop("TITULO_CDI") > 0).sum() >= 5
    assert adjusted.sum() == pytest.approx(1.0)
    assert adjusted.drop("TITULO_CDI").sum() <= .55 + 1e-10
    assert report["effective_equity_weight"] <= report["base_equity_weight"]


def test_high_volatility_reduces_equity_and_profiles_are_distinct() -> None:
    conservative, _ = apply_annual_risk_policy(
        target(), history(.45), ["A1", "A2", "A3", "A4", "A5", "A6"], "conservador",
        decision_date=pd.Timestamp("2025-01-02"),
    )
    aggressive, _ = apply_annual_risk_policy(
        target(), history(.45), ["A1", "A2", "A3", "A4", "A5", "A6"], "arrojado",
        decision_date=pd.Timestamp("2025-01-02"),
    )
    assert conservative.drop("TITULO_CDI").sum() < aggressive.drop("TITULO_CDI").sum()
    assert conservative.drop("TITULO_CDI").sum() < .35


def test_risk_layer_rejects_information_from_or_after_decision() -> None:
    future = history(.10)
    with pytest.raises(ValueError, match="on or after"):
        apply_annual_risk_policy(target(), future, list(future.columns), "equilibrado",
                                 decision_date=future.index[-1])


def test_portuguese_profile_names_and_moderate_alias() -> None:
    assert risk_profile_spec("conservador").target_volatility == .08
    assert risk_profile_spec("moderado") == risk_profile_spec("equilibrado")
    assert risk_profile_spec("arrojado").target_volatility == .18
