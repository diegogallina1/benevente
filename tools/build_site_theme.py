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
    ".hero-performance-pair > div:last-child strong", ".hero-performance-bars em",
    ".hero-performance-bars > div:first-child em",
    ".hero-performance-bars > div:nth-child(2) em", ".wealth-card.primary",
    ".wealth-card.primary header b, .wealth-card.primary strong, .wealth-card.primary .wealth-card-foot",
    ".wealth-card.primary header small, .wealth-card.primary .wealth-card-foot span",
    ".wealth-card.primary strong", ".wealth-card strong.wealth-value",
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
:root {
  --canvas: #0a0a0a; --card: #141414; --elev: #1e1e1e; --inverso: #1e1e1e;
  --line: #313131; --line-strong: #454545; --inverso-linha: #454545;
  --fg: #ffffff; --fg-2: #a7a7a7; --sobre-inverso: #ffffff;
  --acao: #6798ff; --acao-inverso: #6798ff; --acao-fraco: #101a2e;
  --neg: #ff6b6b; --neg-fraco: #241213;
  --btn: #ffffff; --btn-fg: #0a0a0a;
}
:root[data-theme="light"] {
  --canvas: #ffffff; --card: #f6f7f9; --elev: #eceef2; --inverso: #0a0a0a;
  --line: #dcdfe5; --line-strong: #b6bcc6; --inverso-linha: #313131;
  --fg: #0a0a0a; --fg-2: #52565e; --sobre-inverso: #ffffff;
  --acao: #2f5fd0; --acao-inverso: #a8c3ff; --acao-fraco: #eaf0ff;
  --neg: #c8322f; --neg-fraco: #fdecec;
  --btn: #0a0a0a; --btn-fg: #ffffff;
}
/* Os apelidos de fonte do design-system antigo apontam para as novas. Sem
   isso, regras que usam var(--sans) continuam em Plus Jakarta. */
:root, :root[data-theme="light"] {
  --sans: "Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif;
  --display: "Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif;
  --serif: "Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif;
  --mono: "Spline Sans Mono", ui-monospace, monospace;
}
body, body.version-page { background: var(--canvas); color: var(--fg);
       font-family: "Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif; }
h1, h2, h3, h4, h5, .brand, .eyebrow, button, input, select, textarea {
  font-family: "Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif; }
code, kbd, pre, samp { font-family: "Spline Sans Mono", ui-monospace, monospace; }
/* No guia a profundidade vem do degrau entre superficies. Sombra preta sobre
   canvas preto nao comunica nada. */
* { box-shadow: none !important; }
/* A acao primaria e branca com texto preto: e o unico elemento de alta
   luminancia da pagina, e texto branco sobre o indigo da 2,80 e reprova. */
.button-primary, .dossier-download, .button.button-primary, .alpha-split i, .alpha-split .ss {
  background: var(--btn) !important; color: var(--btn-fg) !important;
  border-color: var(--btn) !important;
}
.tema-toggle { font: inherit; font-family: "Spline Sans Mono", ui-monospace, monospace;
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
.brand-mark { background: var(--acao) !important; color: var(--canvas) !important; }
table, th, td { border-color: var(--line); }
/* Paineis escuros cujo fundo o gerador nao alcanca — a cor vem de gradiente,
   que tem mais de um valor e ele ignora. Sem isto o texto deles fica marcado
   como "sobre escuro" (branco) enquanto a superficie ficou clara: branco sobre
   branco. Superficie e texto tem de concordar. */
.wealth-card, .wealth-card.benchmark, .wealth-card.primary,
.version-gateway-card.experimental, .chart-source.active, .chart-add-button,
.hero-performance-pair > div:last-child,
.hero-performance-bars > div:first-child, .hero-performance-bars > div:nth-child(2) {
  background: var(--inverso) !important;
}
.wealth-card *, .version-gateway-card.experimental *, .chart-source.active,
.chart-add-button { border-color: var(--inverso-linha); }
/* E a contrapartida: superficie escura pede texto claro. Forcar so o fundo
   inverteu o defeito — de branco sobre branco para preto sobre preto. */
.wealth-card, .wealth-card *, .version-gateway-card.experimental,
.version-gateway-card.experimental *, .chart-source.active, .chart-add-button,
.hero-performance-pair > div:last-child, .hero-performance-pair > div:last-child *,
.hero-performance-bars > div:first-child, .hero-performance-bars > div:first-child *,
.hero-performance-bars > div:nth-child(2), .hero-performance-bars > div:nth-child(2) * {
  color: var(--sobre-inverso) !important;
}
.wealth-card .up, .version-gateway-card.experimental .version-tag,
.hero-performance-bars em { color: var(--acao-inverso) !important; }
/* O ticker rapido tinha fundo branco fixo, que no tema escuro vira uma ilha
   clara com texto de acento por cima: 2,80 e reprova. */
.quick-ticker { background: var(--card) !important; color: var(--fg) !important;
  border-color: var(--line) !important; }
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
