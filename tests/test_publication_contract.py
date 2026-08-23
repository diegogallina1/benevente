import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_has_static_evidence_and_research_stage() -> None:
    home = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "Carregando" not in home
    assert "PESQUISA EM DESENVOLVIMENTO" in home
    assert "O que está demonstrado e o que ainda não está" in home
    assert "Ver os 7 defeitos corrigidos" in home
    assert "ba2d7b436fc4ca24ed129af61a8331ec8e2a463d3f1c4d7f639ef98336f9d56d" in home
    assert "Abrir no GitHub" in home and "Como reproduzir" in home


def test_browser_bundle_has_one_hash_and_honest_approval_state_per_decision() -> None:
    bundle = json.loads((ROOT / "web" / "annual_research.json").read_text(encoding="utf-8"))
    assert len(bundle["annual"]) == 11
    for decision in bundle["annual"]:
        assert re.fullmatch(r"[0-9a-f]{64}", decision["decision_evidence_sha256"])
        assert "não houve aprovação humana" in decision["approval_status"]


def test_release_manifest_distinguishes_labels_from_evaluated_issuers() -> None:
    manifest = json.loads((ROOT / "web" / "research_manifest.json").read_text(encoding="utf-8"))
    assert manifest["coverage"]["evaluated_distinct_issuers"] == 514
    assert manifest["coverage"]["historical_issuer_labels"] == 2051
    assert "historical_issuers" not in manifest["coverage"]


def test_papers_share_the_language_model_boundary() -> None:
    btech = (ROOT / "paper" / "fucape_btech_2026.md").read_text(encoding="utf-8")
    ieee = (ROOT / "paper" / "ieee_cifer_2027.tex").read_text(encoding="utf-8")
    for name in ("Perlin", "Pelster", "Kim", "FINSABER"):
        assert name in btech
    assert "o modelo apenas explica fatos aprovados" in btech
    assert "There is no edge from $e_t$ to $S$, $A$ or $P$" in ieee
    assert "github.com/diegogallina1" not in ieee
    assert "benevente-wealth-system.vercel.app" not in ieee


def test_ieee_supplement_is_anonymous_and_self_manifested() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_ieee_anonymous_supplement.py")],
        cwd=ROOT,
        check=True,
    )
    archive_path = ROOT / "outputs" / "Benevente_Quant_AI_IEEE_Anonymous_Supplement.zip"
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert "README.md" in names
        assert "MANIFEST.sha256" in names
        assert "artifacts/published_nested/protocol.json" in names
        readable = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".md", ".json", ".py"))
        ).lower()
    assert "diegogallina" not in readable
    assert "github.com/" not in readable
    assert "benevente-wealth-system.vercel.app" not in readable
