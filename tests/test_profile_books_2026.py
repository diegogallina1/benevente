"""A carteira de 2026 tem que ser a mesma política dos outros onze anos.

O site publicava onze anos reconstruídos nos três perfis e, para 2026, um livro
único herdado da configuração que a busca aninhada deixou viva antes de a
política existir. Um leitor não tinha como saber que a diferença estava lá. Os
testes abaixo prendem a correspondência entre o que o registro declara e o que
o acompanhamento diário publica.
"""
from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PERFIS = ("conservador", "equilibrado", "arrojado")
REGISTRO = json.loads((ROOT / "data" / "benevente_profile_ladder_v3_registration.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def livros():
    return {p: json.loads((WEB / f"current_decision_2026_{p}.json").read_text(encoding="utf-8")) for p in PERFIS}


@pytest.fixture(scope="module")
def acompanhamento():
    return {p: json.loads((WEB / f"live_performance_{p}.json").read_text(encoding="utf-8")) for p in PERFIS}


def test_os_tres_livros_seguem_a_politica_vigente(livros) -> None:
    for perfil, livro in livros.items():
        assert livro["policy"] == REGISTRO["policy"]
        assert livro["registration_sha256"] == REGISTRO["registration_sha256"]
        declarado = REGISTRO["profiles"][perfil]
        assert livro["declared"]["maximum_equity_weight"] == declarado["maximum_equity_weight"]
        assert livro["declared"]["top_assets"] == declarado["top_assets"]
        acoes = [h for h in livro["holdings"] if h["ticker"] != "IVVB11"]
        assert len(acoes) == declarado["top_assets"]


def test_a_perna_global_existe_e_e_isenta_da_camada(livros) -> None:
    """Cortar o fundo num sinal doméstico venderia o ativo a que ele não se aplica."""
    for perfil, livro in livros.items():
        global_ = [h for h in livro["holdings"] if h["ticker"] == "IVVB11"]
        assert len(global_) == 1
        esperado = REGISTRO["profiles"][perfil]["global_share_of_portfolio"]
        assert global_[0]["weight"] == pytest.approx(esperado, abs=5e-4)
        assert livro["overlay_exempt"] == ["IVVB11"]


def test_cada_livro_fecha_em_cem_por_cento(livros) -> None:
    for livro in livros.values():
        total = sum(h["weight"] for h in livro["holdings"]) + livro["cdi_weight"]
        assert total == pytest.approx(1.0, abs=1e-6)


def test_a_escada_de_risco_se_mantem_na_carteira_de_2026(livros) -> None:
    acoes = {p: sum(h["weight"] for h in l["holdings"] if h["ticker"] != "IVVB11")
             for p, l in livros.items()}
    assert acoes["conservador"] < acoes["equilibrado"] < acoes["arrojado"]
    emissores = {p: len([h for h in l["holdings"] if h["ticker"] != "IVVB11"]) for p, l in livros.items()}
    assert emissores["conservador"] > emissores["equilibrado"] > emissores["arrojado"]


def test_o_acompanhamento_declara_que_e_reconstrucao(livros) -> None:
    for livro in livros.values():
        assert "amostra confirmatória" in livro["honesty"]
        assert "2027" in livro["honesty"]
        assert any("proventos" in item for item in livro["limitations"])


def test_o_acompanhamento_diario_cobre_os_tres(acompanhamento) -> None:
    dias = {p: doc["through"] for p, doc in acompanhamento.items()}
    assert len(set(dias.values())) == 1, f"perfis em datas diferentes: {dias}"
    for doc in acompanhamento.values():
        assert doc["decision_date"] == "2026-01-02"
        assert len(doc["record_sha256"]) == 64


def test_a_home_carrega_a_carteira_do_ano(livros) -> None:
    home = (WEB / "index.html").read_text(encoding="utf-8")
    assert 'id="carteira-2026"' in home
    assert "carteira2026.js" in home
    # E vem depois do resultado retrospectivo, não antes: o leitor precisa saber
    # o que a política é antes de ver o que ela está fazendo agora.
    assert home.index('id="resultado"') < home.index('id="carteira-2026"')
