import json
from pathlib import Path

import build_release_manifest as release


def test_release_manifest_contract(tmp_path: Path) -> None:
    output = tmp_path / "release_manifest.json"
    manifest = release.build()
    output.write_text(json.dumps(manifest), encoding="utf-8")

    assert manifest["names"]["academic"] == "Benevente Quant AI"
    assert manifest["names"]["commercial"] == "Benevente Wealth System"
    assert "Comparador quantitativo independente" in manifest["role_contract"]["mvo"]
    assert "não seleciona ativos" in manifest["role_contract"]["llm"]
    assert manifest["claims"]["strategy_cagr_net_costs"] > manifest["claims"]["cdi_cagr"]
    assert manifest["claims"]["strategy_cagr_net_costs"] > manifest["claims"]["mvo_reference_cagr"]
    assert release.verify(manifest) == []
