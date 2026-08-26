"""A conexão com a B3 e a recusa em somar imposto que não se sabe apurar.

O risco que estes testes cobrem não é de cálculo, é de conveniência. A pressão
para preencher o custo faltante com uma estimativa vai existir sempre, porque a
tela fica mais bonita e o número fecha. Quando isso acontecer, algum destes
testes cai.
"""
from __future__ import annotations

from datetime import date

import pytest

from b3_connection import (BASE_COMECA_EM, COBERTURA, Consentimento, Negociacao,
                           Qualidade, reconstruir_custo, relatorio_de_lacunas)
from portfolio_mapping import Bucket, Position, Source, adapt_portfolio, map_portfolio

ALVO = {"positions": {"CURY3": 0.10, "CMIN3": 0.10, "BBSE3": 0.06},
        "global_sleeve": 0.11, "cash": 0.63}


# --- consentimento --------------------------------------------------------

def test_o_cpf_nunca_entra_no_registro():
    consentimento = Consentimento(Consentimento.anonimiza("123.456.789-09"), "Benevente",
                                  "2026-08-26T09:00:00-03:00", ("Posição",))
    registro = consentimento.registro()
    assert "12345678909" not in str(registro)
    assert len(registro["documento_hash"]) == 64
    assert registro["credencial_armazenada"] is False


def test_o_registro_declara_onde_se_revoga():
    """Um consentimento sem caminho de saída não é consentimento."""
    registro = Consentimento(Consentimento.anonimiza("12345678909"), "Benevente",
                             "2026-08-26T09:00:00-03:00", ("Posição",)).registro()
    assert "investidor.b3.com.br" in registro["revogavel_em"]


def test_documento_invalido_e_recusado():
    for ruim in ("123", "", "abc"):
        with pytest.raises(ValueError):
            Consentimento.anonimiza(ruim)


def test_o_registro_encadeia_no_anterior():
    primeiro = Consentimento(Consentimento.anonimiza("12345678909"), "Benevente",
                             "2026-08-26T09:00:00-03:00", ("Posição",)).registro()
    segundo = Consentimento(Consentimento.anonimiza("12345678909"), "Benevente",
                            "2026-09-26T09:00:00-03:00", ("Posição",),
                            registro_anterior_sha256=primeiro["registro_sha256"]).registro()
    assert segundo["registro_anterior_sha256"] == primeiro["registro_sha256"]
    assert segundo["registro_sha256"] != primeiro["registro_sha256"]


# --- reconstrução do custo ------------------------------------------------

def test_compras_dentro_da_base_dao_custo_reconstruido():
    custo = reconstruir_custo("CURY3", 4_000, [
        Negociacao("CURY3", date(2021, 3, 12), "compra", 2_500, 6.10),
        Negociacao("CURY3", date(2022, 8, 4), "compra", 1_500, 5.20)])
    assert custo.qualidade is Qualidade.RECONSTRUIDO
    assert custo.valor_brl == pytest.approx(2_500 * 6.10 + 1_500 * 5.20)
    assert custo.cobertura == 1.0


def test_posicao_anterior_a_base_fica_parcial_e_nao_apura():
    """O caso comum: ação boa comprada antes de 01/11/2019."""
    custo = reconstruir_custo("WEGE3", 3_000, [
        Negociacao("WEGE3", date(2023, 5, 18), "compra", 1_000, 38.00)])
    assert custo.qualidade is Qualidade.PARCIAL
    assert custo.qualidade.apura_imposto is False
    assert custo.cobertura == pytest.approx(1 / 3)
    assert f"{BASE_COMECA_EM:%d/%m/%Y}" in custo.observacao


def test_posicao_sem_nenhuma_negociacao_fica_ausente():
    custo = reconstruir_custo("PETR4", 1_000, [])
    assert custo.qualidade is Qualidade.AUSENTE
    assert custo.qualidade.apura_imposto is False


