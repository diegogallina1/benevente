import pandas as pd
import pytest

from corporate_action_reconciliation import reconstruct_total_return


OFFICIAL = "https://www.b3.com.br/evento/1"


def coverage(tickers=("AAAA3",)) -> pd.DataFrame:
    return pd.DataFrame([
        {"ticker": ticker, "coverage_start": "2020-01-01", "coverage_end": "2020-12-31",
         "status": "complete", "source_url": OFFICIAL, "extracted_at": "2021-01-02T00:00:00Z"}
        for ticker in tickers
    ])


def events(rows=()) -> pd.DataFrame:
    columns = ["event_id", "ticker", "event_type", "ex_date", "cash_per_old_share",
               "share_factor", "source_url", "published_at", "status"]
    return pd.DataFrame(list(rows), columns=columns)


def test_cash_distribution_and_split_reconstruct_total_return() -> None:
    raw = pd.DataFrame({
        "date": ["2020-01-02", "2020-01-03", "2020-01-06"],
        "AAAA3": [10.0, 9.0, 4.5],
        "TITULO_CDI": [100.0, 100.1, 100.2],
    })
    corporate = events([
        ["div-1", "AAAA3", "dividend", "2020-01-03", 1.0, None, OFFICIAL, "2019-12-20", "confirmed"],
        ["split-1", "AAAA3", "split", "2020-01-06", None, 2.0, OFFICIAL, "2020-01-03", "confirmed"],
    ])
    rebuilt, applied, audit = reconstruct_total_return(raw, corporate, coverage())
    assert rebuilt.AAAA3.tolist() == pytest.approx([100.0, 100.0, 100.0])
    assert rebuilt.TITULO_CDI.tolist() == [100.0, 100.1, 100.2]
    assert len(applied) == 2
    assert audit.status == "passed"


def test_empty_event_file_is_valid_only_with_explicit_complete_coverage() -> None:
    raw = pd.DataFrame({"date": ["2020-01-02", "2020-01-03"], "AAAA3": [10.0, 11.0]})
    rebuilt, _, audit = reconstruct_total_return(raw, events(), coverage())
    assert rebuilt.AAAA3.iloc[-1] == pytest.approx(110.0)
    assert audit.status == "passed"
    partial = coverage(); partial.loc[0, "status"] = "partial"
    _, _, blocked = reconstruct_total_return(raw, events(), partial)
    assert blocked.status == "blocked"
    assert "primary_coverage_incomplete" in blocked.limitations


def test_manual_event_and_non_primary_source_block_verification() -> None:
    raw = pd.DataFrame({"date": ["2020-01-02", "2020-01-03"], "AAAA3": [10.0, 11.0]})
    corporate = events([
        ["merge-1", "AAAA3", "merger", "2020-01-03", None, None,
         "https://example.com/event", "2020-01-02", "confirmed"],
    ])
    _, _, audit = reconstruct_total_return(raw, corporate, coverage())
    assert audit.status == "blocked"
    assert "invalid_event_records" in audit.limitations
    assert "non_primary_source_present" in audit.limitations


def test_duplicate_event_ids_are_not_applied() -> None:
    raw = pd.DataFrame({"date": ["2020-01-02", "2020-01-03"], "AAAA3": [10.0, 9.0]})
    corporate = events([
        ["same", "AAAA3", "dividend", "2020-01-03", 1.0, None, OFFICIAL, "2020-01-02", "confirmed"],
        ["same", "AAAA3", "dividend", "2020-01-03", 1.0, None, OFFICIAL, "2020-01-02", "confirmed"],
    ])
    rebuilt, applied, audit = reconstruct_total_return(raw, corporate, coverage())
    assert applied.empty
    assert rebuilt.AAAA3.iloc[-1] == pytest.approx(90.0)
    assert audit.duplicate_events == 2
    assert audit.status == "blocked"


def test_late_listing_uses_its_observed_price_span_not_the_global_panel() -> None:
    raw = pd.DataFrame({
        "date": ["2020-01-02", "2020-01-03", "2020-01-06"],
        "AAAA3": [10.0, 11.0, 12.0],
        "BBBB3": [None, 20.0, 21.0],
    })
    ledger = pd.DataFrame([
        {"ticker": "AAAA3", "coverage_start": "2020-01-02", "coverage_end": "2020-01-06",
         "status": "complete", "source_url": OFFICIAL, "extracted_at": "2021-01-02T00:00:00Z"},
        {"ticker": "BBBB3", "coverage_start": "2020-01-03", "coverage_end": "2020-01-06",
         "status": "complete", "source_url": OFFICIAL, "extracted_at": "2021-01-02T00:00:00Z"},
    ])
    _, _, audit = reconstruct_total_return(raw, events(), ledger)
    assert audit.coverage_rate == 1.0
    assert audit.status == "passed"


def test_mixed_publication_timestamp_formats_are_valid() -> None:
    raw = pd.DataFrame({"date": ["2020-01-02", "2020-01-03"], "AAAA3": [10.0, 9.0]})
    corporate = events([
        ["div-1", "AAAA3", "dividend", "2020-01-03", 1.0, None, OFFICIAL,
         "2020-01-01T12:30:00+00:00", "confirmed"],
    ])
    _, _, audit = reconstruct_total_return(raw, corporate, coverage())
    assert audit.invalid_events == 0
