# -*- coding: utf-8 -*-
"""O monitor diário depois do audit: quatro contas que saíam erradas e caladas.

1. O alvo da próxima sessão usava o teto fixo do livro antigo enquanto a série
   usava o multiplicador do perfil: no alerta, o mesmo registro dizia "cortou
   45%" e "manter" ao mesmo tempo.
2. O retorno da perna de ações dividia o valor de todas as posições pelo peso só
   doméstico, e publicava ~26% em todos os perfis.
3. O Benevente 2 escalava o excesso inteiro sobre o caixa, inclusive o da perna
   global que a política declara isenta da camada.
4. Pregões sem preço em algum papel sumiam da série inteira e o arquivo dizia
   missing_tickers vazio, escrito no código.

Cada teste abaixo reprova a versão anterior.
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "update_live_performance", ROOT / "tools" / "update_live_performance.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def _entradas(com_falta: bool = False):
    """Uma carteira com perna doméstica, perna global isenta e caixa."""
    decision = {
        "decision_date": "2026-01-02",
        "holdings": [
            {"ticker": "AAA3", "weight": 0.30},
            {"ticker": "BBB3", "weight": 0.10},
            {"ticker": "IVVB11", "weight": 0.10},
        ],
        "cdi_weight": 0.50,
        "overlay_exempt": ["IVVB11"],
        "overlay": {"config": dict(MODULE.B2_CONFIG), "multipliers": [0.55, 0.25]},
    }
    dias = ["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"]
    series = {
        "AAA3": dict(zip(dias, [10.0, 11.0, 12.0, 12.5])),
        "BBB3": dict(zip(dias, [20.0, 18.0, 20.0, 21.0])),
        "IVVB11": dict(zip(dias, [50.0, 55.0, 60.0, 66.0])),
        "BOVA11": dict(zip(dias, [100.0, 105.0, 110.0, 112.0])),
        "IBOVESPA": dict(zip(dias, [100_000.0, 102_000.0, 103_000.0, 104_000.0])),
    }
    if com_falta:
        del series["BBB3"]["2026-01-06"]
    cdi = {d: 0.001 for d in dias}
    return decision, series, cdi


def _documento(**kw):
    decision, series, cdi = _entradas(**kw)
    return MODULE.build_live_document(
        decision, series, cdi, {"fixture": "0" * 64},
        generated_at=datetime(2026, 1, 8, tzinfo=timezone.utc))


def test_o_retorno_da_perna_de_acoes_usa_o_mesmo_peso_no_numerador_e_no_denominador():
    doc = _documento()
    # 0,30 → 12,5/10 ; 0,10 → 21/20 ; 0,10 → 66/50, sobre 0,50 de ações no total.
    esperado = (0.30 * 1.25 + 0.10 * 1.05 + 0.10 * 1.32) / 0.50 - 1.0
    assert doc["summary"]["equity_sleeve_return"] == pytest.approx(esperado)
    # A versão anterior dividia por 0,40 e publicava um número um quarto maior.
    assert doc["summary"]["equity_sleeve_return"] < (0.30 * 1.25 + 0.10 * 1.05 + 0.10 * 1.32) / 0.40 - 1.0


def test_o_alvo_da_proxima_sessao_sai_da_mesma_regra_que_a_exposicao_corrente():
    doc = _documento()
    camada = doc["benevente2_overlay"]
    estado = camada["next_session_risk_state"]
    fator = {"normal": 1.0, "alerta": 0.55, "severo": 0.25}[estado]
    # 0,40 é a parcela doméstica; a global não entra na conta da camada.
    assert camada["next_session_equity_weight"] == pytest.approx(0.40 * fator)


def test_com_multiplicador_um_a_decomposicao_por_perna_reproduz_a_carteira():
    """Sem corte, Benevente 2 é a própria carteira. É a igualdade que a fórmula
    decomposta precisa manter para valer como generalização da anterior."""
    doc = _documento()
    for linha in doc["series"]:
        if doc["benevente2_overlay"]["current_risk_state"] == "normal":
            # custo zero e multiplicador um: as duas séries coincidem
            assert linha["benevente2"] == pytest.approx(linha["portfolio"], abs=1e-6)


def test_a_perna_global_nao_e_cortada_pela_camada():
    """Com multiplicador abaixo de um, o excesso da perna global segue inteiro."""
    decision, series, cdi = _entradas()
    rows = [{"date": d, "portfolio": p, "domestic": dm, "global": g, "cdi": c, "ibovespa_price": i}
            for d, p, dm, g, c, i in [
                ("2026-01-02", 100.0, 40.0, 10.0, 100.0, 100.0),
                ("2026-01-05", 101.0, 40.0, 11.0, 100.1, 100.0),   # só a global subiu
            ]]
    config = {**MODULE.B2_CONFIG, "cost_bps": 0.0}
    # Força estado de alerta desde o início para o multiplicador morder.
    config = {**config, "alert_drawdown": -1.0}
    _, b2 = MODULE.apply_benevente2_overlay(rows, 0.40, config, (0.55, 0.25))
    ultimo = rows[-1]
    cdi_r = 0.001
    # O que a global rendeu além do caixa entra inteiro. O doméstico ficou
    # parado enquanto o caixa rendeu, então o excesso dele é negativo, e a
    # camada mantém 55% desse excesso: os outros 45% viraram caixa.
    glob_contrib = (11.0 - 10.0) / 100.0
    dom_excesso = 0.0 - (40.0 / 100.0) * cdi_r
    esperado = cdi_r + 0.55 * dom_excesso + (glob_contrib - (10.0 / 100.0) * cdi_r)
    assert ultimo["benevente2"] / 100.0 - 1.0 == pytest.approx(esperado, abs=1e-9)


def test_pregao_sem_preco_em_um_papel_aparece_como_falta_e_nao_como_serie_mais_curta():
    doc = _documento(com_falta=True)
    qualidade = doc["data_quality"]
    assert qualidade["dropped_sessions"] == 1
    faltas = {f["ticker"]: f for f in qualidade["missing_tickers"]}
    assert set(faltas) == {"BBB3"}
    assert faltas["BBB3"]["missing_sessions"] == 1
    assert faltas["BBB3"]["first"] == "2026-01-06"
    # E a série publicada de fato perdeu o dia: a contagem descreve o arquivo.
    assert all(linha["date"] != "2026-01-06" for linha in doc["series"])
