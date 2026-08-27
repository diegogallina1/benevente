"""A paleta tem uma fonte só, e este teste é o que a mantém assim.

O site e o app nasceram de geradores diferentes, cada um com a própria cópia dos
tokens. Estavam idênticos quando unifiquei — conferi os treze comuns nos dois
temas — mas duas cópias iguais hoje são duas cópias divergentes amanhã, e a
divergência apareceria como uma tela levemente diferente da outra: o tipo de
defeito que ninguém reporta e todo mundo sente.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "tools"))
from design_tokens import TEMAS, CLARO, ESCURO, MONO, SANS, css  # noqa: E402

TOKENS_CSS = RAIZ / "web" / "tokens.css"
ARTEFATO = RAIZ / "docs" / "desenho_tela_mapa.html"
APP = RAIZ / "web" / "app.html"
SITE = RAIZ / "web" / "benevente.css"


def _bloco(texto: str, seletor: str) -> dict:
    m = re.search(re.escape(seletor) + r"\s*\{([^}]*)\}", texto)
    return dict(re.findall(r"(--[a-z0-9-]+)\s*:\s*([^;]+)", m.group(1))) if m else {}


def test_os_dois_temas_declaram_exatamente_os_mesmos_tokens():
    """Um token só no escuro vira valor herdado no claro, sem ninguém notar."""
    assert set(ESCURO) == set(CLARO)


def test_o_arquivo_publicado_bate_com_o_modulo():
    assert TOKENS_CSS.exists(), "rode tools/design_tokens.py"
    publicado = TOKENS_CSS.read_text(encoding="utf-8")
    for seletor, esperado in TEMAS:
        achado = _bloco(publicado, seletor)
        for nome, valor in esperado.items():
            assert achado.get(f"--{nome}", "").strip() == valor, f"{seletor} · --{nome}"


def test_o_artefato_carrega_a_mesma_paleta():
    """Ele é um documento só, então embute — mas embute o que o módulo diz."""
    texto = ARTEFATO.read_text(encoding="utf-8")
    for seletor, esperado in TEMAS:
        achado = _bloco(texto, seletor)
        for nome, valor in esperado.items():
            assert achado.get(f"--{nome}", "").strip() == valor, f"artefato · --{nome}"


def test_o_app_do_site_le_o_arquivo_em_vez_de_copiar():
    texto = APP.read_text(encoding="utf-8")
    assert "tokens.css" in texto, "o app do site precisa carregar tokens.css"
    for nome in ("--canvas", "--acao", "--btn"):
        assert f"{nome}: #" not in texto, f"{nome} está duplicado em app.html"


def test_a_folha_do_site_nao_redeclara_a_paleta():
    texto = SITE.read_text(encoding="utf-8")
    for nome in ("--canvas", "--acao", "--fg", "--btn"):
        assert f"{nome}: #" not in texto, f"{nome} está duplicado em benevente.css"


def test_a_tipografia_tambem_vem_do_modulo():
    for arquivo in (TOKENS_CSS, ARTEFATO):
        texto = arquivo.read_text(encoding="utf-8")
        assert SANS.split(",")[0] in texto
        assert MONO.split(",")[0] in texto
    # e a folha do site usa o token, nao a familia escrita a mao
    assert "var(--sans)" in SITE.read_text(encoding="utf-8")


@pytest.mark.parametrize("papel", ["canvas", "card", "fg", "acao", "neg", "btn", "inverso"])
def test_todo_papel_essencial_existe_nos_dois_temas(papel):
    assert papel in ESCURO and papel in CLARO


def _contraste(a: str, b: str) -> float:
    def lum(h):
        h = h.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    claro, escuro = sorted((lum(a), lum(b)), reverse=True)
    return (claro + .05) / (escuro + .05)


def test_o_botao_e_legivel_e_se_destaca_da_pagina():
    """O que importa no botao e a medicao, nao a cor escolhida.

    A versao anterior deste teste exigia ``btn != acao``, que era o rastro de um
    defeito concreto: o botao branco existia porque texto branco sobre o indigo
    dava 2,80 e reprovava. Com o verde da marca no botao os dois passaram a ser a
    mesma cor, e o teste reprovou uma paleta correta — ele guardava a solucao de
    ontem, nao a exigencia. A exigencia e esta: o rotulo tem de ser legivel sobre
    o botao, e o botao tem de se separar da pagina.
    """
    for nome, tema in (("escuro", ESCURO), ("claro", CLARO)):
        rotulo = _contraste(tema["btn"], tema["btn-fg"])
        assert rotulo >= 4.5, f"{nome}: rotulo sobre o botao da {rotulo:.2f}"
        borda = _contraste(tema["btn"], tema["canvas"])
        assert borda >= 3.0, f"{nome}: botao sobre a pagina da {borda:.2f}"


def test_o_acento_e_legivel_como_texto_no_seu_tema():
    """Ele virou verde, e verde claro sobre branco reprova — entao mede-se."""
    for nome, tema in (("escuro", ESCURO), ("claro", CLARO)):
        for fundo in ("canvas", "card"):
            r = _contraste(tema["acao"], tema[fundo])
            assert r >= 4.5, f"{nome}: acento sobre {fundo} da {r:.2f}"


def test_gerar_de_novo_da_o_mesmo_arquivo():
    assert TOKENS_CSS.read_text(encoding="utf-8").replace("\r\n", "\n") == css()
