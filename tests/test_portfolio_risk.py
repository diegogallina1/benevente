import numpy as np
import pandas as pd
import pytest

from dataclasses import replace

from portfolio_risk import (apply_annual_risk_policy, resolve_profile_spec,
                            risk_profile_spec)


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


def spread_target() -> pd.Series:
    """Six names inside the issuer cap, so the sleeve is decided by the risk
    layer rather than clipped away by the per-issuer limit before it runs."""
    return pd.Series({f"A{i}": .10 for i in range(1, 7)} | {"TITULO_CDI": .40})


def _floored(profile: str, fraction: float):
    return replace(risk_profile_spec(profile), minimum_equity_fraction_of_cap=fraction)


def test_exposure_floor_stops_the_volatility_target_from_emptying_the_sleeve():
    """The cap sold to an investor must not be decorative."""
    # Noisy enough that the 18% target actually binds; at 45% it does not,
    # and the test would pass without exercising the floor.
    noisy = history(1.2)
    names = ["A1", "A2", "A3", "A4", "A5", "A6"]
    without, report_without = apply_annual_risk_policy(
        spread_target(), noisy, names, "arrojado", decision_date=pd.Timestamp("2025-01-02"))
    with_floor, report_with = apply_annual_risk_policy(
        spread_target(), noisy, names, _floored("arrojado", .60), decision_date=pd.Timestamp("2025-01-02"))
    assert report_without["volatility_limited_equity_weight"] < report_with["volatility_limited_equity_weight"]
    assert with_floor.drop("TITULO_CDI").sum() > without.drop("TITULO_CDI").sum()
    assert report_with["exposure_floor"] == pytest.approx(.60 * .75)


def test_the_floor_never_invents_exposure_the_selection_did_not_ask_for():
    """A floor may undo a reduction; it may never add risk of its own."""
    calm = history(.05)
    names = ["A1", "A2", "A3", "A4", "A5", "A6"]
    base, report = apply_annual_risk_policy(
        target(), calm, names, _floored("arrojado", 1.0), decision_date=pd.Timestamp("2025-01-02"))
    assert report["effective_equity_weight"] <= report["base_equity_weight"] + 1e-12
    assert base.drop("TITULO_CDI").sum() <= .75 + 1e-10


def test_observable_stress_may_still_cut_below_the_floor():
    """The floor binds the volatility target, not the crisis response."""
    names = ["A1", "A2", "A3", "A4", "A5", "A6"]
    calm = history(.10)
    crisis = calm.copy()
    # A 30% fall over the last quarter is observable before the decision.
    crisis.iloc[-60:] = crisis.iloc[-60:] - .006
    spec = _floored("conservador", 1.0)
    _, quiet = apply_annual_risk_policy(target(), calm, names, spec,
                                        decision_date=pd.Timestamp("2025-01-02"))
    _, stressed = apply_annual_risk_policy(target(), crisis, names, spec,
                                           decision_date=pd.Timestamp("2025-01-02"))
    assert stressed["risk_state"] != "normal"
    assert stressed["effective_equity_weight"] < stressed["exposure_floor"]
    assert stressed["effective_equity_weight"] < quiet["effective_equity_weight"]


def test_default_floor_is_zero_so_the_registered_policy_is_unchanged():
    # Todas as especificações registradas, e não três nomes copiados: o
    # ultraconservador entra por apelido e herda a mesma propriedade.
    from portfolio_risk import PROFILE_ALIASES, PROFILE_SPECS
    for name in (*PROFILE_SPECS, *PROFILE_ALIASES):
        assert risk_profile_spec(name).minimum_equity_fraction_of_cap == 0.0
    names = ["A1", "A2", "A3", "A4", "A5", "A6"]
    published, _ = apply_annual_risk_policy(target(), history(.45), names, "equilibrado",
                                            decision_date=pd.Timestamp("2025-01-02"))
    explicit, _ = apply_annual_risk_policy(target(), history(.45), names, _floored("equilibrado", 0.0),
                                           decision_date=pd.Timestamp("2025-01-02"))
    pd.testing.assert_series_equal(published, explicit)


def test_resolve_profile_spec_accepts_a_name_or_a_declared_spec():
    spec = _floored("conservador", .5)
    assert resolve_profile_spec(spec) is spec
    assert resolve_profile_spec("conservador") == risk_profile_spec("conservador")
