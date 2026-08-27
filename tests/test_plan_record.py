"""O registro que liga a tela ao dossiê.

Antes disto, a pessoa respondia quatro perguntas, informava um custo e escolhia
um plano — e o PDF saía com outras respostas, outro custo e o plano que o script
preferisse. Para demonstração passava; para um documento que leva assinatura,
não.

A regra que estes testes protegem é uma só: **nenhum número atravessa a
fronteira**. O registro carrega decisões — respostas, custos declarados, plano
escolhido — e o gerador refaz as contas do zero com o mesmo módulo. Não existem
dois cálculos, então não há como o documento discordar da tela por acidente.
"""
from __future__ import annotations

import json

import pytest

from b3_connection import Qualidade
from plan_record import SCHEMA, PlanRecord, apply_declared_costs
from portfolio_mapping import Bucket, Position, Source, map_portfolio
from research_portfolio_mapping import alvo_do_perfil, carteira_exemplo

RESPOSTAS = {"horizonte": "5_mais", "queda": "ate_20", "reserva": "sim", "retirada": "nao"}


def registro(**troca) -> dict:
    base = {"schema": SCHEMA, "decided_at": "2026-08-27T10:40:00-03:00", "client": "Fulana",
            "answers": dict(RESPOSTAS), "profile": "equilibrado",
            "declared_costs": {"WEGE3": 40_000.0}, "chosen_path": "adequar"}
    base.update(troca)
    return base


# --- o registro só aceita o que a tela pode ter produzido ------------------

def test_o_perfil_vem_das_respostas_nao_do_campo():
    """O campo é conveniência de leitura; discordância significa arquivo editado."""
    with pytest.raises(ValueError, match="arrojado"):
        PlanRecord.from_json(registro(profile="arrojado"))


def test_plano_inexistente_e_recusado():
    with pytest.raises(ValueError, match="adequar"):
        PlanRecord.from_json(registro(chosen_path="sei_la"))


def test_resposta_fora_do_questionario_e_recusada():
    with pytest.raises(ValueError, match="horizonte"):
        PlanRecord.from_json(registro(answers={**RESPOSTAS, "horizonte": "daqui_a_100_anos"}))


def test_registro_incompleto_e_recusado():
    faltando = {k: v for k, v in RESPOSTAS.items() if k != "reserva"}
    with pytest.raises(ValueError, match="reserva"):
        PlanRecord.from_json(registro(answers=faltando))


def test_esquema_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="esquema"):
        PlanRecord.from_json(registro(schema="outra_coisa_v9"))


def test_custo_declarado_negativo_e_recusado():
    with pytest.raises(ValueError, match="WEGE3"):
        PlanRecord.from_json(registro(declared_costs={"WEGE3": -1}))


def test_ida_e_volta_preserva_a_decisao():
    original = PlanRecord.from_json(registro())
    assert PlanRecord.from_json(original.to_json()) == original


# --- custo declarado é declarado, nunca reconstruído -----------------------

def test_custo_informado_entra_marcado_como_declarado():
    """Um é extrato da B3, o outro é memória de quem tem interesse no resultado."""
    posicoes = apply_declared_costs(carteira_exemplo(), {"WEGE3": 40_000})
    wege = next(p for p in posicoes if p.ticker == "WEGE3")
    assert wege.cost_quality is Qualidade.DECLARADO
    assert wege.cost_basis_brl == 40_000
    # e não contamina as outras
    cury = next(p for p in posicoes if p.ticker == "CURY3")
    assert cury.cost_quality is Qualidade.RECONSTRUIDO


def test_custo_para_posicao_inexistente_e_recusado():
    with pytest.raises(ValueError, match="PETR4"):
        apply_declared_costs(carteira_exemplo(), {"PETR4": 1_000})


def test_informar_custo_fecha_a_apuracao():
    alvo, _ = alvo_do_perfil("equilibrado")
    sem = map_portfolio(carteira_exemplo(), alvo)
    com = map_portfolio(apply_declared_costs(carteira_exemplo(), {"WEGE3": 40_000}), alvo)
    assert sem["tax_is_complete"] is False
    assert com["tax_is_complete"] is True
    assert com["unpriced_sale_brl"] == 0


# --- a fronteira: o dossiê recalcula, não recebe números ------------------

def test_o_registro_nao_carrega_numero_calculado():
    """Se um valor apurado entrasse aqui, haveria duas fontes para o mesmo número."""
    corpo = PlanRecord.from_json(registro()).to_json()
    proibidos = {"transition_total_brl", "transition_tax_brl", "tax_by_bucket", "moves",
                 "alignment", "turnover_brl", "total_brl"}
    assert not (proibidos & set(corpo))
    assert set(corpo) == {"schema", "decided_at", "client", "answers", "profile",
                          "declared_costs", "chosen_path"}


def test_o_dossie_reproduz_o_que_a_tela_mostraria():
    """A conta do documento tem de bater com a do mapa para o mesmo registro."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.build_transition_dossier import payload_from_record

    decisao = PlanRecord.from_json(registro())
    payload = payload_from_record(decisao)

    alvo, _ = alvo_do_perfil("equilibrado")
    esperado = map_portfolio(apply_declared_costs(carteira_exemplo(), {"WEGE3": 40_000}), alvo)
    assert payload["mapping"]["transition_total_brl"] == esperado["transition_total_brl"]
    assert payload["target_profile"] == "equilibrado"
    assert payload["record"]["chosen_path"] == "adequar"


def test_o_plano_nao_escolhido_continua_no_payload():
    """Decisão sem alternativa documentada não se distingue de execução automática."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.build_transition_dossier import payload_from_record

    payload = payload_from_record(PlanRecord.from_json(registro(chosen_path="adaptar")))
    assert payload["alternative"]["path"] == "adaptar"
    assert payload["mapping"]["path"] == "adequar"


def test_respostas_diferentes_dao_perfis_diferentes_no_dossie():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.build_transition_dossier import payload_from_record

    curto = registro(answers={**RESPOSTAS, "horizonte": "ate_2"}, profile="conservador")
    payload = payload_from_record(PlanRecord.from_json(curto))
    assert payload["target_profile"] == "conservador"


# --- e a tela emite exatamente este formato -------------------------------

def test_a_tela_emite_o_esquema_que_o_gerador_consome():
    from pathlib import Path
    tela = (Path(__file__).resolve().parents[1] / "docs" / "desenho_tela_mapa.html")
    fonte = tela.read_text(encoding="utf-8")
    assert f'schema: "{SCHEMA}"' in fonte
    for campo in ("answers", "declared_costs", "chosen_path", "decided_at", "profile"):
        assert f"{campo}:" in fonte, f"a tela não emite {campo}"
    # E não emite número calculado: se emitisse, alguém acabaria confiando nele.
    trecho = fonte[fonte.index("function registroDaDecisao"):]
    trecho = trecho[:trecho.index("function razao")]
    for proibido in ("transition_total", "transition_tax", "turnover", "alignment"):
        assert proibido not in trecho
