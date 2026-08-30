# -*- coding: utf-8 -*-
"""Quais perfis existem, lido da política e não copiado.

A escada apareceu escrita à mão em cinco lugares deste repositório: no gerador
do app, no do site, no monitor diário, no das mudanças do ano e no da faixa.
Enquanto ela teve três degraus as cinco cópias concordaram. Quando ganhou o
quarto, cada uma passou a errar de um jeito diferente: uma caía calada no
degrau de cima, outras publicavam um ano que dizia ter todos os perfis e tinha
um a menos.

A ordem vem do teto de ações, que é o que define a escada. Ela não é escrita
aqui: é derivada do registro, então acrescentar um degrau no meio não pede
edição em lugar nenhum.
"""
from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
REGISTRO = ROOT / "data" / "benevente_profile_ladder_v4_registration.json"


def perfis() -> dict:
    """Os perfis declarados, com o que a política diz de cada um."""
    return json.loads(REGISTRO.read_text(encoding="utf-8"))["profiles"]


def escada() -> list[str]:
    """Os nomes, do degrau mais apertado ao mais solto."""
    declarados = perfis()
    return sorted(declarados, key=lambda nome: declarados[nome]["maximum_equity_weight"])
