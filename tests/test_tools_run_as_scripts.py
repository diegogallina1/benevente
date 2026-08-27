"""Todo programa de tools/ tem de importar como script, não só sob pytest.

Este arquivo existe por causa de uma falha de CI, e a falha é instrutiva. Ao
rodar ``python tools/x.py``, o Python coloca ``tools/`` no sys.path — não a raiz
do repositório. Os módulos de pesquisa vivem na raiz, então um tool que importa
``portfolio_risk`` sem ajustar o caminho quebra na primeira linha.

Sob pytest isso nunca aparece: o pytest insere a raiz sozinho. O resultado é a
pior combinação possível — o teste passa, a suíte fica verde, e o programa
quebra em produção. Foi exatamente o que aconteceu: a correção da camada de
proteção do monitor foi validada por teste e nunca executada como script.

Por isso o teste abaixo não importa nada de forma conveniente. Ele monta o
sys.path idêntico ao de ``python tools/x.py`` e executa o módulo, e a versão
estática varre a árvore de sintaxe atrás do mesmo defeito nos arquivos que são
caros demais para executar.
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
TOOLS = RAIZ / "tools"
MODULOS_DA_RAIZ = {p.stem for p in RAIZ.glob("*.py")}

#: Executar estes custa minutos ou toca a rede; a checagem estática cobre o
#: defeito de caminho, que é o que este arquivo protege.
CAROS = {"build_ladder_web_evidence", "persist_cadence_v2", "update_profile_books",
         "update_live_performance", "build_home_bundle", "stamp_assets"}


def _importa_da_raiz(arvore: ast.AST) -> set[str]:
    """Módulos que moram na raiz e este arquivo importa."""
    achados: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            if no.module.split(".")[0] in MODULOS_DA_RAIZ:
                achados.add(no.module)
        elif isinstance(no, ast.Import):
            for alias in no.names:
                if alias.name.split(".")[0] in MODULOS_DA_RAIZ:
                    achados.add(alias.name)
    return achados


@pytest.mark.parametrize("caminho", sorted(TOOLS.glob("*.py")), ids=lambda p: p.stem)
def test_o_tool_acha_os_modulos_da_raiz(caminho: Path):
    """Quem importa da raiz precisa pôr a raiz no sys.path — sem exceção."""
    fonte = caminho.read_text(encoding="utf-8")
    da_raiz = _importa_da_raiz(ast.parse(fonte))
    if not da_raiz:
        return
    assert "sys.path.insert" in fonte, (
        f"{caminho.name} importa {sorted(da_raiz)} da raiz do repositório, mas rodado como "
        f"script só enxerga tools/. Falta 'sys.path.insert(0, str(ROOT))'.")


@pytest.mark.parametrize(
    "caminho",
    sorted(p for p in TOOLS.glob("*.py") if p.stem not in CAROS),
    ids=lambda p: p.stem)
def test_o_tool_executa_com_o_sys_path_de_script(caminho: Path):
    """O teste de verdade: montar o sys.path do script e importar."""
    salvo = list(sys.path)
    sys.path.insert(0, str(caminho.parent))
    try:
        spec = importlib.util.spec_from_file_location(caminho.stem, caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
    except ModuleNotFoundError as erro:
        pytest.fail(f"{caminho.name} não importa como script: {erro}")
    finally:
        sys.path[:] = salvo
        sys.modules.pop(caminho.stem, None)


def test_os_tools_caros_pelo_menos_resolvem_os_imports():
    """Para os que não dá para executar, confere que os módulos existem."""
    faltando = []
    for nome in sorted(CAROS):
        caminho = TOOLS / f"{nome}.py"
        if not caminho.exists():
            continue
        for modulo in sorted(_importa_da_raiz(ast.parse(caminho.read_text(encoding="utf-8")))):
            if not (RAIZ / f"{modulo.split('.')[0]}.py").exists():
                faltando.append(f"{caminho.name} -> {modulo}")
    assert not faltando, "importam módulo inexistente na raiz:\n  " + "\n  ".join(faltando)
