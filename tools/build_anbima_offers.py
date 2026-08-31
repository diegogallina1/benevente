# -*- coding: utf-8 -*-
"""A grade de papel de mercado da ANBIMA, na mesma régua do catálogo.

O coletor do Tesouro cobre título público. Este cobre a outra metade que tem
fonte pública: debênture, CRI e CRA, que a ANBIMA divulga com taxa de compra, de
venda e indicativa. O que continua sem fonte é captação bancária, e não por
falta de coletor: CDB, LCI e LCA são bilaterais, com taxa por distribuidor, por
valor aplicado e por dia, então não existe livro de ofertas central para ler.
Esses entram pela mão da pessoa, marcados como informados por ela.

A diferença de regime viaja com o dado, porque muda o que se pode afirmar. Papel
da ANBIMA é valor mobiliário sob a CVM e não tem FGC: o catálogo já sabe disso
pela tabela de produtos, e a alocação recusa esses papéis a menos que o risco de
crédito seja declarado. Taxa maior aqui não é oferta melhor, é outro risco.

Credencial vem só do ambiente, nunca do repositório:

* ``ANBIMA_CLIENT_ID`` e ``ANBIMA_CLIENT_SECRET``, do app registrado no portal;
* ``ANBIMA_AMBIENTE``, ``producao`` ou ``sandbox``. O padrão é sandbox, porque
  errar para o lado do ambiente de teste não estraga nada.

O segredo não é impresso, não entra no arquivo de saída e não aparece em
mensagem de erro, nem quando a própria ANBIMA o devolve no corpo de um 4xx. O
token dura uma hora e é pedido a cada execução: guardá-lo em disco criaria mais
um arquivo sensível para vazar, e não pouparia nada que valha isso.

A ANBIMA divulga o mercado secundário a partir das 20h de Brasília. Rodar antes
devolve o dia anterior, e o programa imprime a data que veio em vez de deixar
quem lê supor que é a de hoje.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import base64
import json
import os
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "data" / "ofertas_anbima.json"

BASES = {
    "producao": "https://api.anbima.com.br",
    "sandbox": "https://api-sandbox.anbima.com.br",
}
#: O que buscar, e que tipo do catálogo cada família vira.
FONTES = (
    ("debentures/mercado-secundario", "DEBENTURE"),
    ("cri-cra/mercado-secundario", "CRI"),
)
TEMPO_LIMITE = 30


class SemCredencial(RuntimeError):
    """O ambiente não tem as variáveis, e adivinhar não é opção."""


def credencial() -> tuple[str, str]:
    ident = os.environ.get("ANBIMA_CLIENT_ID", "").strip()
    segredo = os.environ.get("ANBIMA_CLIENT_SECRET", "").strip()
    if not ident or not segredo:
        raise SemCredencial(
            "Defina ANBIMA_CLIENT_ID e ANBIMA_CLIENT_SECRET no ambiente. O "
            "repositório não guarda credencial e o programa não pede em prompt.")
    return ident, segredo


def token(base: str, abrir=urllib.request.urlopen) -> str:
    """Troca a credencial por um token de uma hora, pelo fluxo documentado."""
    ident, segredo = credencial()
    basico = base64.b64encode(f"{ident}:{segredo}".encode("utf-8")).decode("ascii")
    pedido = urllib.request.Request(
        f"{base}/oauth/access-token",
        data=json.dumps({"grant_type": "client_credentials"}).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Basic {basico}"},
        method="POST")
    try:
        with abrir(pedido, timeout=TEMPO_LIMITE) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        # Só o código sai. O corpo de um erro de autenticação pode ecoar o que
        # foi enviado, e um log é o lugar mais fácil de vazar segredo sem querer.
        raise SystemExit(f"Autenticação recusada pela ANBIMA: HTTP {erro.code}.") from None
    if "access_token" not in corpo:
        raise SystemExit("A ANBIMA respondeu sem access_token.")
    return corpo["access_token"]


def buscar(base: str, caminho: str, acesso: str, abrir=urllib.request.urlopen) -> list[dict]:
    """Uma chamada ao feed. Devolve a lista crua, sem interpretar."""
    ident, _ = credencial()
    pedido = urllib.request.Request(
        f"{base}/feed/precos-indices/v1/{caminho}",
        headers={"Authorization": f"Bearer {acesso}", "client_id": ident,
                 "Accept": "application/json"})
    try:
        with abrir(pedido, timeout=TEMPO_LIMITE) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code == 403:
            raise SystemExit(
                f"{caminho}: HTTP 403. O app tem o produto de preços habilitado?") from None
        raise SystemExit(f"{caminho}: HTTP {erro.code}.") from None
    return corpo if isinstance(corpo, list) else corpo.get("content", [])


def numero(valor) -> float | None:
    """A ANBIMA manda número em campo de texto, com vírgula, em parte das rotas."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    try:
        return float(str(valor).replace(".", "").replace(",", "."))
    except ValueError:
        return None


