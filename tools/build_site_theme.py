# -*- coding: utf-8 -*-
"""Gera a camada de cor do site: uma folha que troca cor por token.

A primeira tentativa foi substituir os literais dentro das dez folhas de estilo.
Falhou, e o motivo é instrutivo: no desenho original — que só tinha tema claro —
"texto claro para painel escuro" e "cinza sobre página branca" ocupam faixas de
luminância que se sobrepõem. Nenhuma regra baseada só no valor da cor separa as
duas, e o resultado teve 47 falhas de contraste numa página só, com texto em
razão 1,00.

O que faltava era saber **em que superfície cada regra vive**, e isso só o DOM
sabe. A lista ``SOBRE_ESCURO`` veio de medir a página renderizada: são os
seletores cujos elementos ficam sobre painel escuro. Com esse dado, a mesma
classificação passa a acertar.

A folha gerada não altera geometria. Ela só redeclara cor, fundo e borda, e
carrega por último. Layout intacto, e é reversível apagando um ``<link>``.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import colorsys
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SAIDA = WEB / "benevente.css"

#: Folhas que cada página carrega, na ordem. A camada gerada cobre só estas
#: duas páginas: as outras sete seguem intocadas, e o risco fica isolado.
PAGINAS = {
    "index": ["styles.css", "enhancements.css", "lab.css", "commercial.css",
              "paper.css", "refinements.css", "design-system.css"],
    "versoes": ["versions.css", "paper.css", "site-polish.css", "design-system.css",
                "ladder.css"],
    # As quatro carregam exatamente as folhas de /versoes. As tres restantes
    # (btech, benevente-1, benevente-2) sao redirecionamentos de 400 bytes sem
    # estilo nenhum: nao ha o que tematizar.
    "metodo": ["versions.css", "paper.css", "site-polish.css", "design-system.css", "ladder.css"],
    "quant-ai": ["versions.css", "paper.css", "site-polish.css", "design-system.css", "ladder.css"],
    "para-escritorios": ["versions.css", "paper.css", "site-polish.css", "design-system.css",
                         "ladder.css"],
    "limitacoes": ["versions.css", "paper.css", "site-polish.css", "design-system.css",
                   "ladder.css"],
}

#: Medido no navegador: seletores cujos elementos ficam sobre painel escuro.
#: É o dado que a análise estática não tem como deduzir.
SOBRE_ESCURO = {
    ".version-next", ".version-next span", ".version-next strong", ".version-footer",
    ".version-footer .shell", ".version-footer p", ".version-footer a",
    ".version-page .brand-mark", ".version-next, .version-footer .shell",
    ".live-chart-legend i", ".decision-ledger-intro", ".decision-ledger-intro span",
    ".decision-ledger-intro strong", ".alpha-split span", ".alpha-split i",
    ".alpha-split .ss", ".alpha-split .sf", ".alpha-split span:nth-child(1)",
    ".alpha-split span:nth-child(2)", ".dossier-download",
    ".eyebrow span", ".button-primary", ".footer", ".footer .shell", ".footer .brand",
    ".footer p", ".footer span:last-child", ".period.active", ".curve-toggle i",
    ".chart-source, .chart-add-button", ".chart-source.active, .chart-add-button",
    ".chart-add-button", ".chart-return-summary i", ".chart-sidepanel .chart-add-button",
    ".chart-tools .chart-scale.active", ".wealth-card", ".wealth-card header",
    ".wealth-card header b", ".wealth-card header small", ".wealth-card strong",
    ".wealth-card-foot", ".wealth-card-foot .up", ".version-gateway-card.experimental",
    ".experimental .version-tag", ".experimental > p", ".experimental > b",
    ".hero-performance-pair > div:last-child",
    ".hero-performance-pair > div:last-child small, .hero-performance-pair > div:last-child p",
    ".hero-performance-pair > div:last-child strong", ".wealth-card.primary",
    ".wealth-card.primary header b, .wealth-card.primary strong, .wealth-card.primary .wealth-card-foot",
    ".wealth-card.primary header small, .wealth-card.primary .wealth-card-foot span",
    ".wealth-card.primary strong", ".wealth-card strong.wealth-value",
    ".hero-performance-foot a, .text-link, .version-next a, .version-footer a, [data-event-radar] a, .quick-composition a",
}

BORDAS = ("border-color", "border-top-color", "border-bottom-color",
          "border-left-color", "border-right-color")
#: O CSS do site usa muito a forma abreviada: `background: #fff` e
#: `border: 1px solid #ddd`. Ignorá-las deixava fundo e borda sem token, que foi
#: o que a primeira execução mostrou — nenhum --canvas, nenhum --card.
ABREVIADAS = {"background": "background-color", "border": "border-color",
              "border-top": "border-top-color", "border-bottom": "border-bottom-color",
              "border-left": "border-left-color", "border-right": "border-right-color",
              "outline": "border-color"}
PROPS = ("color", "background-color", "fill", "stroke") + BORDAS
COR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|var\(--[a-z0-9-]+\)")


def _hex_para_rgb(h: str) -> tuple[int, int, int] | None:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) < 6:
        return None
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def para_rgb(valor: str, tabela: dict) -> tuple[int, int, int] | None:
    """Resolve hex, rgb() e var(--antigo) para RGB. Transparente devolve None."""
    valor = valor.strip()
    if valor.startswith("var("):
        nome = valor[4:-1].strip()
        vistos = set()
        while nome in tabela and nome not in vistos:
            vistos.add(nome)
            valor = tabela[nome].strip()
            if not valor.startswith("var("):
                break
            nome = valor[4:-1].strip()
        else:
            if valor.startswith("var("):
                return None
    if valor.startswith("#"):
        return _hex_para_rgb(valor)
    if valor.startswith(("rgb(", "rgba(")):
        nums = re.findall(r"[\d.]+", valor)
        if len(nums) >= 4 and float(nums[3]) == 0:
            return None
        if len(nums) >= 3:
            return tuple(int(float(x)) for x in nums[:3])
    return None


def luminancia(rgb: tuple[int, int, int]) -> float:
    c = [x / 255 for x in rgb]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def token(prop: str, rgb: tuple[int, int, int], em_escuro: bool) -> str:
    """A classificação validada no navegador, num lugar só.

    O piso de luminância no teste de "vivo" existe porque azul-marinho quase
    preto tem saturação alta na matemática HSL e leria como acento: sem ele, o
    texto do corpo inteiro virava azul.
    """
    lum = luminancia(rgb)
    matiz, _, sat = colorsys.rgb_to_hls(*[x / 255 for x in rgb])
    vivo = sat >= .32 and lum >= .06
    vermelho = sat >= .25 and (matiz < .045 or matiz > .95) and lum >= .04

    if prop in ("color", "fill"):
        if vermelho: return "--neg"
        if vivo and lum < .62: return "--acao-inverso" if em_escuro else "--acao"
        if em_escuro: return "--sobre-inverso"
        return "--fg" if lum < .12 else "--fg-2"
    if prop == "background-color":
        if vermelho: return "--neg-fraco" if lum >= .6 else "--neg"
        if vivo and .12 <= lum < .62: return "--acao"
        # O creme do site (#f8f6f1) tem saturacao 0,23 pela matematica HSL e
        # luminancia 0,92: com o limite antigo ele virava tom de acento, e o
        # fundo da pagina inteira ficava azulado. Quase branco e canvas.
        if lum >= .90: return "--canvas"
        if sat >= .18 and lum >= .80: return "--acao-fraco"
        if lum >= .93: return "--canvas"
        if lum >= .82: return "--card"
        if lum >= .12: return "--elev"
        return "--inverso"
    if vermelho: return "--neg"
    if vivo and lum < .62: return "--acao"
    if em_escuro: return "--inverso-linha"
    return "--line" if lum >= .60 else "--line-strong"


def tabela_de_tokens(folhas: list[Path]) -> dict:
    tabela = {}
    for f in folhas:
        for m in re.finditer(r"(--[a-z0-9-]+)\s*:\s*([^;{}]+)", f.read_text(encoding="utf-8")):
            tabela.setdefault(m.group(1), m.group(2).strip())
    return tabela


def regras(texto: str):
    """Percorre regras, carregando a condição de media quando houver."""
    pilha, i, n = [], 0, len(texto)
    while i < n:
        abre = texto.find("{", i)
        if abre < 0:
            break
        cabeca = texto[i:abre].strip()
        if cabeca.startswith("@") and not cabeca.startswith("@font-face"):
            pilha.append(cabeca)
            i = abre + 1
            continue
        fecha = texto.find("}", abre)
        if fecha < 0:
            break
        yield " and ".join(pilha), cabeca, texto[abre + 1:fecha]
        i = fecha + 1
        while i < n and texto[i:i + 1].strip() == "" :
            i += 1
        while pilha and texto[i:i + 1] == "}":
            pilha.pop()
            i += 1
            while i < n and texto[i:i + 1].strip() == "":
                i += 1


def build() -> tuple[str, dict]:
    folhas = sorted({WEB / nome for lista in PAGINAS.values() for nome in lista})
    tabela = tabela_de_tokens(folhas)
    por_media: dict[str, list[str]] = {}
    conta: dict[str, int] = {}

    for f in folhas:
        for media, seletor, corpo in regras(f.read_text(encoding="utf-8")):
            if not seletor or seletor.startswith("@"):
                continue
            em_escuro = seletor.strip() in SOBRE_ESCURO
            decls, bordas = [], []
            for d in corpo.split(";"):
                if ":" not in d:
                    continue
                prop, valor = d.split(":", 1)
                prop = prop.strip().lower()
                prop = ABREVIADAS.get(prop, prop)
                if prop not in PROPS:
                    continue
                achadas = COR.findall(valor)
                if len(achadas) != 1:
                    continue
                rgb = para_rgb(achadas[0], tabela)
                if rgb is None:
                    continue
                tk = token(prop, rgb, em_escuro)
                conta[tk] = conta.get(tk, 0) + 1
                (bordas if prop in BORDAS else decls).append((prop, tk))
            if bordas and len({t for _, t in bordas}) == 1:
                decls.append(("border-color", bordas[0][1]))
            else:
                decls.extend(bordas)
            if decls:
                linha = f"{seletor}{{{';'.join(f'{p}:var({t})' for p, t in decls)}}}"
                por_media.setdefault(media, []).append(linha)

    partes = [CABECALHO]
    partes.extend(por_media.get("", []))
    for media, linhas in por_media.items():
        if not media:
            continue
        partes.append(f"{media}{{")
        partes.extend(linhas)
        partes.append("}")
    return "\n".join(partes) + "\n", conta


CABECALHO = """/* Camada de cor do site. Gerada por tools/build_site_theme.py — nao edite a mao.
 *
 * So redeclara cor, fundo e borda; geometria nao e tocada. Carrega por ultimo e
 * vale apenas nas paginas que a incluem, entao remover o <link> desfaz tudo.
 *
 * A decisao de qual token cada regra recebe usa um dado que so o DOM tem: se
 * aquele seletor vive sobre painel escuro. Sem isso, "texto claro de painel" e
 * "cinza sobre branco" sao indistinguiveis pelo valor da cor, e foi o que
 * derrubou a primeira tentativa.
 */
