# -*- coding: utf-8 -*-
"""A comparação de 2026: a faixa é de janeiro, o resultado é de hoje.

O defeito que estes testes existem para impedir é sutil e seria invisível na
tela: uma faixa recalculada com o ano em andamento acompanha o resultado e
nunca erra, então mede zero. O que a mantém honesta é vir de um artefato
congelado e nunca ser reescrita pelo passo diário.
"""
from __future__ import annotations

from pathlib import Path
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONE = ROOT / "artifacts" / "forecast_2026_cone_v1" / "cone.json"
WEB = ROOT / "web" / "forecast_2026.json"
PERFIS = ("conservador", "equilibrado", "arrojado")


@pytest.fixture(scope="module")
def publicado() -> dict:
    assert WEB.exists(), "rode tools/build_forecast_2026_web.py"
    return json.loads(WEB.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def artefato() -> dict:
    assert CONE.exists(), "rode research_forecast_2026_cone.py"
    return json.loads(CONE.read_text(encoding="utf-8"))


def test_a_faixa_publicada_e_copia_do_artefato(publicado, artefato):
    """Se o site recalculasse a faixa, ela deixaria de ser a de janeiro."""
    for perfil in PERFIS:
        assert publicado["profiles"][perfil]["band"] == artefato["profiles"][perfil]["band"], perfil


def test_a_faixa_so_usa_dado_anterior_ao_ano(artefato):
    assert "anteriores ao primeiro pregão de 2026" in artefato["method"]["point_in_time"]
    for perfil in PERFIS:
        # Dois anos de história é o mínimo que o estimador aceita; aqui há mais
        # de dez, e um número baixo aqui significaria janela errada.
        assert artefato["profiles"][perfil]["history_days"] > 2000, perfil


def test_a_faixa_cresce_com_o_horizonte(publicado):
    """Faixa que encolhe com o tempo denuncia reamostragem independente por
    ponto. Os caminhos são sorteados uma vez justamente para evitar isso."""
    for perfil in PERFIS:
        band = publicado["profiles"][perfil]["band"]
        larguras = [p["p90"] - p["p10"] for p in band]
        assert all(b >= a - 1e-9 for a, b in zip(larguras, larguras[1:])), perfil
        assert all(p["p10"] <= p["p50"] <= p["p90"] for p in band), perfil


def test_a_comparacao_e_no_mesmo_horizonte(publicado):
    """Comparar meio ano com a faixa do ano inteiro faria a carteira parecer
    atrasada só porque o ano não acabou. O ponto de comparação é o pregão."""
    for perfil in PERFIS:
        p = publicado["profiles"][perfil]
        agora, band = p["now"], p["band"]
        assert agora["sessions"] == p["realised"][-1]["sessions"], perfil
        assert agora["realised"] == p["realised"][-1]["r"], perfil
        assert band[0]["sessions"] <= agora["sessions"] <= band[-1]["sessions"], perfil
        # a faixa usada é a do horizonte decorrido, não a do ano cheio
        assert agora["p90"] < band[-1]["p90"], perfil
        assert agora["inside"] == (agora["p10"] <= agora["realised"] <= agora["p90"])


def test_a_pagina_nao_promete_retorno(publicado):
    """A faixa é instrumento de medição, e o texto publicado precisa dizer isso
    sem depender de quem lê ser generoso."""
    assert "não previsão de patrimônio" in publicado["status"]
    assert publicado["limitation"].strip()
    assert "não confirma a regra" in publicado["limitation"]


def test_o_passo_diario_publica_o_arquivo():
    """Gerar sem publicar deixaria o gráfico parado num dia antigo, e a página
    continuaria dizendo que é diária."""
    fluxo = (ROOT / ".github" / "workflows" / "update-live-performance.yml"
             ).read_text(encoding="utf-8")
    assert "tools/build_forecast_2026_web.py" in fluxo
    assert "web/forecast_2026.json" in fluxo
