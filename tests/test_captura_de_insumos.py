"""A captura dos insumos vale como prova, ou não vale nada.

A decisão de um ano precisa continuar reproduzível anos depois. Dois dos quatro
insumos mudam sozinhos com o tempo: o painel de fundamentos ganha formulários e
pode revisar registros antigos, e o de preços é reconstruído a cada carga do
COTAHIST. Por isso a captura guarda os bytes, e não só o hash deles.

Estes testes cobrem as três propriedades que fazem dela uma prova: ela recusa
captura incompleta ou de data errada, ela detecta alteração posterior, e a
carteira sai igual quando gerada a partir dela.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CAPTURA_2026 = ROOT / "artifacts" / "insumos_2026"


def _modulo():
    spec = importlib.util.spec_from_file_location(
        "capturar_insumos", ROOT / "tools" / "capturar_insumos.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_a_captura_publicada_confere() -> None:
    """Silêncio é o resultado bom: os bytes são os do dia."""
    if not CAPTURA_2026.exists():
        pytest.skip("a captura de 2026 não está neste clone")
    assert _modulo().conferir(CAPTURA_2026) == []


def test_alterar_um_insumo_capturado_e_detectado(tmp_path) -> None:
    """Uma captura que não detecta alteração não prova coisa alguma."""
    if not CAPTURA_2026.exists():
        pytest.skip("a captura de 2026 não está neste clone")
    modulo = _modulo()
    copia = tmp_path / "insumos"
    shutil.copytree(CAPTURA_2026, copia)
    alvo = next(p for p in copia.glob("*.csv"))
    alvo.write_bytes(alvo.read_bytes() + b"\n# alteracao posterior\n")
    problemas = modulo.conferir(copia)
    assert any(alvo.name in linha for linha in problemas), problemas


def test_mexer_no_manifesto_tambem_e_detectado(tmp_path) -> None:
    """O manifesto guarda o próprio hash: reescrevê-lo não passa despercebido."""
    if not CAPTURA_2026.exists():
        pytest.skip("a captura de 2026 não está neste clone")
    modulo = _modulo()
    copia = tmp_path / "insumos"
    shutil.copytree(CAPTURA_2026, copia)
    caminho = copia / modulo.MANIFESTO
    documento = json.loads(caminho.read_text(encoding="utf-8"))
    documento["decision_date"] = "2027-01-04"
    caminho.write_text(json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8")
    problemas = modulo.conferir(copia)
    assert any("manifesto" in linha for linha in problemas), problemas


def test_a_captura_recusa_data_que_nao_bate_com_o_retrato(tmp_path) -> None:
    """O retrato do universo é o que amarra a decisão à data.

    Capturar um retrato de outro dia produziria uma carteira que parece certa e
    não é, e isso é pior do que não capturar.
    """
    modulo = _modulo()
    # Todos os insumos precisam existir para esta recusa ser a que dispara: com
    # algum faltando, a que vem antes é a de insumo ausente. O painel de preços
    # não é versionado, então num clone limpo este teste é pulado.
    faltando = [item["arquivo"] for item in modulo.INSUMOS.values()
                if not (ROOT / item["arquivo"]).exists()]
    if faltando:
        pytest.skip(f"insumo fora do clone: {faltando}")
    with pytest.raises(SystemExit) as erro:
        modulo.capturar("2099-01-04", tmp_path / "insumos")
    assert "retrato do universo" in str(erro.value)


def test_a_captura_recusa_insumo_ausente(tmp_path, monkeypatch) -> None:
    """Publicar carteira a partir de insumo faltando é o pior modo de falha."""
    modulo = _modulo()
    inventado = dict(modulo.INSUMOS)
    inventado["prices"] = dict(inventado["prices"], arquivo="data/arquivo_que_nao_existe.csv")
    monkeypatch.setattr(modulo, "INSUMOS", inventado)
    with pytest.raises(SystemExit) as erro:
        modulo.capturar("2026-01-02", tmp_path / "insumos")
    assert "insumo ausente" in str(erro.value)


def test_o_manifesto_descreve_cada_insumo_e_quem_o_produz() -> None:
    """A lista de compras de qualquer ano vive junto de quem a usa."""
    if not CAPTURA_2026.exists():
        pytest.skip("a captura de 2026 não está neste clone")
    modulo = _modulo()
    manifesto = json.loads((CAPTURA_2026 / modulo.MANIFESTO).read_text(encoding="utf-8"))
    assert manifesto["decision_date"] == "2026-01-02"
    assert len(manifesto["files"]) == len(modulo.INSUMOS)
    for item in manifesto["files"]:
        assert item["produzido_por"], f"{item['arquivo']} não diz quem o produz"
        assert item["descricao"], f"{item['arquivo']} não diz o que é"
        assert len(item["sha256"]) == 64
    # Os dois que mudam sozinhos são exatamente os que tornam a cópia necessária.
    mutaveis = {item["papel"] for item in manifesto["files"] if item["muda_sozinho"]}
    assert mutaveis == {"prices", "fundamentals"}, mutaveis