def test_venda_abate_ao_custo_medio():
    custo = reconstruir_custo("CURY3", 1_000, [
        Negociacao("CURY3", date(2021, 1, 4), "compra", 1_000, 10.00),
        Negociacao("CURY3", date(2021, 2, 4), "compra", 1_000, 20.00),
        Negociacao("CURY3", date(2021, 6, 4), "venda", 1_000, 30.00)])
    assert custo.qualidade is Qualidade.RECONSTRUIDO
    assert custo.valor_brl == pytest.approx(15_000.0)   # 1.000 ao médio de 15


def test_venda_sem_compra_conhecida_nao_inventa_ganho():
    """Abater ao custo zero criaria um ganho que a corretora anterior já tributou."""
    custo = reconstruir_custo("WEGE3", 500, [
        Negociacao("WEGE3", date(2020, 1, 6), "venda", 400, 40.00),
        Negociacao("WEGE3", date(2021, 1, 6), "compra", 500, 30.00)])
    assert custo.valor_brl == pytest.approx(15_000.0)
    assert custo.qualidade is Qualidade.RECONSTRUIDO


def test_o_relatorio_de_lacunas_nomeia_o_que_falta():
    custos = {t: reconstruir_custo(t, q, n) for t, q, n in [
        ("CURY3", 1_000, [Negociacao("CURY3", date(2021, 1, 4), "compra", 1_000, 10.0)]),
        ("WEGE3", 1_000, []),
    ]}
    lacunas = relatorio_de_lacunas(custos)
    assert lacunas["com_custo_defensavel"] == 1
    assert set(lacunas["pendentes"]) == {"WEGE3"}


def test_a_cobertura_declara_que_nao_ha_preco_medio():
    """Se algum dia houver endpoint de custo, este teste deve ser o primeiro a cair.

    Casa pelo sentido e não pela frase: o texto é voltado ao cliente e pode ser
    reescrito, mas a ausência do preço de compra tem de continuar declarada.
    """
    dito = " ".join(COBERTURA["nao_entrega"]).lower()
    assert "por quanto você comprou" in dito or "preço médio" in dito


# --- o mapa diante de um custo que não sustenta conta ---------------------

def carteira(qualidade: Qualidade) -> list[Position]:
    return [
        Position("WEGE3", Bucket.ACAO, 200_000, 38_000, Source.B3_INVESTIDOR,
                 cost_quality=qualidade),
        Position("CURY3", Bucket.ACAO, 40_000, 20_000, Source.B3_INVESTIDOR,
                 cost_quality=Qualidade.RECONSTRUIDO),
        Position("Tesouro Selic", Bucket.CAIXA, 160_000, 158_000, Source.B3_INVESTIDOR,
                 cost_quality=Qualidade.RECONSTRUIDO),
    ]


def test_custo_parcial_mantem_o_imposto_fora_da_soma_e_nomeado():
    mapa = map_portfolio(carteira(Qualidade.PARCIAL), ALVO)
    assert mapa["tax_is_complete"] is False
    assert [p["ticker"] for p in mapa["positions_without_cost_basis"]] == ["WEGE3"]
    assert mapa["unpriced_sale_brl"] == pytest.approx(200_000, abs=1)


def test_o_ganho_de_uma_posicao_de_custo_parcial_nao_e_publicado():
    """valor de mercado menos custo parcial não é ganho: é ficção grande."""
    mapa = map_portfolio(carteira(Qualidade.PARCIAL), ALVO)
    wege = next(m for m in mapa["moves"] if m["ticker"] == "WEGE3")
    assert wege["realised_gain_brl"] == 0.0
    assert any("ainda não calculado" in n for n in wege["notes"])


def test_com_custo_reconstruido_o_imposto_fecha():
    mapa = map_portfolio(carteira(Qualidade.RECONSTRUIDO), ALVO)
    assert mapa["tax_is_complete"] is True
    assert mapa["positions_without_cost_basis"] == []
    assert mapa["unpriced_sale_brl"] == 0


