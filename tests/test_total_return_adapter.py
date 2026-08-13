import json

import pandas as pd
import pytest

from total_return_adapter import file_sha256, load_total_return_export


def test_total_return_export_requires_a_matching_attribution_manifest(tmp_path):
    prices = tmp_path / "total_return.csv"; manifest = tmp_path / "manifest.json"
    pd.DataFrame({"date": ["2020-01-02"], "AAAA3.SA": [100.0], "TITULO_CDI": [100.0]}).to_csv(prices, index=False)
    metadata = {
        "price_basis": "total_return", "provider": "test", "extraction_timestamp": "2020-01-03T00:00:00Z",
        "coverage_start": "2020-01-02", "coverage_end": "2020-01-02", "corporate_actions": "included",
        "cdi_source": "test", "file_sha256": file_sha256(prices),
    }
    manifest.write_text(json.dumps(metadata), encoding="utf-8")
    loaded, _ = load_total_return_export(prices, manifest)
    assert loaded.columns.tolist() == ["date", "AAAA3.SA", "TITULO_CDI"]
    metadata["file_sha256"] = "not-the-real-hash"; manifest.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="hash"):
        load_total_return_export(prices, manifest)