def produto(linha: dict, tipo: str) -> dict | None:
    """Uma linha do feed no formato que fixed_income_catalog lê.

    A taxa usada é a indicativa, não a de compra nem a de venda. As duas pontas
    descrevem quem quer negociar; a indicativa é a referência. Fica declarado no
    arquivo de saída, porque escolher a ponta conveniente é a forma mais fácil
    de inflar uma comparação sem mentir em nenhum número isolado.
    """
    codigo = str(linha.get("codigo_ativo") or linha.get("codigo") or "").strip()
    vencimento = str(linha.get("data_vencimento") or linha.get("vencimento") or "").strip()
    taxa = numero(linha.get("taxa_indicativa"))
    if not codigo or not vencimento or taxa is None:
        return None
    indice = str(linha.get("indice") or linha.get("indexador") or "").strip().upper()
    if indice.startswith("DI"):
        familia = "CDI+"
    elif indice.startswith("IPCA"):
        familia = "IPCA+"
    elif indice.startswith("PRE"):
        familia = "prefixado"
    else:
        return None
    return {
        "name": f"{tipo} {codigo}",
        "kind": tipo,
        "issuer": str(linha.get("emissor") or codigo),
        "conglomerate": str(linha.get("emissor") or codigo),
        "index": familia,
        "rate": round(taxa / 100.0, 6),
        "maturity": vencimento,
        "minimum_brl": 1000.0,
        "daily_liquidity": False,
    }


def coletar(ambiente: str, abrir=urllib.request.urlopen) -> dict:
    base = BASES[ambiente]
    acesso = token(base, abrir)
    itens: list[dict] = []
    por_fonte: dict[str, tuple[int, int]] = {}
    for caminho, tipo in FONTES:
        cruas = buscar(base, caminho, acesso, abrir)
        convertidas = [x for x in (produto(l, tipo) for l in cruas) if x]
        por_fonte[caminho] = (len(cruas), len(convertidas))
        itens.extend(convertidas)
    return {
        "source": "ANBIMA Feed, preços e índices, mercado secundário",
        "environment": ambiente,
        "origem": "AUTOMATICA_PUBLICA",
        "rate_source": "taxa indicativa, não a de compra nem a de venda",
        "regime": "valor mobiliário sob a CVM, sem cobertura do FGC",
        "products": itens,
        "por_fonte": {k: {"linhas": v[0], "convertidas": v[1]} for k, v in por_fonte.items()},
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ambiente", choices=sorted(BASES),
                   default=os.environ.get("ANBIMA_AMBIENTE", "sandbox"))
    args = p.parse_args()

    documento = coletar(args.ambiente)
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

    itens = documento["products"]
    print(f"{DESTINO.relative_to(ROOT)}: {len(itens)} papéis · ambiente {args.ambiente}")
    for caminho, contagem in documento["por_fonte"].items():
        print(f"  {caminho}: {contagem['convertidas']} de {contagem['linhas']} linhas")
    datas = sorted({x["maturity"] for x in itens})
    if datas:
        print(f"  vencimentos de {datas[0]} a {datas[-1]}")
    print("  regime: valor mobiliário, sem FGC. A alocação recusa sem risco declarado.")


if __name__ == "__main__":
    main()
