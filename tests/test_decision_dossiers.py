"""O dossiê baixável é a promessa central do produto virando arquivo.

Se um ano ou perfil ficar sem PDF, o botão do explorador aponta para um 404 —
o pior defeito possível numa página cujo argumento é auditabilidade. Os testes
prendem o conjunto completo, o conteúdo mínimo de um exemplar e os três lugares
do site que apontam para os arquivos.
"""
from pathlib import Path
import json
import re

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DOSSIERS = ROOT / "web" / "dossiers"


def test_every_profile_year_has_a_dossier() -> None:
    composition = json.loads((ROOT / "web" / "composition.json").read_text(encoding="utf-8"))
    expected = {f"dossie_{profile}_{block['decision_year']}.pdf"
                for profile, blocks in composition["profiles"].items() for block in blocks}
    published = {path.name for path in DOSSIERS.glob("*.pdf")}
    assert expected == published
    assert len(expected) == 33
    small = [path.name for path in DOSSIERS.glob("*.pdf") if path.stat().st_size < 40_000]
    assert not small, f"PDF suspeito de truncado: {small}"


def test_sample_dossier_carries_the_contract() -> None:
    text = " ".join(page.extract_text() or ""
                    for page in PdfReader(DOSSIERS / "dossie_equilibrado_2025.pdf").pages)
    flat = re.sub(r"\s+", " ", text)
    assert "fc5521f11d133520" in flat            # hash do registro congelado
    assert "Diego Gallina" in flat               # aprovador nominal
    assert "RECONSTRUÇÃO RETROSPECTIVA" in flat  # honestidade sobre 2015-2025
    assert "SEPARADA DE PROPÓSITO" in flat       # fronteira da informação posterior
    assert "RETORNO NO CICLO SEGUINTE" in flat


def test_site_links_resolve_to_existing_files() -> None:
    ladder = (ROOT / "web" / "ladder.js").read_text(encoding="utf-8")
    assert "./dossiers/dossie_${activeProfile}_${activeYear}.pdf" in ladder
    for page in ("index.html", "para-escritorios.html"):
        source = (ROOT / "web" / page).read_text(encoding="utf-8")
        for match in re.findall(r'href="\./(dossiers/[^"]+\.pdf)"', source):
            assert (ROOT / "web" / match).exists(), match
    assert 'href="./dossiers/' in (ROOT / "web" / "index.html").read_text(encoding="utf-8")
