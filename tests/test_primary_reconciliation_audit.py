from tools.build_primary_reconciliation_audit import build


def test_strategy_scope_reconciliation_refuses_false_completion() -> None:
    summary = build()
    assert summary["status"] == "blocked_not_institutionally_reconciled"
    assert summary["holding_year_records"] == 56
    assert summary["current_endpoint_compared_records"] == 54
    assert summary["current_endpoint_unavailable_records"] == 2
    assert summary["manual_events_overlapping_actual_holds"] == 0
    assert summary["material_differences_over_5pp"] == 7
    assert summary["current_b3_endpoint_archive"]["records"] == 9772
    assert summary["current_b3_endpoint_archive"]["price_series_queried"] == 475
