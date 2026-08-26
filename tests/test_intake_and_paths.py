"""O questionário e as duas portas do fim do mapa.

O que estes testes protegem não é aritmética, é honestidade. A tentação
comercial do caminho B é grande e específica: dizer que manter a carteira do
cliente entrega o retorno publicado. Existe um teste aqui só para impedir que
alguém, um dia, marque ``track_record_applies`` como verdadeiro nesse caminho.
"""
from __future__ import annotations

import pytest

from client_intake import QUESTIONS, WORST_DRAWDOWN, Intake
from portfolio_mapping import Bucket, Position, Source, adapt_portfolio, map_portfolio

ALVO = {"positions": {"CURY3": 0.10, "CMIN3": 0.10, "BBSE3": 0.06},
        "global_sleeve": 0.11, "cash": 0.63}


def carteira() -> list[Position]:
    return [
        Position("CURY3", Bucket.ACAO, 40_000, 20_000, Source.B3_INVESTIDOR),
        Position("WEGE3", Bucket.ACAO, 200_000, 50_000, Source.B3_INVESTIDOR),
        Position("MGLU3", Bucket.ACAO, 30_000, 90_000, Source.B3_INVESTIDOR),
        Position("Tesouro Selic", Bucket.CAIXA, 130_000, 128_000, Source.B3_INVESTIDOR),
    ]


# --- o questionário -------------------------------------------------------

def test_o_perfil_e_o_menor_teto_nao_uma_soma_de_pontos():
    """Horizonte curto manda, mesmo com a resposta mais arrojada na queda."""
    intake = Intake(answers={"horizonte": "ate_2", "queda": "acima_20",
                             "reserva": "sim", "retirada": "nao"})
    assert intake.profile == "conservador"


def test_sempre_da_para_apontar_a_resposta_que_definiu_o_perfil():
    intake = Intake(answers={"horizonte": "2_a_5", "queda": "acima_20",
                             "reserva": "sim", "retirada": "nao"})
    resultado = intake.assessment()
    assert resultado["profile"] == "equilibrado"
    assert [b["caps_at"] for b in resultado["binding"]] == ["equilibrado"]
    assert "dois e cinco anos" in resultado["binding"][0]["answer"].lower()


def test_toda_resposta_fica_registrada_inclusive_as_que_nao_limitam():
    """Um registro que só guarda a resposta vencedora não permite conferir."""
    intake = Intake(answers={"horizonte": "5_mais", "queda": "acima_20",
                             "reserva": "sim", "retirada": "nao"})
    assert len(intake.assessment()["all_limits"]) == 4


def test_todo_teto_declarado_traz_a_justificativa_junto():
    for question in QUESTIONS:
        for option in question.options:
            if option.caps_profile is not None:
                assert option.note, f"{question.key}/{option.value} limita sem dizer por quê"


def test_a_pergunta_da_queda_usa_os_numeros_medidos_de_cada_perfil():
    queda = next(q for q in QUESTIONS if q.key == "queda")
    for valor in WORST_DRAWDOWN.values():
        assert f"{abs(valor) * 100:.1f}".replace(".", ",") in queda.help


def test_perguntas_sem_resposta_sao_listadas_em_vez_de_assumidas():
    assert set(Intake(answers={"queda": "ate_10"}).assessment()["unanswered"]) == {
        "horizonte", "reserva", "retirada"}


# --- caminho A: adequar ---------------------------------------------------

def test_posicao_travada_permanece_e_o_desvio_fica_registrado():
    mapa = map_portfolio(carteira(), ALVO, locked_tickers=("WEGE3",))
    wege = next(m for m in mapa["moves"] if m["ticker"] == "WEGE3")
    assert wege["action"] == "manter"
    assert wege["reason"] == "travada pelo cliente"
    assert wege["notes"] and "não chega ao alvo" in wege["notes"][0]


def test_prejuizo_acumulado_informado_abate_o_imposto_da_travessia():
    sem = map_portfolio(carteira(), ALVO)["transition_tax_brl"]
    com = map_portfolio(carteira(), ALVO, carried_loss_brl=50_000)["transition_tax_brl"]
    assert sem > 0 and com < sem


def test_ativo_fora_do_escopo_nao_e_vendido_por_nao_estar_na_cesta():
    """Ele não foi analisado e reprovado — ele não foi olhado."""
    posicoes = carteira() + [Position("Cripto", Bucket.FORA_DO_ESCOPO, 20_000, 30_000,
                                      Source.MANUAL)]
    cripto = next(m for m in map_portfolio(posicoes, ALVO)["moves"] if m["ticker"] == "Cripto")
    assert cripto["reason"] == "fora do escopo da política"
    assert not any("mesma cesta" in n for n in cripto["notes"])


# --- caminho B: adaptar ---------------------------------------------------

def test_adaptar_nunca_pode_alegar_o_historico_publicado():
    """A afirmação comercialmente fácil e falsa. Se cair, cai aqui."""
    assert adapt_portfolio(carteira(), ALVO)["track_record_applies"] is False
    assert adapt_portfolio(carteira(), ALVO)["modules"] == ["Módulo 2 — Proteção"]
    assert "não descreve esta carteira" in adapt_portfolio(carteira(), ALVO)["honesty"]


