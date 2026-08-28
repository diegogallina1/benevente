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
  para cima. A elevação vem do degrau de luminância, não de sombra. Os três são
  da mesma família do acento: cinza frio ao lado de verde lê como cor de outro
  lugar, e foi assim que os fundos passaram a parecer "diferentes".

  No claro a página é a superfície mais escura das três, e o cartão é branco.
  Parece invertido e não é: branco puro numa página inteira cansa, e o cartão só
  se destaca se tiver para onde subir. A menta da página é o tom, e o branco do
  cartão é o degrau.
* ``inverso`` — painel escuro sobre página clara. No tema escuro ele não pode
  continuar preto, senão some no fundo: vira superfície elevada.
* ``fg``, ``fg-2`` — texto principal e secundário. ``fg-3`` é só para
  desabilitado, e usá-lo em legenda reprova no contraste.
* ``sobre-inverso``, ``acao-inverso`` — texto e acento **dentro** de painel
  invertido, que não seguem a mesma inversão do resto.
* ``btn`` — fundo de ação com ``btn-fg`` por cima. Leva um verde bem mais claro
  que ``acao``, com rótulo escuro: 5.85 de contraste no claro, 10,66 no escuro.
  Ele não clareia mais que isto porque precisa se separar da própria
  página: em 3.20 contra ela, já está no limite do que um elemento
  não-textual pode ter de contorno.
  A razão é que ``acao`` não pode clarear. Verde como **texto** sobre fundo
  claro trava perto de 5,0 de contraste, e clarear a menta não ajuda porque aí
  quem passa a travar é a própria página. Então o que clareia é tudo o que não
  é texto: botão, barra e halo. É onde está a área de verde que se enxerga.
* ``acao-vivo`` — o verde de **preenchimento**, com ``acao-vivo-fg`` por cima.
  Existe porque ``acao`` precisa ser escuro o bastante para servir de texto
  sobre branco, e escuro demais para pintar barra: barra escura pesa mais que
  o número que ela apresenta. O par foi medido: 5,57 no claro, 10,66 no escuro.
* ``neg`` — perda. É o segundo cromático, e existe porque valor negativo em
  tela financeira é requisito de leitura, não decoração.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "web" / "tokens.css"

#: O claro e o padrao. O guia do design system e escuro por definicao, mas o
#: pedido foi explicito, e preferencia declarada vence guia de estilo.
CLARO = {
    "canvas": "#f4faf7", "card": "#ffffff", "elev": "#e8f3ee", "inverso": "#0d2b22",
    "line": "#dcdfe5", "line-strong": "#b6bcc6", "inverso-linha": "#2c5a49",
    "fg": "#0a0a0a", "fg-2": "#52565e", "fg-3": "#767b85", "sobre-inverso": "#ffffff",
    # O verde da marca em duas intensidades: no claro ele precisa ser escuro o
    # bastante para servir de texto sobre branco (5,35 de contraste); o claro de
    # verdade fica reservado para o que vive dentro de painel escuro.
    "acao": "#0d7a52", "acao-inverso": "#79e1ce", "acao-fraco": "#eaf7f1",
    "acao-vivo": "#35bd87", "acao-vivo-fg": "#0a0a0a",
    "neg": "#c8322f", "neg-fraco": "#fdecec",
    "btn": "#2a9d7b", "btn-fg": "#0a0a0a",
}
ESCURO = {
    "canvas": "#0a0a0a", "card": "#101915", "elev": "#17231e", "inverso": "#17231e",
    "line": "#313131", "line-strong": "#454545", "inverso-linha": "#454545",
    "fg": "#ffffff", "fg-2": "#a7a7a7", "fg-3": "#7c7c7c", "sobre-inverso": "#ffffff",
    "acao": "#5fd3a0", "acao-inverso": "#5fd3a0", "acao-fraco": "#0c2119",
    "acao-vivo": "#5fd3a0", "acao-vivo-fg": "#0a0a0a",
    "neg": "#ff6b6b", "neg-fraco": "#241213",
    "btn": "#5fd3a0", "btn-fg": "#0a0a0a",
}

#: Qual seletor carrega qual tema. Fica aqui, e nao repetido no gerador e nos
#: testes, porque foi exatamente o que precisou mudar quando o claro virou o
#: padrao — e um teste que repete a decisao trava a decisao em vez de conferi-la.
TEMAS = ((":root", CLARO), (':root[data-theme="dark"]', ESCURO))

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
    """O bloco de tokens. O claro é o padrão; o escuro é escolha explícita."""
    partes = []
    if com_cabecalho:
        partes.append(
            "/* Paleta da Benevente. Gerada por tools/design_tokens.py — não edite à mão.\n"
            " * O site e o app leem este mesmo arquivo; o artefato recebe o mesmo bloco\n"
            " * embutido, porque precisa ser um documento só. Um teste compara os três.\n"
            " *\n"
            " * O claro é o padrão, e é o que vale quando nada foi escolhido — a\n"
            " * preferência do sistema não é consultada, para que a página nunca abra\n"
            " * num tema que o :root não descreve. O escuro é escolha explícita e fica\n"
            " * guardada no navegador de quem escolheu.\n"
            " */")
    for seletor, valores in TEMAS:
        partes.append(_bloco(seletor, valores))
    partes.append(
        ", ".join(seletor for seletor, _ in TEMAS) + " {\n"
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
