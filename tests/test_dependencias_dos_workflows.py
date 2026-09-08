# -*- coding: utf-8 -*-
"""Nenhum workflow mantém a própria lista de dependências.

Este arquivo existe porque o mesmo defeito aconteceu três vezes, e as três da
mesma forma: um workflow instala à mão o que acha que precisa, os testes passam
a alcançar um módulo novo, e a execução morre com ``ModuleNotFoundError`` num
caminho que ninguém observa enquanto a CI de pull request segue verde — ela já
lia ``requirements-ci.txt``.

* 03/09/2026: os testes alcançaram ``fundamentals.py``, que importa pydantic, e
  o noturno caiu três noites seguidas com a lista ``pytest numpy pandas``.
* 04/09/2026: o teste do selo da política passou a alcançar
  ``tools/reatestar_politica_v4.py``, que importa ``profile_ladder_v2`` e com ele
  o pandas. O radar de eventos, que instalava só ``pytest``, falhou oito
  execuções seguidas — de 04/09 às 18h até 08/09 às 8h.

A segunda é a que dói: a execução de 05/09 do radar rodou exatamente sobre o
commit "O noturno passa a ler a mesma lista de dependências dos outros
workflows". O conserto deste defeito estava chegando para um workflow enquanto o
outro caía por ele, e nada ligou as duas coisas — porque nada tinha como ligar.

A relação não é dedutível de nenhum arquivo isolado: quem escreve o teste não
olha o workflow, e quem escreve o workflow não sabe que a árvore de importação
cresceu. O único ponto onde os dois se encontram é aqui.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[1]
WORKFLOWS = RAIZ / ".github" / "workflows"
LISTA = "requirements-ci.txt"

#: Toda instalação tem de ser esta. Um `pip install <pacote>` escrito à mão é
#: uma promessa de que alguém vai lembrar de atualizá-lo, e é essa promessa que
#: falhou nas três vezes.
INSTALACAO = re.compile(r"pip install\s+(?!-r\s+" + re.escape(LISTA) + r"\b)(\S.*)")


def workflows() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def comandos(caminho: Path) -> str:
    """Só o que de fato roda: os `run:` dos passos, sem comentário nenhum.

    Ler o arquivo inteiro com regex reprovaria a própria nota que registra o
    defeito — a primeira versão deste teste reprovou o comentário que explica
    por que o `pip install pytest` saiu. O YAML separa o que é instrução do que
    é prosa, e as linhas de comentário de shell caem junto.
    """
    documento = yaml.safe_load(caminho.read_text(encoding="utf-8"))
    linhas: list[str] = []
    for job in (documento.get("jobs") or {}).values():
        for passo in job.get("steps") or []:
            if isinstance(passo, dict) and isinstance(passo.get("run"), str):
                linhas.extend(l for l in passo["run"].splitlines()
                              if not l.strip().startswith("#"))
    return "\n".join(linhas)


def test_ha_workflows_para_conferir() -> None:
    """Sem isto, apagar a pasta faria os testes abaixo passarem por vacuidade."""
    assert workflows()


@pytest.mark.parametrize("caminho", workflows(), ids=lambda p: p.stem)
def test_o_workflow_nao_escreve_a_propria_lista(caminho: Path) -> None:
    inline = [m.group(1).strip() for m in INSTALACAO.finditer(comandos(caminho))]
    assert not inline, (
        f"{caminho.name} instala à mão: {inline}. Use "
        f"`python -m pip install -r {LISTA}`. Lista escrita à mão fica para trás "
        f"quando a árvore de importação dos testes cresce, e a execução morre "
        f"com ModuleNotFoundError onde ninguém está olhando.")


@pytest.mark.parametrize("caminho", workflows(), ids=lambda p: p.stem)
def test_quem_roda_pytest_instala_da_lista(caminho: Path) -> None:
    executado = comandos(caminho)
    if "pytest" not in executado:
        return
    assert LISTA in executado, (
        f"{caminho.name} roda pytest e não instala de {LISTA}. Os módulos de "
        f"teste importam os do projeto no topo do arquivo, então o pytest nem "
        f"chega a coletar sem eles.")