def test_adaptar_nao_vende_nada_por_estar_fora_da_cesta():
    mapa = adapt_portfolio(carteira(), ALVO)
    assert not any(m["reason"] == "não está na cesta do perfil" for m in mapa["moves"])
    assert all(m["action"] in ("manter", "reduzir") for m in mapa["moves"])


def concentrada() -> list[Position]:
    """Dentro do orçamento de ações, mas com um nome grande demais.

    Separada da outra porque só assim o teto de concentração é o limite que
    aperta: com ações acima do orçamento, quem corta é o orçamento, e o teto
    nunca chega a ser testado.
    """
    return [
        Position("CURY3", Bucket.ACAO, 20_000, 10_000, Source.B3_INVESTIDOR),
        Position("WEGE3", Bucket.ACAO, 100_000, 30_000, Source.B3_INVESTIDOR),
        Position("MGLU3", Bucket.ACAO, 20_000, 60_000, Source.B3_INVESTIDOR),
        Position("Tesouro Selic", Bucket.CAIXA, 260_000, 255_000, Source.B3_INVESTIDOR),
    ]


def test_adaptar_corta_concentracao_pelo_peso_medio_do_proprio_cliente():
    """O teto da política vale para oito emissores; o cliente tem três."""
    mapa = adapt_portfolio(concentrada(), ALVO)
    assert mapa["issuer_cap"] > max(ALVO["positions"].values())
    wege = next(m for m in mapa["moves"] if m["ticker"] == "WEGE3")
    assert wege["action"] == "reduzir"
    assert wege["reason"] == "teto de concentração por emissor"
    # O teto é publicado com quatro casas, então a comparação é em peso e a
    # folga é a da própria arredondagem, não um valor em reais.
    assert wege["to_brl"] / mapa["total_brl"] <= mapa["issuer_cap"] + 5e-5


def test_adaptar_nao_compra_quando_a_carteira_esta_abaixo_do_orcamento():
    """Comprar exigiria escolher o quê — e escolher é o Módulo 1."""
    mapa = adapt_portfolio(concentrada(), ALVO)
    assert mapa["equity_below_budget"] is True
    assert not any(m["action"] == "comprar" for m in mapa["moves"])


def test_adaptar_corta_pelo_orcamento_quando_as_acoes_passam_dele():
    mapa = adapt_portfolio(carteira(), ALVO)
    assert mapa["equity_below_budget"] is False
    assert mapa["equity_after"] <= mapa["equity_budget"] + 1e-6
    assert any(m["reason"] == "orçamento de ações do perfil" for m in mapa["moves"])


def test_adaptar_mexe_menos_que_adequar():
    assert (adapt_portfolio(carteira(), ALVO)["turnover_brl"]
            < map_portfolio(carteira(), ALVO)["turnover_brl"])


def test_o_credito_nao_usado_nunca_vale_mais_que_o_imposto_pago():
    mapa = adapt_portfolio(carteira(), ALVO)
    assert mapa["tax_left_on_table_brl"] <= mapa["transition_tax_brl"] + 1e-6


def test_teto_de_concentracao_declara_que_nao_foi_medido():
    assert "não medido no histórico" in adapt_portfolio(carteira(), ALVO)["issuer_cap_rule"]


def test_carteira_sem_valor_e_recusada_nos_dois_caminhos():
    vazia = [Position("X", Bucket.ACAO, 0.0, 0.0, Source.MANUAL)]
    for fn in (map_portfolio, adapt_portfolio):
        with pytest.raises(ValueError):
            fn(vazia, ALVO)


# --- a tela ---------------------------------------------------------------

def test_o_prototipo_publicado_nao_fica_para_tras_do_modulo():
    """A tela embute os dados. Editar o módulo sem regerá-la publica número velho.

    É a mesma falha que já aconteceu com o bundle da home: o artefato mudou, a
    página não, e ninguém percebeu porque as duas coisas continuavam válidas
    separadamente.
    """
    import subprocess
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    pagina = raiz / "docs" / "desenho_tela_mapa.html"
    antes = pagina.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(raiz / "tools" / "build_mapa_prototype.py")],
                   check=True, cwd=raiz, capture_output=True)
    assert pagina.read_text(encoding="utf-8") == antes, (
        "docs/desenho_tela_mapa.html está desatualizada: rode tools/build_mapa_prototype.py")


def test_a_tela_nunca_publica_o_historico_no_caminho_que_nao_o_tem():
    from pathlib import Path
    pagina = (Path(__file__).resolve().parents[1] / "docs" / "desenho_tela_mapa.html")
    texto = pagina.read_text(encoding="utf-8")
    assert '"path":"adaptar","path_label":"Manter a carteira e aplicar a proteção",' \
           '"modules":["Módulo 2 — Proteção"],"track_record_applies":false' in texto