def test_a_lacuna_tem_o_tamanho_do_que_sai_nao_da_posicao():
    """Reduzir catorze mil de uma posição de duzentos mil não pendura duzentos mil."""
    mapa = adapt_portfolio(carteira(Qualidade.PARCIAL), ALVO)
    wege = next(m for m in mapa["moves"] if m["ticker"] == "WEGE3")
    vendido = wege["from_brl"] - wege["to_brl"]
    assert 0 < vendido < 200_000
    assert mapa["unpriced_sale_brl"] == pytest.approx(vendido, abs=1)


def test_o_custo_do_plano_incompleto_e_menor_que_o_completo():
    """É por isso que ele é publicado como piso: some imposto, não custo."""
    parcial = map_portfolio(carteira(Qualidade.PARCIAL), ALVO)
    completo = map_portfolio(carteira(Qualidade.RECONSTRUIDO), ALVO)
    assert parcial["transition_total_brl"] < completo["transition_total_brl"]
    assert parcial["tax_is_complete"] is False and completo["tax_is_complete"] is True


# --- o campo que informa o custo que falta -------------------------------

def resolver(resolucao: dict, custos: dict[str, float]) -> float:
    """A aritmética que a tela faz quando o custo é informado.

    Escrita aqui em Python e transcrita literalmente para o JavaScript do
    protótipo. O teste abaixo compara o resultado dela com o do módulo de
    verdade em vários valores de custo: é o que impede as duas implementações
    de divergirem em silêncio, cada uma continuando plausível sozinha.
    """
    total = resolucao["fixed_brl"]
    for cesta, cfg in resolucao["buckets"].items():
        ganho = cfg["other_gain_brl"]
        for p in resolucao["positions"]:
            if p["bucket"] == cesta:
                ganho += p["sale_brl"] - custos[p["ticker"]] * p["sale_fraction"]
        ganho -= cfg["carried_loss_brl"]
        if ganho <= 0 or cesta == "fora_do_escopo" or cfg["exempt_month"]:
            continue
        total += ganho * cfg["rate"]
    return total


@pytest.mark.parametrize("custo", [0, 38_000, 90_000, 150_000, 200_000, 400_000])
@pytest.mark.parametrize("fn", [map_portfolio, adapt_portfolio])
def test_a_conta_da_tela_bate_com_a_do_modulo(fn, custo):
    """Informar o custo pela tela tem de dar o mesmo que o módulo calcularia."""
    pendente = fn(carteira(Qualidade.PARCIAL), ALVO)
    previsto = resolver(pendente["pending_resolution"], {"WEGE3": custo})

    informado = fn([p if p.ticker != "WEGE3" else
                    Position("WEGE3", Bucket.ACAO, 200_000, custo, Source.B3_INVESTIDOR,
                             cost_quality=Qualidade.DECLARADO)
                    for p in carteira(Qualidade.PARCIAL)], ALVO)
    assert informado["tax_is_complete"] is True
    assert previsto == pytest.approx(informado["transition_total_brl"], abs=0.02)


def test_sem_pendencia_nao_ha_o_que_resolver():
    assert map_portfolio(carteira(Qualidade.RECONSTRUIDO), ALVO)["pending_resolution"] == {}


def test_a_resolucao_separa_o_que_nao_depende_do_custo():
    """fixed_brl é execução mais imposto das cestas sem pendência."""
    mapa = map_portfolio(carteira(Qualidade.PARCIAL), ALVO)
    r = mapa["pending_resolution"]
    assert r["fixed_brl"] >= mapa["transition_cost_brl"]
    assert [p["ticker"] for p in r["positions"]] == ["WEGE3"]
    assert set(r["buckets"]) == {"renda_variavel"}


def test_a_fracao_vendida_e_o_que_liga_custo_da_posicao_a_ganho_da_venda():
    inteira = map_portfolio(carteira(Qualidade.PARCIAL), ALVO)["pending_resolution"]
    parcial = adapt_portfolio(carteira(Qualidade.PARCIAL), ALVO)["pending_resolution"]
    assert inteira["positions"][0]["sale_fraction"] == 1.0
    assert 0 < parcial["positions"][0]["sale_fraction"] < 1.0
