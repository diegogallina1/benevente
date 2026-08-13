import json

import pandas as pd

from brapi_total_return import build_brapi_total_return
from total_return_adapter import load_total_return_export


def response_for(url: str):
    if "bcdata.sgs.12" in url:
        payload = [{"data": "02/01/2013", "valor": "0,03"}, {"data": "03/01/2013", "valor": "0,03"}]
    elif "dividends" in url:
        payload = {"results": [{"data": {"cashDividends": [{"label": "JCP"}], "stockDividends": [{"label": "DESDOBRAMENTO"}], "subscriptions": []}}]}
    else:
        payload = {"results": [{"data": {"historicalDataPrice": [
            {"date": 1357092000, "adjustedClose": 10}, {"date": 1357178400, "adjustedClose": 10.5},
            {"date": 1357264800, "adjustedClose": None},
        ]}}]}
    raw = json.dumps(payload).encode("utf-8")
    return raw, payload


def test_brapi_builder_archives_events_and_allows_sparse_asset_history(tmp_path):
    output, manifest, coverage = tmp_path / "prices.csv", tmp_path / "manifest.json", tmp_path / "coverage.csv"
    prices, report, metadata = build_brapi_total_return(
        ["AAAA3.SA"], "2013-01-01", "2013-01-03", output, manifest, coverage, tmp_path / "raw", fetch=response_for,
    )
    assert report.iloc[0].cash_dividends_jcp_events == 1
    assert (tmp_path / "raw" / "events" / "AAAA3.json").exists()
    assert metadata["source_tier"] == "public_reproducible_research"
    loaded, _ = load_total_return_export(output, manifest)
    assert loaded.TITULO_CDI.notna().all()
    assert prices.columns.tolist() == ["date", "AAAA3.SA", "TITULO_CDI"]


def test_total_return_adapter_allows_ipo_gaps_but_not_cdi_gaps(tmp_path):
    prices = tmp_path / "prices.csv"; manifest = tmp_path / "manifest.json"
    pd.DataFrame({"date": ["2020-01-02", "2020-01-03"], "AAAA3.SA": [None, 100], "TITULO_CDI": [100, 100.1]}).to_csv(prices, index=False)
    from total_return_adapter import file_sha256
    manifest.write_text(json.dumps({"price_basis": "total_return", "provider": "test", "extraction_timestamp": "x",
                                    "coverage_start": "x", "coverage_end": "x", "corporate_actions": "x", "cdi_source": "x",
                                    "file_sha256": file_sha256(prices)}), encoding="utf-8")
    loaded, _ = load_total_return_export(prices, manifest)
    assert loaded["AAAA3.SA"].isna().sum() == 1


def test_brapi_request_adds_authorization_only_when_token_is_configured(monkeypatch):
    from brapi_total_return import _download_json

    captured = {}
    class Response:
        content = b'{"ok": true}'
        def raise_for_status(self): return None
    def get_request(url, headers, timeout):
        captured["authorization"] = headers.get("Authorization")
        return Response()
    monkeypatch.setattr("requests.get", get_request)
    monkeypatch.setenv("BRAPI_TOKEN", "secret-test-token")
    _, payload = _download_json("https://example.test/data")
    assert captured["authorization"] == "Bearer secret-test-token"
    assert payload["ok"] is True


def test_brapi_token_can_be_loaded_from_ignored_local_env(tmp_path, monkeypatch):
    monkeypatch.delenv("BRAPI_TOKEN", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.local").write_text("OPENAI_API_KEY=separate\nBRAPI_TOKEN=brapi-local-token\n", encoding="utf-8")
    from brapi_total_return import brapi_token
    assert brapi_token() == "brapi-local-token"
