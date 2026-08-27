# -*- coding: utf-8 -*-
"""Troca as cores literais do site por tokens semânticos.

O site acumulou 456 cores literais em 825 lugares, dez arquivos, 121 KB. Não dá
para ter tema claro e escuro com isso: cada valor teria de virar dois. E não dá
para remapear à mão sem errar dezenas de vezes.

Este programa classifica cada cor pelo papel em que ela aparece — texto, fundo,
borda — e pela luminância, e substitui pelo token correspondente. A classificação
é o trabalho intelectual; a substituição é mecânica e auditável, e roda com
``--dry-run`` antes de escrever qualquer coisa.

O caso que exige cuidado são as seções invertidas: painéis escuros sobre página
clara, como o rodapé e o painel do herói. Elas não podem virar ``--canvas``,
senão no tema escuro ficam pretas sobre pretas e somem. Ganham token próprio,
que no claro é escuro e no escuro é superfície elevada.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import collections
import colorsys
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
MAPA = ROOT / "data" / "site_color_tokens.json"
COR = re.compile(r"#[0-9a-fA-F]{3,8}\b")

#: Cores que não devem ser tocadas: transparências e o branco puro dentro de
#: gradientes de máscara, onde o valor é geometria e não paleta.
IGNORAR = {"#00000000", "#ffffff00"}


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def luminancia(h: str) -> float:
    c = [x / 255 for x in _rgb(h)]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def matiz_saturacao(h: str) -> tuple[float, float]:
    r, g, b = [x / 255 for x in _rgb(h)]
    matiz, _, sat = colorsys.rgb_to_hls(r, g, b)
    return matiz, sat


def familia(h: str) -> str:
    matiz, sat = matiz_saturacao(h)
    if sat < .10:
        return "neutro"
    if matiz < .05 or matiz > .95:
        return "vermelho"
    if matiz < .13:
        return "ouro"
    return "acento"


def papel(declaracao: str) -> str:
    """Em que propriedade a cor aparece. É o que revela o papel dela."""
    if ":" not in declaracao:
        return "?"
    prop = declaracao.split(":")[0].strip().lower().split()[-1]
    if prop in ("color", "fill"):
        return "texto"
    if "background" in prop:
        return "fundo"
    if "border" in prop or prop in ("stroke", "outline"):
        return "borda"
    if "shadow" in prop:
        return "sombra"
    return "?"


def token(cor: str, onde: str) -> str | None:
    """A regra de classificação, num lugar só.

    A ordem importa. Família vem antes de luminância porque o teal de marca do
    site é escuro (luminância 0,17): classificado só pelo brilho, ele viraria
    texto secundário e o site perderia o acento inteiro.

    E cor clara e saturada quase sempre está sobre painel escuro. Ela ganha
    token próprio: no tema claro precisa continuar clara, senão some no painel;
    no escuro é o mesmo acento do resto.
    """
    lum, fam = luminancia(cor), familia(cor)
    _, sat = matiz_saturacao(cor)
    if fam == "vermelho":
        return "--neg-fraco" if (onde == "fundo" and lum > .5) else "--neg"
    # O ouro do site é decorativo e o guia admite um acento só: vira acento.
    acentuada = fam in ("acento", "ouro") and sat >= .30

    if onde == "fundo":
        if lum >= .93: return "--canvas"
        if lum >= .82: return "--card"
        if acentuada and .12 <= lum < .60: return "--acao"
        if lum >= .60: return "--elev"
        if lum >= .12: return "--elev"
        return "--inverso"
    if onde == "borda":
        if acentuada and lum < .62: return "--acao"
        if lum >= .60: return "--line"
        if lum >= .25: return "--line-strong"
        return "--inverso-linha"
    if onde == "texto":
        if acentuada:
            return "--acao-inverso" if lum >= .62 else "--acao"
        if lum < .12: return "--fg"
        if lum < .62: return "--fg-2"
        return "--sobre-inverso"
    return None


def normaliza(cor: str) -> str:
    cor = cor.lower()
    if len(cor) == 4:
        cor = "#" + "".join(c * 2 for c in cor[1:])
    return cor


def processar(escrever: bool) -> dict:
    resumo: collections.Counter = collections.Counter()
    exemplos: dict[str, set] = collections.defaultdict(set)
    intocadas: collections.Counter = collections.Counter()

    for arquivo in sorted(WEB.glob("*.css")):
        texto = arquivo.read_text(encoding="utf-8")
        saida, pos = [], 0
        # Percorre declaração a declaração para conhecer a propriedade de cada cor.
        for m in re.finditer(r"[^;{}]+", texto):
            trecho = m.group(0)
            if not COR.search(trecho):
                continue
            onde = papel(trecho)
            novo = trecho
            for bruta in COR.findall(trecho):
                cor = normaliza(bruta)
                if cor in IGNORAR or len(bruta) > 7:
                    intocadas[bruta.lower()] += 1
                    continue
                alvo = token(cor, onde)
                if alvo is None:
                    intocadas[cor] += 1
                    continue
                novo = novo.replace(bruta, f"var({alvo})")
                resumo[alvo] += 1
                exemplos[alvo].add(cor)
            if novo != trecho:
                saida.append((m.start(), m.end(), novo))
        if escrever and saida:
            partes, pos = [], 0
            for ini, fim, novo in saida:
                partes.append(texto[pos:ini]); partes.append(novo); pos = fim
            partes.append(texto[pos:])
            arquivo.write_text("".join(partes), encoding="utf-8")

    return {"resumo": dict(resumo.most_common()),
            "exemplos": {k: sorted(v)[:6] for k, v in sorted(exemplos.items())},
            "intocadas": dict(intocadas.most_common(12))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()

    r = processar(escrever=not args.dry_run)
    print(("SIMULAÇÃO" if args.dry_run else "APLICADO") +
          f" · {sum(r['resumo'].values())} substituições\n")
    for tk, n in r["resumo"].items():
        print(f"  {tk:<18}{n:>5}   ex: {', '.join(r['exemplos'][tk][:5])}")
    if r["intocadas"]:
        print(f"\n  não tocadas ({sum(r['intocadas'].values())}): "
              f"{', '.join(f'{c}×{n}' for c, n in list(r['intocadas'].items())[:8])}")
    if not args.dry_run:
        MAPA.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
