import pandas as pd

from consolidate_b3_cvm_coverage import consolidate


def test_consolidation_reports_universe_mapping_and_fundamental_gates(tmp_path):
    panel = tmp_path / "panel.csv"; coverage = tmp_path / "coverage.csv"
    universe = tmp_path / "universe.csv"; mapping = tmp_path / "mapping.csv"
    pd.DataFrame([{"decision_date": "2013-01-02", "ticker": "AAAA3.SA"}]).to_csv(panel, index=False)
    pd.DataFrame([
        {"decision_date": "2013-01-02", "ticker": "AAAA3.SA", "status": "accepted", "reason": ""},
        {"decision_date": "2013-01-02", "ticker": "BBBB3.SA", "status": "blocked", "reason": "no filing"},
    ]).to_csv(coverage, index=False)
    pd.DataFrame([
        {"universe_year": 2013, "ticker": "AAAA3.SA", "asset_class": "equity"},
        {"universe_year": 2013, "ticker": "BBBB3.SA", "asset_class": "equity"},
        {"universe_year": 2013, "ticker": "ETF11.SA", "asset_class": "etf"},
    ]).to_csv(universe, index=False)
    pd.DataFrame([
        {"universe_year": 2013, "ticker": "AAAA3.SA", "mapping_status": "accepted"},
        {"universe_year": 2013, "ticker": "BBBB3.SA", "mapping_status": "accepted"},
    ]).to_csv(mapping, index=False)
    result, summary = consolidate([panel], [coverage], universe, mapping)
    assert len(result) == 1
    assert summary.loc[0, "b3_instruments"] == 3
    assert summary.loc[0, "fundamental_accepted"] == 1
