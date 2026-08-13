import pandas as pd

from total_return_adapter import load_total_return_export
from yahoo_total_return import build_yahoo_total_return


def fixture_history(symbol, start, end):
    index = pd.DatetimeIndex(["2013-01-02 00:00:00-02:00", "2013-01-03 00:00:00-02:00"])
    return pd.DataFrame({"Close": [10, 11], "Adj Close": [5, 5.5], "Dividends": [0, .2], "Stock Splits": [0, 0]}, index=index)


def bcb_fetch(url):
    payload = [{"data": "02/01/2013", "valor": "0,03"}, {"data": "03/01/2013", "valor": "0,03"}]
    import json
    return json.dumps(payload).encode(), payload


def test_yahoo_builder_archives_history_events_and_valid_total_return(tmp_path, monkeypatch):
    monkeypatch.setattr("yahoo_total_return._fetch_cdi", lambda start, end, raw: __import__("brapi_total_return")._fetch_cdi(start, end, raw, bcb_fetch))
    output, manifest, coverage = tmp_path / "prices.csv", tmp_path / "manifest.json", tmp_path / "coverage.csv"
    prices, report, metadata = build_yahoo_total_return(
        ["AAAA3.SA"], "2013-01-01", "2013-01-03", output, manifest, coverage, tmp_path / "raw", pause_seconds=0,
        fetch_history=fixture_history,
    )
    assert prices.columns.tolist() == ["date", "AAAA3", "TITULO_CDI"]
    assert report.iloc[0].cash_dividend_events == 1
    assert (tmp_path / "raw" / "history" / "AAAA3.SA.csv").exists()
    assert (tmp_path / "raw" / "events" / "AAAA3.SA.csv").exists()
    loaded, _ = load_total_return_export(output, manifest)
    assert loaded.TITULO_CDI.notna().all()
    assert metadata["source_tier"] == "public_reproducible_research"


def test_yahoo_builder_resumes_from_archived_history(tmp_path, monkeypatch):
    monkeypatch.setattr("yahoo_total_return._fetch_cdi", lambda start, end, raw: __import__("brapi_total_return")._fetch_cdi(start, end, raw, bcb_fetch))
    common = dict(tickers=["AAAA3.SA"], start="2013-01-01", end="2013-01-03", raw_dir=tmp_path / "raw", pause_seconds=0)
    build_yahoo_total_return(output_path=tmp_path / "first.csv", manifest_path=tmp_path / "first.json", coverage_path=tmp_path / "first_coverage.csv", fetch_history=fixture_history, **common)
    def should_not_download(*_): raise AssertionError("cache was not used")
    _, report, _ = build_yahoo_total_return(output_path=tmp_path / "second.csv", manifest_path=tmp_path / "second.json", coverage_path=tmp_path / "second_coverage.csv", fetch_history=should_not_download, **common)
    assert bool(report.iloc[0].from_cache)


def test_yahoo_normalises_mixed_daylight_saving_offsets():
    from yahoo_total_return import _normalise_history
    history = pd.DataFrame({"Adj Close": [10, 11]}, index=["2013-01-02 00:00:00-02:00", "2013-07-02 00:00:00-03:00"])
    series, _ = _normalise_history(history, "AAAA3.SA", pd.Timestamp("2013-01-01"), pd.Timestamp("2013-12-31"))
    assert series.index.tolist() == [pd.Timestamp("2013-01-02"), pd.Timestamp("2013-07-02")]


def test_yahoo_export_uses_canonical_b3_ticker_without_yahoo_suffix(tmp_path, monkeypatch):
    monkeypatch.setattr("yahoo_total_return._fetch_cdi", lambda start, end, raw: __import__("brapi_total_return")._fetch_cdi(start, end, raw, bcb_fetch))
    prices, report, _ = build_yahoo_total_return(
        ["AAAA3.SA"], "2013-01-01", "2013-01-03", tmp_path / "prices.csv", tmp_path / "manifest.json",
        tmp_path / "coverage.csv", tmp_path / "raw", pause_seconds=0, fetch_history=fixture_history,
    )
    assert "AAAA3" in prices.columns
    assert report.loc[0, "ticker"] == "AAAA3"
    assert report.loc[0, "source_symbol"] == "AAAA3.SA"


def test_yahoo_builder_defers_uncached_tickers_after_batch_limit(tmp_path, monkeypatch):
    monkeypatch.setattr("yahoo_total_return._fetch_cdi", lambda start, end, raw: __import__("brapi_total_return")._fetch_cdi(start, end, raw, bcb_fetch))
    _, report, metadata = build_yahoo_total_return(
        ["AAAA3.SA", "BBBB3.SA"], "2013-01-01", "2013-01-03", tmp_path / "prices.csv", tmp_path / "manifest.json",
        tmp_path / "coverage.csv", tmp_path / "raw", pause_seconds=0, download_limit=1, fetch_history=fixture_history,
    )
    assert metadata["newly_downloaded_tickers"] == 1
    assert metadata["deferred_tickers"] == 1
    assert report.status.tolist() == ["accepted", "deferred"]