/* Os valores dos tokens vivem em tokens.css, gerado por tools/design_tokens.py
   e carregado antes desta folha. Duas copias iguais hoje sao duas copias
   divergentes amanha. */
/* Rede de seguranca: os tokens da paleta antiga passam a apontar para os novos.
   O gerador reescreve as regras que consegue ler; o que escapar — declaracao com
   mais de uma cor, seletor exotico — ao menos segue o tema em vez de ficar preso
   numa cor fixa. Foi assim que um span com --v-muted sobrou em /para-escritorios. */
:root, :root[data-theme="dark"] {
  --navy: var(--fg); --ink: var(--fg); --ink-strong: var(--fg);
  --v-navy: var(--fg); --v-ink: var(--fg);
  --muted: var(--fg-2); --ink-soft: var(--fg-2); --ink-muted: var(--fg-2);
  --ink-faint: var(--fg-2); --v-muted: var(--fg-2);
  --teal: var(--acao); --brand-green: var(--acao); --v-teal: var(--acao);
  --series-color: var(--acao); --gold: var(--acao); --v-gold: var(--acao);
  --v-line: var(--line); --hairline: var(--line); --hairline-strong: var(--line-strong);
  --cream: var(--canvas); --v-cream: var(--canvas); --surface: var(--canvas);
  --v-white: var(--canvas); --surface-soft: var(--card); --surface-sunk: var(--card);
  --mint: var(--acao-fraco); --surface-mint: var(--acao-fraco); --v-teal-soft: var(--acao-fraco);
  --dark: var(--inverso); --v-dark: var(--inverso); --brand-dark: var(--inverso);
}

