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
    assert "PROTÓTIPO DE PESQUISA" in home
    assert "Matriz de Evidências" in home
    assert "Ver os 7 defeitos corrigidos" in home
    assert "ba2d7b436fc4ca24ed129af61a8331ec8e2a463d3f1c4d7f639ef98336f9d56d" in home
    assert "Reproduzir no GitHub" in home
    assert "O Benevente separa o que calcula, o que explica e o que decide" in home
    assert "sensibilidade, não prova de descontaminação" in home
    assert "a queda máxima passou de 30,4% para 47,8%" in home
    assert "fidelidade" in home.lower() and "números inventados" in home.lower()


def test_site_data_contract_matches_canonical_sources() -> None:
    contract = json.loads((ROOT / "web" / "data_contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "web" / "research_manifest.json").read_text(encoding="utf-8"))
    universe = json.loads((ROOT / "web" / "b3_universe.json").read_text(encoding="utf-8"))
    protocol_path = ROOT / "artifacts" / "published_nested" / "protocol.json"

    assert contract["research_window"]["annual_decisions"] == manifest["evaluation"]["annual_decisions"]
    assert contract["historical_panel"]["evaluated_distinct_issuers"] == manifest["coverage"]["evaluated_distinct_issuers"]
    assert contract["historical_panel"]["price_series"] == manifest["coverage"]["price_tickers"]
    assert contract["historical_panel"]["fundamental_records"] == manifest["coverage"]["fundamental_records"]
    assert contract["current_b3_catalog"]["instruments"] == universe["instrument_count"]
    assert contract["current_b3_catalog"]["observed_at"] == universe["observed_at"]
    assert contract["corporate_events"]["primary_records"] == manifest["coverage"]["primary_event_records"]
    assert contract["corporate_events"]["covered_price_series"] == manifest["coverage"]["primary_event_tickers_complete"]
    assert contract["prospective_protocol"]["sha256"] == __import__("hashlib").sha256(protocol_path.read_bytes()).hexdigest()


def test_site_uses_honest_language_model_and_cadence_claims() -> None:
    home = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    method = (ROOT / "web" / "metodo.html").read_text(encoding="utf-8")
    quant = (ROOT / "web" / "quant-ai.html").read_text(encoding="utf-8")
    combined = home + method
    assert "look-ahead bias / viés de antecipação" in combined
    assert "Não há evidência de contaminação temporal" not in method
    assert "teste de sensibilidade, não prova de descontaminação" in method
    assert "does not reject a benefit in other periods" in quant


def test_public_site_text_is_utf8_and_has_no_placeholder_metrics() -> None:
    text_extensions = {".html", ".js", ".css", ".json"}
    for path in (ROOT / "web").rglob("*"):
        if path.suffix.lower() not in text_extensions:
            continue
        source = path.read_text(encoding="utf-8")
        assert "\ufffd" not in source, path
        if path.suffix.lower() in {".html", ".js"}:
            assert "NaN%" not in source, path
            assert "A recalcular" not in source, path


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
