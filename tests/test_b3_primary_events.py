import pandas as pd

from b3_primary_events import (
    TickerContext, _cash_type, _security_class, _share_factor, normalize_issuer_events,
)


def context(ticker="PETR3", isin="BRPETRACNOR9") -> TickerContext:
    return TickerContext(
        ticker=ticker, isin=isin, issuer="PETR", security_class=_security_class(ticker),
        trading_dates=(pd.Timestamp("2020-01-02"), pd.Timestamp("2020-01-03"), pd.Timestamp("2020-01-06")),
    )


def test_b3_labels_and_share_factors_are_explicit() -> None:
    assert _cash_type("JRS CAP PROPRIO") == "jcp"
    assert _cash_type("DIVIDENDO") == "dividend"
    assert _cash_type("INCORPORACAO") == "merger"
    assert _cash_type("CIS RED CAP") == "spin_off"
    assert _share_factor("DESDOBRAMENTO", "100,000") == 2.0
    assert _share_factor("BONIFICACAO", "10,000") == 1.1
    assert _share_factor("GRUPAMENTO", "0,100") == 0.1


def test_next_session_never_uses_the_cum_rights_date() -> None:
    assert context().next_session("02/01/2020") == "2020-01-03"
    assert context().next_session("03/01/2020") == "2020-01-06"
    assert context().next_session("06/01/2020") is None
    assert context().next_session("16/11/1998") is None


def test_normalizer_maps_security_class_and_keeps_subscription_unresolved() -> None:
    ctx = context()
    supplement = {
        "stockDividends": [{
            "assetIssued": ctx.isin, "isinCode": ctx.isin, "factor": "100,000", "label": "DESDOBRAMENTO",
            "lastDatePrior": "02/01/2020", "approvedOn": "01/01/2020",
        }],
        "subscriptions": [{
            "assetIssued": ctx.isin, "isinCode": ctx.isin, "percentage": "10,0", "priceUnit": "5,0",
            "label": "SUBSCRICAO", "lastDatePrior": "03/01/2020", "approvedOn": "01/01/2020",
            "subscriptionDate": "10/01/2020",
        }],
    }
    cash = [{
        "typeStock": "ON", "valueCash": "1,25", "corporateAction": "DIVIDENDO",
        "lastDatePriorEx": "02/01/2020", "dateApproval": "01/01/2020",
    }]
    events, coverage = normalize_issuer_events(
        [ctx], supplement, cash, "https://sistemaswebb3-listados.b3.com.br/a",
        ["https://sistemaswebb3-listados.b3.com.br/b"], "2020-02-01T00:00:00+00:00",
    )
    assert {row["event_type"] for row in events} == {"dividend", "split", "subscription"}
    split = next(row for row in events if row["event_type"] == "split")
    assert split["share_factor"] == 2.0
    subscription = next(row for row in events if row["event_type"] == "subscription")
    assert subscription["resolution"] == ""
    assert coverage[0]["status"] == "queried_current_endpoint"
    assert "historical completeness not certified" in coverage[0]["note"]


def test_identical_cash_installments_are_not_collapsed() -> None:
    ctx = context()
    row = {
        "typeStock": "ON", "valueCash": "0,50", "corporateAction": "DIVIDENDO",
        "lastDatePriorEx": "02/01/2020", "dateApproval": "01/01/2020",
    }
    first = {**row, "_b3_row_number": 1}
    second = {**row, "_b3_row_number": 2}
    events, _ = normalize_issuer_events(
        [ctx], {"stockDividends": [], "subscriptions": []}, [first, second],
        "https://sistemaswebb3-listados.b3.com.br/a", [], "2020-02-01T00:00:00+00:00",
    )
    assert len(events) == 2
    assert len({item["event_id"] for item in events}) == 2
