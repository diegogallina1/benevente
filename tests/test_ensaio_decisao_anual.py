"""O ensaio da decisão anual continua reproduzindo o que foi publicado.

A amostra confirmatória começa no primeiro pregão de 2027, e até lá o único
jeito de saber se o maquinário serve é refazer um ano cuja resposta já se
conhece. Este teste trava o resultado do ensaio: se alguém mexer no gerador, na
triagem ou nos insumos e a decisão de janeiro de 2026 deixar de sair igual, ele
reprova aqui, e não em janeiro de 2027 com o ano correndo.

É lento, porque roda a triagem inteira. É o preço de saber.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _ensaio():
    spec = importlib.util.spec_from_file_location(
        "ensaio_decisao_anual", ROOT / "tools" / "ensaio_decisao_anual.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def relatorio():
    modulo = _ensaio()
    faltando = [caminho for caminho, _ in modulo.INSUMOS.values() if not (ROOT / caminho).exists()]
    if faltando:
        pytest.skip(f"insumo fora do clone: {faltando}")
    import tempfile
    publicado = json.loads(modulo.PUBLICADO.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as pasta:
        ensaiado = modulo.executa(Path(pasta))
    return modulo, publicado, ensaiado


def test_a_decisao_de_janeiro_de_2026_ainda_reproduz(relatorio) -> None:
    modulo, publicado, ensaiado = relatorio
    linhas = modulo.compara(publicado, ensaiado)
    assert linhas, "o ensaio não comparou perfil nenhum"
    quebrados = [linha for linha in linhas if not linha["reproduz"]]
    assert not quebrados, quebrados


def test_o_ultraconservador_continua_com_dois_metodos(relatorio) -> None:
    """Enquanto a divergência existir, ela fica descrita em vez de esquecida.

    O site publica o degrau escalando os pesos do conservador; o gerador o
    calcula sob o teto por ativo próprio. O total em ações é o mesmo, a
    distribuição entre os papéis não. Qual dos dois governa é interpretação da
    política, e o dia em que for decidido este teste muda junto.
    """
    modulo, _, ensaiado = relatorio
    divergencia = modulo.divergencia_do_ultraconservador(ensaiado)
    assert divergencia["total_em_acoes"]["igual"], divergencia["total_em_acoes"]
    assert divergencia["pesos_diferentes_em"], (
        "os dois métodos convergiram: decida qual governa e atualize a descrição")


def test_nenhuma_amarra_a_2026_voltou() -> None:
    """O ano é propriedade do insumo, e tem de continuar sendo.

    As quatro amarras caíram em 04/09/2026: o ano passou a sair do retrato do
    universo, e não de constante, nome de arquivo ou número escrito no corpo.
    Reintroduzir qualquer uma faz o fluxo servir a um ano só de novo, e o
    sintoma disso em 2027 seria ler silenciosamente o ano errado.
    """
    modulo = _ensaio()
    pinos = modulo.pinos_de_2026()
    assert pinos, "o inventário de amarras ficou vazio"
    de_pe = [p for p in pinos if p["presente"]]
    assert not de_pe, de_pe


def test_o_ano_sai_do_retrato_do_universo() -> None:
    """Não de um sinalizador: assim os dados e o ano não têm como se separar."""
    import pandas as pd
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import build_profile_books_2026 as gerador
    for data, esperado in (("2026-01-02", 2026), ("2027-01-04", 2027)):
        universo = pd.DataFrame({"decision_date": [data]})
        assert gerador.ano_da_decisao(universo) == esperado


def test_o_comando_documentado_do_gerador_funciona() -> None:
    """O padrão do --mapping precisa apontar para uma ponte com isin.

    Ele apontava para uma exportação sem essa coluna, e current_mapping funde
    por ticker E isin: quem rodasse o comando como documentado recebia
    KeyError. O ensaio existe para achar exatamente esse tipo de coisa.
    """
    import csv
    fonte = (ROOT / "build_profile_books_2026.py").read_text(encoding="utf-8")
    linha = next(l for l in fonte.splitlines() if '"--mapping"' in l)
    caminho = linha.split('default="')[1].split('"')[0]
    arquivo = ROOT / caminho
    assert arquivo.exists(), f"o padrão aponta para {caminho}, que não existe"
    with arquivo.open(encoding="utf-8", errors="ignore", newline="") as fh:
        cabecalho = next(csv.reader(fh))
    assert "isin" in cabecalho, f"{caminho} não traz isin, e a fusão exige"