body, body.version-page { background: var(--canvas); color: var(--fg);
       font-family: var(--sans); }
h1, h2, h3, h4, h5, .brand, .eyebrow, button, input, select, textarea {
  font-family: var(--sans); }
code, kbd, pre, samp { font-family: var(--mono); }
/* No guia a profundidade vem do degrau entre superficies. Sombra preta sobre
   canvas preto nao comunica nada. */
* { box-shadow: none !important; }
/* A acao primaria carrega o verde da marca. O par foi escolhido por medicao —
   5,35 de contraste no claro, 10,66 no escuro — e nao por gosto: e a mesma
   verificacao que reprovou branco sobre o indigo anterior, com 2,80. */
.button-primary, .dossier-download, .button.button-primary, .alpha-split i, .alpha-split .ss {
  background: var(--btn) !important; color: var(--btn-fg) !important;
  border-color: var(--btn) !important;
}
.tema-toggle { font: inherit; font-family: var(--mono);
  font-size: 11px; letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2);
  background: transparent; border: 1px solid var(--line-strong); border-radius: 9999px;
  min-height: 34px; padding: 0 12px; cursor: pointer; display: inline-flex;
  align-items: center; gap: 6px; white-space: nowrap; }
.tema-toggle:hover { color: var(--fg); border-color: var(--fg-2); }
.tema-toggle:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }
@media (max-width: 780px) { .tema-toggle { min-height: 44px; } }

