import pandas as pd

from model_validation import CommercialReadinessGate, SelectionGate, commercial_readiness, passes_selection_gate


def result_frame(periods: int, return_value: float = .01) -> pd.DataFrame:
    returns = pd.Series([return_value] * periods)
    return pd.DataFrame({
        "date": pd.date_range("2020-01-31", periods=periods, freq="ME"),
        "net_return": returns,
        "wealth": 100 * (1 + returns).cumprod(),
        "turnover": [.10] * periods,
    })


def test_selection_gate_rejects_short_or_nonpositive_excess_history():
    candidate = result_frame(12, .01)
    cdi = result_frame(12, .011)
    passed, evidence = passes_selection_gate(candidate, cdi)
    assert not passed
    assert "insufficient_training_periods" in evidence["selection_reasons"]
    assert "nonpositive_excess_sharpe" in evidence["selection_reasons"]


def test_selection_gate_accepts_only_predefined_minimum_conditions():
    candidate = result_frame(24, .02)
    cdi = result_frame(24, .01)
    passed, evidence = passes_selection_gate(candidate, cdi, SelectionGate(min_excess_sharpe=.0))
    assert passed
    assert evidence["selection_status"] == "accepted"


def test_commercial_readiness_requires_beating_cdi_and_mvo():
    candidate = result_frame(24, .012)
    cdi = result_frame(24, .008)
    mvo = result_frame(24, .006)
    approved, evidence = commercial_readiness(candidate, cdi, mvo, CommercialReadinessGate())
    assert approved
    assert evidence["commercial_readiness"] == "approved"


def test_commercial_readiness_rejects_strategy_that_loses_to_cdi():
    candidate = result_frame(24, .006)
    cdi = result_frame(24, .008)
    mvo = result_frame(24, .004)
    approved, evidence = commercial_readiness(candidate, cdi, mvo, CommercialReadinessGate())
    assert not approved
    assert "did_not_beat_cdi_net_of_costs" in evidence["commercial_readiness_reasons"]
