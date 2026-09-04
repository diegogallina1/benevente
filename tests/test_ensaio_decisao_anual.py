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


def test_o_ultraconservador_tem_um_metodo_so(relatorio) -> None:
    """Decidido em 04/09/2026: escalar a carteira do conservador.

    Havia dois métodos e duas respostas. Ficou escalar, porque a declaração do
    degrau diz que a regra moveu o teto de ações e só ele, e refazer a triagem
    sob um teto por ativo próprio seria uma segunda decisão sobre pesos que ela
    não autoriza. A razão está em data/decisao_metodo_do_ultraconservador_2026-09-04.json.

    Este teste vigia a convergência: o gerador e o arquivo publicado têm de dar
    exatamente os mesmos pesos. Se voltarem a discordar, alguém reintroduziu o
    segundo método.
    """
    modulo, _, ensaiado = relatorio
    resultado = modulo.divergencia_do_ultraconservador(ensaiado)
    assert resultado["total_em_acoes"]["igual"], resultado["total_em_acoes"]
    assert not resultado["pesos_diferentes_em"], resultado["pesos_diferentes_em"]
    assert resultado["papeis_conferidos"] == 12, resultado["papeis_conferidos"]


def test_a_decisao_do_metodo_esta_registrada() -> None:
    """A escolha é interpretação de política, então ela é declarada, não implícita."""
    caminho = ROOT / "data" / "decisao_metodo_do_ultraconservador_2026-09-04.json"
    registro = json.loads(caminho.read_text(encoding="utf-8"))
    assert registro["chosen"] == "escalar a carteira do conservador"
    assert registro["decided_by"], "decisão sem quem decidiu"
    assert registro["rejected"]["why_not"], "o método recusado precisa dizer por quê"
    assert len(registro["record_sha256"]) == 64
    # O fator é o que a política implica, não um número escolhido à parte.
    politica = json.loads(
        (ROOT / "data" / "benevente_profile_ladder_v4_registration.json").read_text(encoding="utf-8"))
    perfis = politica["profiles"]
    esperado = perfis["ultraconservador"]["maximum_equity_weight"] / perfis["conservador"]["maximum_equity_weight"]
    assert abs(registro["factor"] - esperado) < 1e-6


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