/* Ajustes a mao: regras que o gerador nao alcanca porque a cor vem de forma
   abreviada com mais de um valor, ou de seletor que ele nao percorre. Sao
   poucas e ficam nomeadas aqui em vez de espalhadas. */
/* !important aqui e deliberado: as regras originais tem especificidade maior, e
   este bloco existe justamente para vencer as poucas que o gerador nao alcanca.
   Fora dele, a camada usa o mesmo seletor da regra original e ganha por ordem. */
details > summary, .annual-decision summary, .live-holdings summary { color: var(--acao) !important; }
.allocation-disclaimer, .live-quality, .research-note, .candidate-disclosure,
.line-chart-caption, .carteira-2026-note { color: var(--fg-2) !important; }
.version-next a, .version-next .button { background: var(--btn) !important;
  color: var(--btn-fg) !important; border-color: var(--btn) !important; }
/* A marca leva a cor do favicon, para que a aba e a pagina sejam a mesma coisa.
   O favicon e o quadrado azul-marinho com o B claro; a cor e dele. */
.brand-mark { background: #102a43 !important; color: #f7fbf8 !important; }
.brand { color: #102a43 !important; }
:root[data-theme="dark"] .brand { color: var(--fg) !important; }

/* Os selos da coluna AÇÃO saiam todos com a mesma menta: seis significados
   diferentes com a mesma aparencia, que e o mesmo que nao ter selo. Cada um
   ganha um sinal proprio, e o sinal e uma FORMA — seta, sinal, traco — porque
   cor sozinha nao carrega significado: o vermelho e o verde da paleta tem
   praticamente o mesmo cinza, e quem nao distingue os dois ficaria sem nada.
   O tom entra depois, so para reforcar o que a forma ja diz.
   "Reduziu" nao ganha vermelho de proposito: diminuir posicao e direcao, nao
   prejuizo, e pintar de perda seria dizer uma coisa que o dado nao diz. */
.alpha-action { display: inline-flex; align-items: center; gap: 5px;
  border: 1px solid transparent; border-radius: 9999px; padding: 2px 9px;
  font-variant-numeric: tabular-nums; }
.alpha-action::before { font-family: var(--mono); font-weight: 500; }
.alpha-entered { background-color: var(--acao) !important; color: var(--btn-fg) !important; }
.alpha-entered::before { content: "+"; }
.alpha-increased { background-color: var(--acao-fraco) !important; color: var(--acao) !important;
  border-color: var(--acao) !important; }
.alpha-increased::before { content: "\2191"; }
.alpha-reduced { background-color: var(--card) !important; color: var(--fg) !important;
  border-color: var(--line-strong) !important; }
.alpha-reduced::before { content: "\2193"; }
.alpha-maintained { background-color: transparent !important; color: var(--fg-2) !important;
  border-color: var(--line) !important; }
.alpha-maintained::before { content: "="; }
.alpha-exited { background-color: var(--neg-fraco) !important; color: var(--neg) !important; }
.alpha-exited::before { content: "\00d7"; }
.alpha-not_held { background-color: transparent !important; color: var(--fg-2) !important;
  border-style: dashed !important; border-color: var(--line-strong) !important; }
.alpha-not_held::before { content: "\2013"; }

/* A faixa projetada vira verde pastel e ganha corpo: era um fio cinza de 1px,
   que num grafico de calibracao e justamente o elemento que precisa ser lido. */
.calib-faixa { stroke: var(--acao-fraco) !important; stroke-width: 9;
  stroke-linecap: round; }
.calib-dentro { fill: var(--acao) !important; stroke: var(--canvas) !important;
  stroke-width: 2; }
.calib-fora { fill: var(--neg) !important; stroke: var(--canvas) !important;
  stroke-width: 2; }
/* A linha divisoria entre perfis sai: o espaco ja separa, e a pagina tinha
   fio cinza demais. */
.calib-perfil { border-top: 0 !important; margin-top: 34px; padding-top: 0; }

/* A linha tracejada do "inicio da avaliacao" sai de vista, a pedido. Vai na cor
   do fundo, e nao em branco literal: no tema escuro o branco viraria um risco
   claro atravessando o grafico, que e o oposto de sumir. */
.line-boundary { stroke: var(--canvas) !important; }

table, th, td { border-color: var(--line); }
/* Paineis escuros cujo fundo o gerador nao alcanca — a cor vem de gradiente,
   que tem mais de um valor e ele ignora. Sem isto o texto deles fica marcado
   como "sobre escuro" (branco) enquanto a superficie ficou clara: branco sobre
   branco. Superficie e texto tem de concordar. */
.wealth-card, .wealth-card.benchmark, .wealth-card.primary,
.version-gateway-card.experimental, .chart-source.active, .chart-add-button,
.hero-performance-pair > div:last-child {
  background: var(--inverso) !important;
}
.wealth-card *, .version-gateway-card.experimental *, .chart-source.active,
.chart-add-button { border-color: var(--inverso-linha); }
/* E a contrapartida: superficie escura pede texto claro. Forcar so o fundo
   inverteu o defeito — de branco sobre branco para preto sobre preto. */
.wealth-card, .wealth-card *, .version-gateway-card.experimental,
.version-gateway-card.experimental *, .chart-source.active, .chart-add-button,
.hero-performance-pair > div:last-child, .hero-performance-pair > div:last-child * {
  color: var(--sobre-inverso) !important;
}
.wealth-card .up, .version-gateway-card.experimental .version-tag {
  color: var(--acao-inverso) !important; }

/* As duas primeiras barras da comparacao eram blocos verde-escuros no meio de
   uma pagina clara: pesavam mais que o numero que deviam apresentar, e eram
   as unicas tres linhas do bloco a nao se parecerem entre si. Viram cartao
   claro como a terceira, e o verde passa para o preenchimento, que e onde ele
   diz alguma coisa.

   Fundo e texto mudam na mesma edicao. Separar os dois foi como eu troquei
   branco-sobre-branco por preto-sobre-preto da ultima vez. */
.hero-performance-bars > div:first-child,
.hero-performance-bars > div:nth-child(2) { background: var(--card) !important; }
.hero-performance-bars > div:first-child, .hero-performance-bars > div:first-child *,
.hero-performance-bars > div:nth-child(2), .hero-performance-bars > div:nth-child(2) * {
  color: var(--fg) !important;
}
.hero-performance-bars i { background: var(--acao-fraco) !important; }
.hero-performance-bars em, .hero-performance-bars > div:first-child em,
.hero-performance-bars > div:nth-child(2) em { background: var(--acao) !important; }
/* O ticker rapido tinha fundo branco fixo, que no tema escuro vira uma ilha
   clara com texto de acento por cima: 2,80 e reprova. */
.quick-ticker { background: var(--card) !important; color: var(--fg) !important;
  border-color: var(--line) !important; }
/* Link dentro de texto corrido. O gerador cobre os que tem classe; estes vem
   de seletores como ".paper-page p" que definem so a cor do paragrafo, e o
   link herdava a cor antiga de marca — 1,85 de contraste no tema escuro. */
p a, li a, td a, dd a, figcaption a { color: var(--acao) !important; }
p a:hover, li a:hover, td a:hover { color: var(--acao-inverso) !important; }
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    css, conta = build()
    print(f"{'SIMULAÇÃO' if args.dry_run else SAIDA.name}: {len(css)/1024:.1f} KB · "
          f"{css.count('{') - css.count('@media')} regras")
    for tk, n in sorted(conta.items(), key=lambda x: -x[1]):
        print(f"  {tk:<18}{n:>5}")
    if not args.dry_run:
        SAIDA.write_text(css, encoding="utf-8")


if __name__ == "__main__":
    main()
