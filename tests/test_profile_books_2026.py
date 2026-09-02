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
# A escada e o registro vêm da política, não de uma tupla e de um caminho
# escritos aqui. Escritos à mão, este arquivo testava três livros contra a v3
# enquanto o site publicava quatro sob a v4, e o quarto degrau ficou sem
# propriedade nenhuma testada.
import sys
sys.path.insert(0, str(ROOT / "tools"))
from politica import REGISTRO as CAMINHO_DO_REGISTRO, escada  # noqa: E402

PERFIS = tuple(escada())
REGISTRO = json.loads(CAMINHO_DO_REGISTRO.read_text(encoding="utf-8"))


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
    # Na ordem da escada, do degrau mais apertado ao mais solto: a parcela em
    # ações cresce a cada degrau e o número de emissores não cresce. Escrita
    # com três nomes, a comparação nunca olhava o degrau que a política acrescentou.
    acoes = [sum(h["weight"] for h in livros[p]["holdings"] if h["ticker"] != "IVVB11") for p in PERFIS]
    emissores = [len([h for h in livros[p]["holdings"] if h["ticker"] != "IVVB11"]) for p in PERFIS]
    assert all(a < b for a, b in zip(acoes, acoes[1:])), dict(zip(PERFIS, acoes))
    assert all(a >= b for a, b in zip(emissores, emissores[1:])), dict(zip(PERFIS, emissores))


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


def test_a_camada_aplicada_e_a_camada_registrada(livros, acompanhamento) -> None:
    """O monitor tinha as constantes do livro anterior e ninguém percebeu.

    A regra aposentada expressa a camada como teto — no alerta, ações não passam
    de 50%. A escada declarada expressa como multiplicador por perfil. Aplicar o
    teto de 50% a um livro de 44% não corta nada: o acompanhamento publicava
    "estado alerta" com a exposição intacta, dizendo estar protegido sem ter
    vendido um real. Os dois números abaixo são a diferença entre descrever a
    política e executá-la.
    """
    from portfolio_risk import risk_profile_spec

    esperado = REGISTRO["intrayear_overlay"]["config"]
    for perfil, doc in acompanhamento.items():
        camada = doc["benevente2_overlay"]
        for chave, valor in esperado.items():
            assert camada["configuration"][chave] == pytest.approx(valor), f"{perfil}.{chave}"
        spec = risk_profile_spec(perfil)
        assert camada["profile_multipliers"]["alerta"] == pytest.approx(spec.alert_multiplier)
        assert camada["profile_multipliers"]["severo"] == pytest.approx(spec.severe_multiplier)

        # E a exposição publicada tem que ser o alvo vezes o multiplicador do
        # estado, não um teto que por acaso não morde.
        acoes = sum(h["weight"] for h in livros[perfil]["holdings"] if h["ticker"] != "IVVB11")
        fator = {"normal": 1.0, "alerta": spec.alert_multiplier, "severo": spec.severe_multiplier}
        estado = camada["current_risk_state"]
        assert camada["current_equity_weight"] == pytest.approx(acoes * fator[estado], abs=1e-6), (
            f"{perfil}: exposição publicada não é o alvo vezes o multiplicador de '{estado}'")
