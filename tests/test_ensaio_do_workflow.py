"""O encadeamento do workflow roda hoje, para um ano que nunca passou por ele.

O workflow de janeiro só executa de verdade em janeiro, contra B3 e CVM, e
esperar até lá para descobrir que não funciona é caro: a amostra confirmatória
começa no primeiro pregão de 2027 e não há segunda chance no mesmo ano.

Estes testes exercitam a corrente inteira com os dois passos de rede
substituídos por dado real — o retrato histórico do universo daquele ano — e
fixam a descoberta que o ensaio trouxe: o gerador recusa publicar carteira com
menos emissores do que a política declara.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _carrega(nome: str, caminho: Path):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _ensaio():
    return _carrega("ensaio_do_workflow", ROOT / "tools" / "ensaio_do_workflow.py")


@pytest.fixture(scope="module")
def corrida():
    modulo = _ensaio()
    if not (modulo.RETRATOS / "b3_universe_2025.csv").exists():
        pytest.skip("o retrato histórico de 2025 não está neste clone")
    if not (ROOT / "data" / "prices_b3_cotahist_2011_2026.csv").exists():
        pytest.skip("o painel de preços não está neste clone")
    return modulo.ensaiar(2025)


def test_a_corrente_inteira_executa_para_outro_ano(corrida) -> None:
    """Nenhum passo pode falhar: o maquinário não pode ser secretamente de 2026."""
    falhos = [p for p in corrida["passos"] if not p["ok"]]
    assert not falhos, falhos
    assert corrida["decision_date"] == "2025-01-02"


def test_a_captura_do_ano_ensaiado_confere(corrida) -> None:
    passo = next(p for p in corrida["passos"] if p["passo"] == "conferência da captura")
    assert passo["ok"], passo
    assert "mesmos" in passo["detalhe"]


def test_carteira_com_menos_emissores_que_o_declarado_e_recusada() -> None:
    """A descoberta do ensaio, virada em guarda.

    Com o cache da CVM cobrindo só os formulários de 2026, a triagem de 2025
    enxergou quatro fundamentos em vez de cento e quinze, e o gerador produzia
    livros de três emissores onde o conservador declara doze — sem reclamar.
    Numa execução de janeiro com a CVM meio fora do ar, sairia uma cesta de três
    nomes publicada como a carteira declarada.

    Publicar parcial é o modo de falha que o workflow inteiro existe para não
    ter, e faltava justamente no passo que produz a carteira.
    """
    modulo = _ensaio()
    if not (modulo.RETRATOS / "b3_universe_2025.csv").exists():
        pytest.skip("o retrato histórico de 2025 não está neste clone")
    relatorio = modulo.ensaiar(2025)
    passo = next(p for p in relatorio["passos"] if p["passo"] == "decisão a partir da captura")
    assert "recusada" in passo["detalhe"], passo
    assert relatorio["livro"] is None
