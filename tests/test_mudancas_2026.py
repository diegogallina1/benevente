# -*- coding: utf-8 -*-
"""O que mudou em cada carteira: a lista que a página mostra ao abrir o cartão.

Este arquivo existe para que a página não precise da série diária inteira, que
tem 249 KB por perfil. O risco de resumir é publicar um resumo que não bate com
a série de onde ele saiu, e é isso que os testes abaixo impedem.
"""
from __future__ import annotations

from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PERFIS = ("conservador", "equilibrado", "arrojado")


@pytest.fixture(scope="module")
def resumo() -> dict:
    caminho = WEB / "mudancas_2026.json"
    assert caminho.exists(), "rode tools/build_changes_2026_web.py"
    return json.loads(caminho.read_text(encoding="utf-8"))


@pytest.mark.parametrize("perfil", PERFIS)
def test_o_resumo_bate_com_a_serie_diaria(resumo, perfil):
    serie = json.loads((WEB / f"live_performance_{perfil}.json").read_text(encoding="utf-8"))["series"]
    esperadas = [(serie[i]["date"], serie[i - 1]["risk_state"], serie[i]["risk_state"])
                 for i in range(1, len(serie))
                 if serie[i]["risk_state"] != serie[i - 1]["risk_state"]]
    publicadas = [(m["date"], m["from_state"], m["to_state"])
                  for m in resumo["profiles"][perfil]["changes"]]
    assert publicadas == esperadas, perfil
    assert resumo["profiles"][perfil]["through"] == serie[-1]["date"], perfil


@pytest.mark.parametrize("perfil", PERFIS)
def test_o_sinal_e_lido_antes_de_ser_executado(resumo, perfil):
    """A ordem entra no pregão seguinte ao fechamento que disparou o sinal.
    Publicar as duas datas como uma só faria a carteira parecer reagir no mesmo
    instante, que é promessa que nenhum sistema real cumpre."""
    for m in resumo["profiles"][perfil]["changes"]:
        assert m["observed_on"] < m["date"], (perfil, m)


@pytest.mark.parametrize("perfil", PERFIS)
def test_o_motivo_cita_o_limite_que_foi_cruzado(resumo, perfil):
    """"Por que mudou" tem de ser o número contra o limite declarado, não uma
    frase genérica sobre o mercado."""
    cfg = resumo["profiles"][perfil]["thresholds"]
    assert {"alert_drawdown", "alert_volatility", "recovery_days"} <= set(cfg)
    for m in resumo["profiles"][perfil]["changes"]:
        assert "limite" in m["why"], (perfil, m["why"])
        assert "%" in m["why"], (perfil, m["why"])


def test_o_passo_diario_publica_as_mudancas():
    fluxo = (ROOT / ".github" / "workflows" / "update-live-performance.yml"
             ).read_text(encoding="utf-8")
    assert "tools/build_changes_2026_web.py" in fluxo
    assert "web/mudancas_2026.json" in fluxo


def test_a_pagina_le_o_arquivo_resumido_e_nao_a_serie():
    """Buscar as três séries diárias custaria 750 KB para listar uma mudança."""
    js = (WEB / "carteira2026.js").read_text(encoding="utf-8")
    assert "mudancas_2026.json" in js
    assert "live_performance_" not in js


@pytest.mark.parametrize("perfil", PERFIS)
def test_o_estado_de_hoje_fecha_em_cem_por_cento(resumo, perfil):
    """Ações mais global mais CDI é a carteira inteira. Se não fechar, algum dos
    três está sendo publicado errado, e o erro apareceria como um peso que a
    pessoa não consegue conciliar com o extrato."""
    n = resumo["profiles"][perfil]["now"]
    assert abs(n["equity_br"] + n["global"] + n["cdi"] - 1.0) < 1e-3, perfil
    assert abs(n["equity_br_january"] + n["global"] + n["cdi_january"] - 1.0) < 1e-3, perfil


@pytest.mark.parametrize("perfil", PERFIS)
def test_a_camada_multiplica_todas_as_acoes_pelo_mesmo_fator(resumo, perfil):
    """A camada não escolhe ativo: ela reduz a perna de ações inteira na mesma
    proporção. Um fator por ativo significaria seleção durante o ano, que é
    exatamente o que a política declara não fazer."""
    n = resumo["profiles"][perfil]["now"]
    acoes = [h for h in n["holdings"] if h["ticker"] != "IVVB11"]
    for h in acoes:
        assert abs(h["now"] - h["january"] * n["factor"]) < 5e-4, (perfil, h["ticker"])
    globais = [h for h in n["holdings"] if h["ticker"] == "IVVB11"]
    for h in globais:
        assert h["now"] == h["january"], "a perna global não é tocada pelo sinal doméstico"


@pytest.mark.parametrize("perfil", PERFIS)
def test_o_que_sai_das_acoes_entra_no_cdi(resumo, perfil):
    for m in resumo["profiles"][perfil]["changes"]:
        saiu = m["from_equity"] - m["to_equity"]
        entrou = m["to_cdi"] - m["from_cdi"]
        assert abs(saiu - entrou) < 1e-3, (perfil, m["date"])


def test_a_pagina_mostra_o_peso_de_hoje_e_nao_so_o_de_janeiro():
    """O defeito que este teste impede: a tabela mostrar a decisão de janeiro
    com cara de posição atual, depois que a camada já mexeu nos pesos."""
    js = (WEB / "carteira2026.js").read_text(encoding="utf-8")
    assert "Composição de hoje" in js
    assert "agora.cdi" in js and "h.now" in js
