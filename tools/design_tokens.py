# -*- coding: utf-8 -*-
"""A paleta, num lugar só.

O site e o app nasceram de geradores diferentes e cada um trazia a própria cópia
dos tokens. Estavam idênticos — conferi os treze comuns nos dois temas antes de
unificar — mas duas cópias iguais hoje são duas cópias divergentes amanhã, e a
divergência apareceria como uma tela levemente diferente da outra, que é o tipo
de defeito que ninguém reporta e todo mundo sente.

Agora os valores vivem aqui. O site carrega ``web/tokens.css``, gerado deste
módulo; o app da web carrega o mesmo arquivo; e o artefato, que precisa ser um
documento só, recebe o mesmo bloco embutido. Um teste compara os três.

Os papéis, porque nomear cor por aparência envelhece mal:

* ``canvas``, ``card``, ``elev`` — a pilha de superfícies, do fundo da página
  para cima. A elevação vem do degrau de luminância, não de sombra.
* ``inverso`` — painel escuro sobre página clara. No tema escuro ele não pode
  continuar preto, senão some no fundo: vira superfície elevada.
* ``fg``, ``fg-2`` — texto principal e secundário. ``fg-3`` é só para
  desabilitado, e usá-lo em legenda reprova no contraste.
* ``sobre-inverso``, ``acao-inverso`` — texto e acento **dentro** de painel
  invertido, que não seguem a mesma inversão do resto.
* ``btn`` — fundo de ação com ``btn-fg`` por cima. Nunca é o acento: texto
  branco sobre o indigo dá 2,80 de contraste e reprova. É por isso que a ação
  primária é branca com texto preto.
* ``neg`` — perda. É o segundo cromático, e existe porque valor negativo em
  tela financeira é requisito de leitura, não decoração.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "web" / "tokens.css"

ESCURO = {
    "canvas": "#0a0a0a", "card": "#141414", "elev": "#1e1e1e", "inverso": "#1e1e1e",
    "line": "#313131", "line-strong": "#454545", "inverso-linha": "#454545",
    "fg": "#ffffff", "fg-2": "#a7a7a7", "fg-3": "#7c7c7c", "sobre-inverso": "#ffffff",
    "acao": "#6798ff", "acao-inverso": "#6798ff", "acao-fraco": "#101a2e",
    "neg": "#ff6b6b", "neg-fraco": "#241213",
    "btn": "#ffffff", "btn-fg": "#0a0a0a",
}
CLARO = {
    "canvas": "#ffffff", "card": "#f6f7f9", "elev": "#eceef2", "inverso": "#0a0a0a",
    "line": "#dcdfe5", "line-strong": "#b6bcc6", "inverso-linha": "#313131",
    "fg": "#0a0a0a", "fg-2": "#52565e", "fg-3": "#767b85", "sobre-inverso": "#ffffff",
    "acao": "#2f5fd0", "acao-inverso": "#a8c3ff", "acao-fraco": "#eaf0ff",
    "neg": "#c8322f", "neg-fraco": "#fdecec",
    "btn": "#0a0a0a", "btn-fg": "#ffffff",
}

SANS = '"Schibsted Grotesk", ui-sans-serif, system-ui, -apple-system, sans-serif'
MONO = '"Spline Sans Mono", ui-monospace, SFMono-Regular, Menlo, monospace'

FONTES_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    'family=Schibsted+Grotesk:wght@400;500;600;700&'
    'family=Spline+Sans+Mono:wght@400;500&display=swap">'
)


def _bloco(seletor: str, valores: dict) -> str:
    linhas = "\n".join(f"  --{nome}: {valor};" for nome, valor in valores.items())
    return f"{seletor} {{\n{linhas}\n}}"


def css(com_cabecalho: bool = True) -> str:
    """O bloco de tokens. O escuro é o padrão; o claro é escolha explícita."""
    partes = []
    if com_cabecalho:
        partes.append(
            "/* Paleta da Benevente. Gerada por tools/design_tokens.py — não edite à mão.\n"
            " * O site e o app leem este mesmo arquivo; o artefato recebe o mesmo bloco\n"
            " * embutido, porque precisa ser um documento só. Um teste compara os três.\n"
            " *\n"
            " * O escuro é o padrão: o design system é escuro por definição, então a\n"
            " * preferência do sistema não é consultada. O claro é escolha explícita e\n"
            " * fica guardada no navegador de quem escolheu.\n"
            " */")
    partes.append(_bloco(":root", ESCURO))
    partes.append(_bloco(':root[data-theme="light"]', CLARO))
    partes.append(
        ":root, :root[data-theme=\"light\"] {\n"
        f"  --sans: {SANS};\n"
        f"  --display: {SANS};\n"
        f"  --serif: {SANS};\n"
        f"  --mono: {MONO};\n"
        "}")
    return "\n".join(partes) + "\n"


def write() -> Path:
    CSS.parent.mkdir(parents=True, exist_ok=True)
    CSS.write_bytes(css().encode("utf-8"))
    return CSS


def main() -> None:
    caminho = write()
    print(f"{caminho.relative_to(ROOT)}: {caminho.stat().st_size} bytes · "
          f"{len(ESCURO)} tokens × 2 temas")


if __name__ == "__main__":
    main()
