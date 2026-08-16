import pandas as pd

from annual_decision_evidence import build_decision_evidence


def test_evidence_uses_the_same_year_and_never_a_future_b3_listing():
    universe = pd.DataFrame([
        {"decision_date": "2020-01-02", "universe_year": 2020, "ticker": "AAAA3.SA", "asset_class": "equity"},
        {"decision_date": "2021-01-04", "universe_year": 2021, "ticker": "BBBB3.SA", "asset_class": "equity"},
    ])
    mapping = pd.DataFrame([
        {"universe_year": 2020, "ticker": "AAAA3.SA", "mapping_status": "accepted"},
        {"universe_year": 2021, "ticker": "BBBB3.SA", "mapping_status": "accepted"},
    ])
    evidence, manifest = build_decision_evidence(universe, mapping)
    assert evidence.allows(pd.Timestamp("2020-01-02"), "AAAA3.SA")
    assert not evidence.allows(pd.Timestamp("2020-01-02"), "BBBB3.SA")
    assert manifest.accepted_identifier_equities.tolist() == [1, 1]


def test_evidence_keeps_share_classes_under_one_economic_issuer():
    universe = pd.DataFrame([
        {"decision_date": "2025-01-02", "universe_year": 2025, "ticker": "AAAA3.SA", "asset_class": "equity"},
        {"decision_date": "2025-01-02", "universe_year": 2025, "ticker": "AAAA4.SA", "asset_class": "equity"},
    ])
    mapping = pd.DataFrame([
        {"universe_year": 2025, "ticker": "AAAA3.SA", "mapping_status": "accepted", "cnpj_cia": "00.000.000/0001-00"},
        {"universe_year": 2025, "ticker": "AAAA4.SA", "mapping_status": "accepted", "cnpj_cia": "00.000.000/0001-00"},
    ])
    evidence, _ = build_decision_evidence(universe, mapping)
    issuers = evidence.issuer_ids(pd.Timestamp("2025-01-02"))
    assert issuers["AAAA3.SA"] == issuers["AAAA4.SA"]
