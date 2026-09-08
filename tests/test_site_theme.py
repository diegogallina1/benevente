# -*- coding: utf-8 -*-
"""O gerador da camada de cor tem de rodar, e ninguém estava rodando.

Este arquivo existe por causa de um defeito que ficou invisível por não ter
dono. A remoção do desenho B2B apagou `web/commercial.css`, mas a folha
continuou listada em `PAGINAS`, e `build_site_theme.py` passou a levantar
`FileNotFoundError` antes de gerar qualquer coisa. O site seguiu correto —
`benevente.css` está versionado e as páginas não linkavam mais a folha morta —,
de modo que nada apontou o problema: nenhum teste e nenhum workflow executam
esse programa. O defeito só apareceria na próxima vez que alguém mexesse em cor,
provavelmente meses depois, sem ligação com a causa.

A outra metade do mesmo desvio: `para-escritorios` virou redirecionamento de
meio kilobyte e continuou na lista como página com estilo, enquanto
`para-voce`, que é a página de verdade, ficou de fora.

Os testes abaixo prendem as duas metades e o vazio entre elas. O mais forte é o
último: a folha publicada tem de ser byte a byte o que o gerador produz. Ele foi
editada à mão uma vez — foi assim que as regras da folha apagada saíram — e uma
saída de gerador editada à mão é um gerador que ninguém confere.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

import pytest

RAIZ = Path(__file__).resolve().parents[1]
WEB = RAIZ / "web"
sys.path.insert(0, str(RAIZ / "tools"))

from build_site_theme import PAGINAS, SAIDA, build  # noqa: E402

#: Folhas que toda página carrega e que o gerador não tematiza: as duas
#: primeiras são a fonte dos tokens, e a terceira é a própria saída — incluí-la
#: faria o gerador ler o que ele mesmo escreveu.
FORA_DO_GERADOR = {"fontes.css", "tokens.css", "benevente.css"}


def folhas_ligadas(pagina: str) -> list[str]:
    html = (WEB / f"{pagina}.html").read_text(encoding="utf-8")
    ligadas = [alvo.split("?")[0].removeprefix("./")
               for alvo in re.findall(r'<link rel="stylesheet" href="([^"]+)"', html)]
    return [f for f in ligadas if f not in FORA_DO_GERADOR]


def paginas_com_a_camada() -> set[str]:
    return {caminho.stem for caminho in WEB.glob("*.html")
            if "benevente.css" in caminho.read_text(encoding="utf-8")}


def test_o_gerador_roda() -> None:
    """O teste que faltava. Uma folha listada e ausente parava o programa aqui."""
    css, contagem = build()
    assert css.startswith("/*")
    assert contagem, "nenhum token foi contado: o gerador rodou sem ler nada"


@pytest.mark.parametrize("pagina", sorted(PAGINAS))
def test_toda_folha_listada_existe(pagina: str) -> None:
    faltando = [nome for nome in PAGINAS[pagina] if not (WEB / nome).exists()]
    assert not faltando, (
        f"{pagina} lista folha que não existe: {faltando}. Apagar um arquivo de "
        f"estilo sem tirá-lo daqui quebra o gerador, e nada mais reclama.")


def test_a_lista_de_paginas_e_exatamente_quem_carrega_a_camada() -> None:
    """Entrar na lista sem carregar a folha, ou o contrário, são erros diferentes.

    Página listada que não carrega a camada faz o gerador ler estilo que ninguém
    vê, e foi o que sobrou de `para-escritorios`. Página que carrega e não está
    listada recebe uma camada calculada sem olhar para ela, e foi o que
    aconteceu com `para-voce` — que só passou despercebido porque ela carrega as
    mesmas folhas de `/versoes`.
    """
    assert set(PAGINAS) == paginas_com_a_camada()


@pytest.mark.parametrize("pagina", sorted(PAGINAS))
def test_cada_pagina_lista_as_folhas_que_de_fato_carrega(pagina: str) -> None:
    """Na mesma ordem: a cascata depende dela, e o gerador afirma segui-la."""
    assert PAGINAS[pagina] == folhas_ligadas(pagina)


def test_a_camada_publicada_e_a_que_o_gerador_produz() -> None:
    """A folha diz de si mesma que não se edita à mão. Aqui isso vira regra.

    Editar a saída à mão funciona uma vez e some com a evidência: o gerador
    passa a divergir do publicado, e a divergência só aparece quando alguém o
    executa, o que pode não acontecer por meses.
    """
    esperado, _ = build()
    assert SAIDA.read_text(encoding="utf-8") == esperado, (
        "web/benevente.css não é o que build_site_theme.py produz. "
        "Rode tools/build_site_theme.py e, em seguida, tools/stamp_assets.py.")
