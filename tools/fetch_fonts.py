"""Baixa as fontes do Google uma vez e as hospeda no próprio site.

Enquanto as páginas carregavam a folha do Google, o IP de cada visitante ia
para o Google antes de a primeira letra aparecer, e a CSP precisava abrir duas
origens externas para isso funcionar. Hospedando os arquivos, o visitante não
fala com terceiro nenhum, a CSP fecha em 'self', e a tipografia deixa de
depender de um serviço fora do nosso controle.

O que este script faz, e por que ele existe em vez de um download manual: a
folha do Google é gerada por User-Agent, então pedir com um navegador moderno é
o que traz woff2 em vez de formatos antigos. Cada face vem com o seu
unicode-range, que é o que faz o navegador baixar só o subconjunto que a página
usa; copiar as fontes sem esse intervalo faria todo visitante baixar tudo. O
registro em data/fontes_hospedadas.json guarda origem, data e SHA-256 de cada
arquivo, para que uma troca silenciosa apareça.

    python tools/fetch_fonts.py
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "web" / "fonts"
FOLHA = ROOT / "web" / "fontes.css"
REGISTRO = ROOT / "data" / "fontes_hospedadas.json"

ORIGEM = ("https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700"
          "&family=Spline+Sans+Mono:wght@400;500&display=swap")
# A folha do Google muda de formato conforme o User-Agent: com um navegador
# moderno ela devolve woff2, que é o que queremos servir.
NAVEGADOR = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")


def _baixa(url: str, *, agente: str = NAVEGADOR, timeout: int = 60) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": agente})
    with urllib.request.urlopen(pedido, timeout=timeout) as resposta:
        return resposta.read()


def _campo(corpo: str, nome: str) -> str:
    achado = re.search(rf"{nome}:\s*([^;]+);", corpo)
    if not achado:
        raise RuntimeError(f"face sem {nome}: {corpo[:120]}")
    return achado.group(1).strip()


def _nome_do_arquivo(familia: str, estilo: str, subconjunto: str, digest: str) -> str:
    """Nome por família, subconjunto e conteúdo, sem o peso.

    As duas famílias são fontes variáveis: o Google devolve o MESMO arquivo para
    os quatro pesos do Figtree e para os dois do Spline Sans Mono, mudando só a
    regra @font-face. Salvar um arquivo por peso guardaria quatro cópias do
    mesmo binário e, pior, faria o navegador baixar cada cópia outra vez, porque
    URL diferente é entrada de cache diferente. Nomeando pelo conteúdo, quatro
    regras apontam para um arquivo só, que é o que a folha do Google faz.

    O hash no nome é o que torna seguro servir com cache imutável: se a fonte
    mudar, o nome muda junto e nenhum navegador fica preso na versão velha.
    """
    base = re.sub(r"[^a-z0-9]+", "-", familia.lower()).strip("-")
    sufixo = "" if estilo == "normal" else f"-{estilo}"
    return f"{base}{sufixo}-{subconjunto}.{digest[:8]}.woff2"


def main() -> None:
    folha = _baixa(ORIGEM).decode("utf-8")
    faces = re.findall(r"/\*\s*([a-z0-9-]+)\s*\*/\s*@font-face\s*\{(.*?)\}", folha, re.S)
    if not faces:
        raise SystemExit("a folha do Google não trouxe nenhuma face; verifique a URL")
    DESTINO.mkdir(parents=True, exist_ok=True)

    regras: list[str] = []
    arquivos: dict[str, dict[str, object]] = {}
    baixados: dict[str, bytes] = {}
    for subconjunto, corpo in faces:
        familia = _campo(corpo, "font-family").strip("'\"")
        estilo = _campo(corpo, "font-style")
        peso = _campo(corpo, "font-weight")
        intervalo = _campo(corpo, "unicode-range")
        url = re.search(r"url\((https://[^)]+)\)", corpo).group(1)
        if url not in baixados:
            baixados[url] = _baixa(url)
        conteudo = baixados[url]
        digest = hashlib.sha256(conteudo).hexdigest()
        nome = _nome_do_arquivo(familia, estilo, subconjunto, digest)
        if nome not in arquivos:
            (DESTINO / nome).write_bytes(conteudo)
            arquivos[nome] = {
                "file": f"web/fonts/{nome}",
                "family": familia,
                "style": estilo,
                "subset": subconjunto,
                "weights": [],
                "bytes": len(conteudo),
                "source_url": url,
                "sha256": digest,
            }
        arquivos[nome]["weights"].append(peso)
        regras.append("\n".join([
            f"/* {familia} {peso} {estilo} · {subconjunto} */",
            "@font-face {",
            f"  font-family: '{familia}';",
            f"  font-style: {estilo};",
            f"  font-weight: {peso};",
            # swap mantém o texto visível durante o carregamento, como fazia a
            # folha do Google; sem isso a página abre em branco por um instante.
            "  font-display: swap;",
            f"  src: url('./fonts/{nome}') format('woff2');",
            f"  unicode-range: {intervalo};",
            "}",
        ]))

    cabecalho = (
        "/* Fontes hospedadas aqui, não no Google.\n"
        " *\n"
        " * Gerado por tools/fetch_fonts.py a partir de\n"
        f" * {ORIGEM}\n"
        " * A procedência de cada arquivo, com SHA-256, está em\n"
        " * data/fontes_hospedadas.json. Não edite esta folha à mão: rode o script.\n"
        " */\n"
    )
    FOLHA.write_text(cabecalho + "\n" + "\n\n".join(regras) + "\n", encoding="utf-8")

    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(json.dumps({
        "schema_version": "1.0.0",
        "fetched_on": date.today().isoformat(),
        "source": ORIGEM,
        "why": ("Servir as fontes do próprio domínio: nenhum visitante fala com o "
                "Google para ler o site, e a CSP fecha style-src e font-src em 'self'."),
        "license": ("Figtree e Spline Sans Mono são SIL Open Font License 1.1, que "
                    "permite hospedagem própria e redistribuição."),
        "stylesheet": "web/fontes.css",
        "note": ("Ambas as famílias são variáveis: o mesmo arquivo serve todos os pesos "
                 "declarados, e por isso há menos arquivos do que regras @font-face."),
        "files": list(arquivos.values()),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Um arquivo que sobrou de uma execução anterior continuaria sendo publicado
    # sem nenhuma regra apontando para ele.
    esperados = set(arquivos)
    for antigo in sorted(DESTINO.glob("*.woff2")):
        if antigo.name not in esperados:
            antigo.unlink()
            print(f"removido órfão: {antigo.name}")

    total = sum(int(item["bytes"]) for item in arquivos.values())
    print(f"{len(arquivos)} arquivos · {total / 1024:.0f} KB · {len(faces)} regras · folha em {FOLHA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
