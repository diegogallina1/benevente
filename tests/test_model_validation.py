import pandas as pd

from model_validation import (AnnualHoldoutGate, CommercialReadinessGate, SelectionGate,
                              annual_holdout_readiness, commercial_readiness, passes_selection_gate)


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


def annual_result(years: range, benevente: float, cdi: float, mvo: float) -> pd.DataFrame:
    count = len(years)
    # Preserve positive but non-constant excess so the information ratio is
    # defined in the validation test.
    wobble = [0.002 if index % 2 else -0.001 for index in range(count)]
    return pd.DataFrame({"decision_year": list(years),
                         "net_return": [benevente + value for value in wobble],
                         "cdi_net_return": cdi,
                         "mvo_eligible_net_return": mvo})


def test_annual_holdout_requires_verified_total_return_and_beating_both_benchmarks():
    results = annual_result(range(2013, 2023), .15, .08, .10)
    gate = AnnualHoldoutGate(min_training_years=5, min_holdout_years=3)
    approved, evidence = annual_holdout_readiness(results, 2019, True, gate)
    assert approved
    assert evidence["annual_validation_status"] == "approved"
    blocked, blocked_evidence = annual_holdout_readiness(results, 2019, False, gate)
    assert not blocked
    assert "total_return_input_not_verified" in blocked_evidence["annual_validation_reasons"]


def test_annual_holdout_does_not_approve_a_strategy_that_loses_to_mvo():
    results = annual_result(range(2013, 2023), .10, .08, .14)
    approved, evidence = annual_holdout_readiness(results, 2019, True, AnnualHoldoutGate())
    assert not approved
    assert "did_not_beat_mvo_in_frozen_holdout" in evidence["annual_validation_reasons"]


def test_public_research_source_cannot_be_passed_as_verified_holdout_input():
    results = annual_result(range(2013, 2023), .15, .08, .10)
    source_tier = "public_reproducible_research"
    source_verified = source_tier in {"official_or_licensed_verified", "reconciled_primary_records"}
    approved, evidence = annual_holdout_readiness(results, 2019, source_verified, AnnualHoldoutGate())
    assert not approved
    assert "total_return_input_not_verified" in evidence["annual_validation_reasons"]
