import pandas as pd

from annual_input_contract import validate_annual_inputs


def test_price_only_input_is_blocked_before_a_performance_claim():
    prices = pd.DataFrame({"date": ["2020-01-02"], "AAAA3.SA": [10.0]})
    result = validate_annual_inputs(prices, pd.DataFrame([{"ticker": "AAAA3.SA"}]), "price_return_only")
    assert not result.performance_permitted
    assert "price_return_only_excludes_dividends_jcp_and_corporate_actions" in result.reasons


def test_total_return_input_with_cdi_is_permitted():
    prices = pd.DataFrame({"date": ["2020-01-02"], "AAAA3.SA": [10.0], "TITULO_CDI": [100.0]})
    result = validate_annual_inputs(prices, pd.DataFrame([{"ticker": "AAAA3.SA"}]), "total_return")
    assert result.performance_permitted
