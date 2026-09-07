# -*- coding: utf-8 -*-
"""A régua pública só vale se recusar as comparações que não pode fazer.

A distribuição de emissão do Open Finance responde uma pergunta estreita — onde
esta taxa cai dentro do que este emissor emitiu — e o jeito de estragá-la é
alargá-la: comparar entre emissores, entre prazos, ou interpolar um percentil
que os quatro números publicados não sustentam. Estes testes prendem a recusa no
lugar, porque é ela que o módulo tem de mais valioso.
"""
from __future__ import annotations

from datetime import date
import json

import pytest

from fixed_income_catalog import Index, Product
from open_finance_reference import (Colheita, carregar, conferir, faixa_de_prazo,
                                    taxas_de_servico, termos_de_distribuicao)

HOJE = date(2026, 1, 2)
CNPJ_A, CNPJ_B = "45086338000178", "11111111000191"


def distribuicao(medianas, pesos, minimo, maximo) -> dict:
    return {
        "prices": [{"interval": f"{i + 1}_FAIXA", "value": f"{m:.6f}",
                    "operationRate": f"{p:.6f}"}
                   for i, (m, p) in enumerate(zip(medianas, pesos))],
        "minimum": f"{minimo:.6f}", "maximum": f"{maximo:.6f}",
    }


def linha_bancaria(*, emissor=CNPJ_A, nome="Banco A", tipo="CDB", indexador="CDI",
                   resgate="DATA_VENCIMENTO", vencimento="361_1080",
                   publico="PESSOA_NATURAL", minimo=1_000.0,
                   medianas=(1.00, 1.05, 1.12, 1.15), pesos=(0.4, 0.3, 0.2, 0.1),
                   faixa_minima=0.95, faixa_maxima=1.18) -> dict:
    return {
        "issuerInstitutionCnpjNumber": emissor,
        "issuerInstitutionName": nome,
        "investmentType": tipo,
        "index": {"indexer": indexador,
                  "issueRemunerationRate": distribuicao(medianas, pesos,
                                                        faixa_minima, faixa_maxima)},
        "investmentConditions": {"minimumAmount": f"{minimo:.2f}",
                                 "redemptionTerm": resgate,
                                 "expirationPeriod": vencimento,
                                 "gracePeriod": "1_360"},
        "targetAudience": publico,
    }


def linha_de_fundo(cnpj="64108803000191", nome="FUNDO EXEMPLO FIC FI",
                   adm=0.02, minima=100.00, cotizacao=3, liquidacao=3) -> dict:
    return {
        "name": nome, "cnpjNumber": cnpj, "isinCode": "BRAAAAAAA000",
        "admin": {}, "fundManager": {}, "anbimaCategory": "RENDA_FIXA",
        "taxation": "LONGO_PRAZO",
        "fees": {"maxAdminFee": f"{adm:.6f}", "entryFee": "0.000000",
                 "performanceFee": {"amount": "0.200000", "benchmark": "CDI"}},
        "generalConditions": {
            "minimumAmount": {"value": f"{minima:.2f}", "currency": "BRL"},
            "application": {"quotationDays": 0, "quotationTerm": "DIAS_UTEIS"},
            "redemption": {"quotationDays": cotizacao, "quotationTerm": "DIAS_UTEIS",
                           "paymentDays": liquidacao, "paymentTerm": "DIAS_UTEIS",
                           "graceDays": 365},
            "fundQuotaType": "ABERTO"},
    }


def documento(bancarias=(), fundos=(), tesouro=(), marca="Corretora Exemplo") -> dict:
    return {
        "colhido_em": "2026-09-07T12:00:00+00:00",
        "participantes": [{
            "marca": marca, "organizacao": marca, "cnpj": CNPJ_A,
            "recursos": {
                "bank-fixed-incomes": {"linhas": len(bancarias), "dados": list(bancarias)},
                "funds": {"linhas": len(fundos), "dados": list(fundos)},
                "treasure-titles": {"linhas": len(tesouro), "dados": list(tesouro)},
            },
        }],
    }


def colher(tmp_path, **kw) -> Colheita:
    caminho = tmp_path / "dados_abertos_open_finance.json"
    caminho.write_text(json.dumps(documento(**kw), ensure_ascii=False), encoding="utf-8")
    return carregar(caminho)


