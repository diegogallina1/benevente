import pandas as pd

from build_b3_price_history import build_price_history


def test_price_history_fails_closed_when_no_official_archive_is_available(tmp_path):
    prices, report = build_price_history({"AAAA3.SA"}, 2020, 2020, tmp_path)
    assert prices.empty
    assert report.status.tolist() == ["blocked"]
    assert report.reason.str.contains("missing_b3_archive").all()
