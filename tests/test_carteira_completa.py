# -*- coding: utf-8 -*-
"""A carteira inteira na tela, com a procedência de cada linha.

O defeito que estes testes existem para impedir é o silencioso: uma posição sem
valor tratada como zero. Zero é uma resposta, e some no total sem deixar rastro;
"não sei" precisa aparecer, porque é ele que decide se o plano pode ser feito.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from b3_connection import Origem, Posicao, consolidar  # noqa: E402

TELA = ROOT / "docs" / "desenho_tela_mapa.html"


def _payload() -> dict:
    return json.loads(re.search(r"const DADOS = (\{.*?\});",
                                TELA.read_text(encoding="utf-8"), re.S).group(1))


def test_posicao_sem_valor_nao_vira_zero():
    p = Posicao("LCA Banco Beta 2028", "LCA", Origem.B3_PARCIAL, quantidade=1)
    assert p.valor_brl is None and not p.completa
    r = consolidar([p, Posicao("CURY3", "ação", Origem.B3, 44_000.0)])
    assert r["total_conhecido_brl"] == 44_000.0
    assert r["sem_valor"] == 1 and r["completo"] is False


def test_o_total_se_declara_parcial_enquanto_faltar_valor():
    """Publicar só o total somável esconderia o buraco, e a porcentagem de
    qualquer coisa sobre o patrimônio ficaria com o denominador errado."""
    r = consolidar([Posicao("X", "LCA", Origem.B3_PARCIAL),
                    Posicao("Y", "ação", Origem.B3, 10.0)])
    assert r["sem_valor_nomes"] == ["X"]


def test_a_carteira_publicada_traz_a_origem_de_cada_linha():
    """Lê o payload da página, não o artefato.

    ``connection_example.json`` não é versionado: um teste apoiado nele passa
    aqui e falha em clone limpo, que é a pior forma de falhar. A página está no
    repositório e carrega o mesmo dado.
    """
    posicoes = _payload()["b3"]["posicoes"]
    assert posicoes, "sem lista de posições a tela volta a mostrar só o agregado"
    origens = {p["origem"] for p in posicoes}
    assert Origem.B3.value in origens
    assert Origem.B3_PARCIAL.value in origens, (
        "a renda fixa que a B3 manda pela metade precisa aparecer, senão a "
        "carteira parece menor do que é")
    for p in posicoes:
        if not p["completa"]:
            assert p["valor_brl"] is None and p["falta"], p["nome"]


def test_a_tela_carrega_posicoes_e_o_historico_de_mudancas():
    d = _payload()
    assert d["b3"]["posicoes"], "a tela promete origem por posição: precisa das posições"
    assert d["b3"]["consolidado"]["sem_valor"] >= 1
    assert d["mudancas"]["perfis"], "sem isso não há alerta de mudança na estratégia"


def test_o_alerta_so_existe_para_quem_copia_a_estrategia():
    """Quem escolheu manter a própria carteira não segue a política, e receber
    ordem de uma estratégia que não é a sua é ruído com cara de instrução."""
    tela = TELA.read_text(encoding="utf-8")
    assert 'chave !== "adequar"' in tela


def test_o_alerta_avisa_quando_o_numero_e_piso():
    """O valor em reais sai do patrimônio conhecido. Enquanto faltar posição, ele
    é piso, e a tela precisa dizer isso no mesmo parágrafo em que dá o número."""
    assert "Esse número é piso" in TELA.read_text(encoding="utf-8")
