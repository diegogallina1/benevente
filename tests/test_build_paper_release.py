import json
import re
from pathlib import Path

from tools.build_paper_release import build_bundle, write_release


def test_paper_release_reconciles_canonical_metrics() -> None:
    bundle = build_bundle()
    assert bundle["release_contract"]["canonical_strategy"] == "Benevente 1"
    assert bundle["release_contract"]["decision_count"] == 11
    assert round(bundle["published_strategy"]["cagr"], 4) == 0.1786
    assert round(bundle["published_strategy"]["daily_max_drawdown"], 4) == -0.4778
    assert round(bundle["benevente_2"]["cagr"], 4) == 0.1845
    assert bundle["llm_experiment"]["malformed_weight_years"] == 5


def test_paper_release_writes_strict_json(tmp_path: Path) -> None:
    write_release(tmp_path)
    evidence = json.loads((tmp_path / "paper_evidence.json").read_text(encoding="utf-8"))
    manifest = json.loads((tmp_path / "paper_release_manifest.json").read_text(encoding="utf-8"))
    assert evidence["benchmarks"]["cdi_cagr"] > 0
    assert manifest["status"] == "validated"


def test_final_manuscripts_obey_release_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    btech = (root / "paper" / "fucape_btech_2026.md").read_text(encoding="utf-8")
    ieee = (root / "paper" / "ieee_cifer_2027.tex").read_text(encoding="utf-8")

    # The official BTech range includes references.
    assert 6_000 <= len(re.findall(r"\w+", btech, flags=re.UNICODE)) <= 8_000
    assert "https://github.com/diegogallina1/benevente" in btech
    assert "benevente-wealth-system.vercel.app" in btech
    assert "pacote suplementar anônimo" not in btech.lower()
    assert "arquivo permanente com DOI" not in btech
    assert "ponto-no-tempo" not in btech.lower()
    assert "A completar" not in btech

    assert r"\documentclass[10pt,conference]{IEEEtran}" in ieee
    assert "an anonymised archive" in ieee
    assert r"\section*{Acknowledgment and generative-AI disclosure}" in ieee
    assert "The production artifact never uses this channel" in ieee
    assert "anonymisation cannot prove" in ieee.lower()
    assert "A completar" not in ieee
