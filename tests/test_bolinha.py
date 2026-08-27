# -*- coding: utf-8 -*-
"""O halo que segue o ponteiro, e as duas situações em que ele não deve existir.

Enfeite que se move é a primeira coisa que incomoda quem tem sensibilidade a
movimento, e a última que alguém lembra de testar.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "web" / "bolinha.js"
CSS = ROOT / "web" / "benevente.css"
PAGINAS = ("index", "versoes", "metodo", "limitacoes", "para-escritorios", "quant-ai")


def test_o_script_desiste_sem_ponteiro_e_com_movimento_reduzido():
    texto = JS.read_text(encoding="utf-8")
    assert '(hover: none)' in texto, "tela de toque não tem ponteiro para seguir"
    assert '(prefers-reduced-motion: reduce)' in texto
    # As duas checagens têm de acontecer antes de qualquer coisa ser criada.
    antes = texto.index("createElement")
    for guarda in ('(hover: none)', '(prefers-reduced-motion: reduce)'):
        assert texto.index(guarda) < antes, guarda


def test_a_folha_tambem_esconde_o_halo_nesses_casos():
    """O CSS repete a regra porque o script pode ser bloqueado e o elemento
    ainda assim existir numa carga anterior em cache."""
    texto = CSS.read_text(encoding="utf-8")
    assert "#bolinha" in texto
    bloco = texto[texto.index("#bolinha"):]
    assert "hover: none" in bloco and "prefers-reduced-motion: reduce" in bloco


def test_o_halo_nao_intercepta_clique_nem_e_lido():
    js, css = JS.read_text(encoding="utf-8"), CSS.read_text(encoding="utf-8")
    assert 'aria-hidden' in js, "enfeite não entra na árvore de acessibilidade"
    assert "pointer-events: none" in css[css.index("#bolinha"):]


def test_todas_as_paginas_carregam_o_halo():
    for nome in PAGINAS:
        html = (ROOT / "web" / f"{nome}.html").read_text(encoding="utf-8")
        assert "bolinha.js" in html, nome