def cdb(rate, *, meses=24, emissor="Banco A", **kw) -> Product:
    return Product(name=f"CDB {rate:.0%}", kind=kw.pop("kind", "CDB"), issuer=emissor,
                   conglomerate=emissor, index=kw.pop("index", Index.CDI), rate=rate,
                   maturity=date(2026 + meses // 12, 1 + meses % 12, 2), **kw)


# --- as faixas de prazo da especificação ------------------------------------

def test_a_faixa_de_prazo_segue_os_cortes_publicados() -> None:
    assert faixa_de_prazo(1) == "1_360"
    assert faixa_de_prazo(360) == "1_360"
    assert faixa_de_prazo(361) == "361_1080"
    assert faixa_de_prazo(1080) == "361_1080"
    assert faixa_de_prazo(1081) == "1081+"


# --- leitura da coleta ------------------------------------------------------

def test_linha_sem_os_campos_obrigatorios_e_contada_e_nao_engolida(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[linha_bancaria(), {"investmentType": "CDB"}])
    assert len(colheita.emissoes) == 1
    assert len(colheita.descartadas) == 1
    assert "campos obrigatórios" in colheita.descartadas[0]


def test_a_data_da_colheita_viaja_com_ela(tmp_path) -> None:
    assert colher(tmp_path, bancarias=[linha_bancaria()]).colhido_em.startswith("2026-09-07")


# --- a conferência ----------------------------------------------------------

def test_a_oferta_e_lida_contra_as_medianas_e_nao_contra_um_percentil(tmp_path) -> None:
    """O que se pode afirmar com quatro medianas é quantas ficam abaixo.

    Borda de faixa não é publicada. Um percentil interpolado teria a mesma cara
    de um percentil medido e apareceria na mesma linha da tela.
    """
    colheita = colher(tmp_path, bancarias=[linha_bancaria()])
    conferida = conferir(cdb(1.10), HOJE, colheita.emissoes)
    assert conferida.conferivel
    (comparacao,) = conferida.comparacoes
    assert comparacao.medianas_abaixo == 2
    assert comparacao.peso_das_medianas_abaixo == pytest.approx(0.7)
    assert not comparacao.abaixo_do_minimo and not comparacao.acima_do_maximo
    assert "70.0% das operações" in comparacao.leitura
    assert not hasattr(comparacao, "percentil")


def test_oferta_igual_a_mediana_nao_conta_como_acima_dela(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[linha_bancaria()])
    (comparacao,) = conferir(cdb(1.05), HOJE, colheita.emissoes).comparacoes
    assert comparacao.medianas_abaixo == 1


def test_fora_dos_extremos_a_leitura_diz_isso_e_nao_uma_posicao(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[linha_bancaria()])
    acima = conferir(cdb(1.25), HOJE, colheita.emissoes).comparacoes[0]
    abaixo = conferir(cdb(0.80), HOJE, colheita.emissoes).comparacoes[0]
    assert acima.acima_do_maximo and "acima do máximo" in acima.leitura
    assert abaixo.abaixo_do_minimo and "abaixo do mínimo" in abaixo.leitura


def test_nao_compara_entre_emissores(tmp_path) -> None:
    """Taxa maior de emissor pior não é oferta melhor, é outro risco de crédito."""
    colheita = colher(tmp_path, bancarias=[linha_bancaria(emissor=CNPJ_B, nome="Banco B")])
    conferida = conferir(cdb(1.10, emissor="Banco A"), HOJE, colheita.emissoes)
    assert not conferida.conferivel
    assert "nenhuma linha publicada" in conferida.recusa


def test_nao_compara_entre_faixas_de_vencimento(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[linha_bancaria(vencimento="1_360")])
    conferida = conferir(cdb(1.10, meses=24), HOJE, colheita.emissoes)
    assert not conferida.conferivel
    assert "faixa 361_1080" in conferida.recusa


def test_o_cnpj_vence_o_nome_quando_e_informado(tmp_path) -> None:
    """Casar por nome é o segundo melhor, e o resultado diz por qual casou."""
    colheita = colher(tmp_path, bancarias=[linha_bancaria(emissor=CNPJ_B,
                                                          nome="Banco B S.A.")])
    por_nome = conferir(cdb(1.10, emissor="banco b sa"), HOJE, colheita.emissoes)
    por_cnpj = conferir(cdb(1.10, emissor="qualquer coisa"), HOJE, colheita.emissoes,
                        emissor_cnpj="11.111.111/0001-91")
    assert por_nome.conferivel and por_cnpj.conferivel
    assert conferir(cdb(1.10), HOJE, colheita.emissoes,
                    emissor_cnpj=CNPJ_A).recusa.count("CNPJ") == 1


def test_liquidez_diaria_casa_com_os_dois_termos_diarios(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[
        linha_bancaria(resgate="DIARIA_PRAZO_CARENCIA"),
        linha_bancaria(resgate="DATA_VENCIMENTO")])
    conferida = conferir(cdb(1.10, daily_liquidity=True), HOJE, colheita.emissoes)
    assert [c.emissao.resgate for c in conferida.comparacoes] == ["DIARIA_PRAZO_CARENCIA"]


def test_cdi_mais_spread_e_recusado_com_o_motivo_da_especificacao(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[linha_bancaria()])
    conferida = conferir(cdb(0.015, index=Index.CDI_MAIS), HOJE, colheita.emissoes)
    assert not conferida.conferivel
    assert "taxa mista" in conferida.recusa


def test_papel_de_credito_e_tesouro_sao_recusados_por_falta_de_fonte(tmp_path) -> None:
    """A API só traz taxa de custódia e de carregamento para esses, nunca a do papel."""
    colheita = colher(tmp_path, bancarias=[linha_bancaria()])
    for tipo in ("DEBENTURE", "CRI", "TESOURO"):
        conferida = conferir(cdb(0.07, kind=tipo, index=Index.IPCA), HOJE,
                             colheita.emissoes)
        assert not conferida.conferivel
        assert "não tem contraparte pública de taxa" in conferida.recusa


def test_lci_isenta_tambem_e_conferivel(tmp_path) -> None:
    colheita = colher(tmp_path, bancarias=[linha_bancaria(tipo="LCI")])
    assert conferir(cdb(0.92, kind="LCI"), HOJE, colheita.emissoes).conferivel


def test_a_aplicacao_minima_da_linha_viaja_no_resultado_e_nao_filtra(tmp_path) -> None:
    """Descartar por desigualdade jogaria fora a linha mais parecida com a oferta."""
    colheita = colher(tmp_path, bancarias=[linha_bancaria(minimo=500_000.0)])
    (comparacao,) = conferir(cdb(1.10, minimum_brl=1_000.0), HOJE,
                             colheita.emissoes).comparacoes
    assert comparacao.emissao.minimo_brl == 500_000.0


# --- fundos e taxas de serviço ----------------------------------------------

def test_os_termos_do_fundo_vem_por_distribuidor(tmp_path) -> None:
    colheita = colher(tmp_path, fundos=[linha_de_fundo(minima=100.0),
                                        linha_de_fundo(cnpj="99999999000191")])
    (termos,) = termos_de_distribuicao("64.108.803/0001-91", colheita.fundos)
    assert termos.taxa_administracao_maxima == 0.02
    assert termos.aplicacao_minima_brl == 100.0
    assert termos.resgate_cotizacao_dias == 3 and termos.resgate_liquidacao_dias == 3
    assert termos.carencia_dias == 365
    assert termos.marca == "Corretora Exemplo"


def test_taxa_de_servico_e_da_instituicao_e_nao_do_papel(tmp_path) -> None:
    colheita = colher(tmp_path, tesouro=[{
        "investmentType": "TESOURO_DIRETO",
        "custodyFee": distribuicao((0.001, 0.002, 0.0025, 0.003),
                                   (0.5, 0.2, 0.2, 0.1), 0.0, 0.004),
        "loadingRate": distribuicao((0.0, 0.0, 0.0, 0.0),
                                    (1.0, 0.0, 0.0, 0.0), 0.0, 0.0)}])
    (taxa,) = taxas_de_servico(colheita, "TESOURO")
    assert taxa.tipo == "TESOURO_DIRETO"
    assert taxa.custodia.maximo == 0.004
    assert taxas_de_servico(colheita, "RENDA_FIXA_CREDITO") == ()
