import pandas as pd
import pytest

from forecast_research import build_conditional_scenarios


def test_conditional_scenario_never_uses_the_selected_year_return():
    holdings = pd.DataFrame([
        {"decision_year": 2023, "decision_date": "2023-01-02", "ticker": "AAAA3.SA", "weight": .12, "eligible_at_decision": True, "realised_next_year_return": .10},
        {"decision_year": 2023, "decision_date": "2023-01-02", "ticker": "BBBB3.SA", "weight": .12, "eligible_at_decision": True, "realised_next_year_return": .20},
        {"decision_year": 2024, "decision_date": "2024-01-02", "ticker": "AAAA3.SA", "weight": .12, "eligible_at_decision": True, "realised_next_year_return": .99},
        {"decision_year": 2024, "decision_date": "2024-01-02", "ticker": "BBBB3.SA", "weight": .12, "eligible_at_decision": True, "realised_next_year_return": .99},
    ])
    result = build_conditional_scenarios(holdings, 2024)
    assert result["portfolio"]["historical_observations"] == 1
    assert result["portfolio"]["historical_median_return"] == pytest.approx(.036)
    assert all(asset["historical_observations"] == 1 for asset in result["assets"])
