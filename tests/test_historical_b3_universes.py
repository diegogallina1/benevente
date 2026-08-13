import pandas as pd

from build_historical_b3_universes import build_historical_b3_universes


def test_historical_builder_reports_missing_archives_without_substituting_current_universe(tmp_path):
    universe, coverage = build_historical_b3_universes(2013, 2014, tmp_path)
    assert universe.empty
    assert coverage.status.tolist() == ["blocked", "blocked"]
    assert coverage.reason.str.contains("Missing B3 archive").all()
