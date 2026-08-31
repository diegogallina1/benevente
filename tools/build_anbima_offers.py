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
DESTINO_FUNDOS = ROOT / "data" / "fundos_anbima.json"
#: Onde a credencial pode morar sem entrar no repositório. Os dois nomes já
#: estão no .gitignore, e nenhum deles é lido de outro lugar do projeto.
ARQUIVOS_DE_CREDENCIAL = (ROOT / ".env.anbima", ROOT / ".env.local")

BASES = {
    "producao": "https://api.anbima.com.br",
    "sandbox": "https://api-sandbox.anbima.com.br",
}
#: O que buscar, e que tipo do catálogo cada família vira.
FONTES = (
    ("debentures/mercado-secundario", "DEBENTURE"),
    ("cri-cra/mercado-secundario", "CRI"),
)
#: Da mais nova para a mais velha. A ANBIMA publica v1 e v2 do pacote de preços,
#: e os caminhos do v2 não estão na documentação pública que dá para ler daqui.
#: Então a versão é configuração, e não um palpite escrito no código: em "auto"
#: o programa tenta a mais nova, aceita 404 como "esta rota não existe nesta
#: versão", cai para a anterior e grava qual respondeu. Descobrir é honesto;
#: fixar v2 sem conferir seria publicar um chute com cara de fato.
VERSOES = ("v2", "v1")
TEMPO_LIMITE = 30


#: ``abrir`` é sempre por nome. Quando a versão virou parâmetro, um teste passou
#: a função falsa na posição dela e o "abrir" caiu no padrão: o teste foi para a
#: rede de verdade sem ninguém notar. Argumento posicional não deve conseguir
#: trocar um dublê por um socket.
class RotaAusente(RuntimeError):
    """A rota não existe nesta versão da API. Serve para cair para a anterior."""


class SemCredencial(RuntimeError):
    """O ambiente não tem as variáveis, e adivinhar não é opção."""


def _do_arquivo() -> dict[str, str]:
    """Lê CHAVE=valor de um .env ignorado pelo git, se existir.

    Existe porque exportar variável na linha de comando deixa o segredo no
    histórico do shell, e porque "não sei onde por" é o começo de todo segredo
    commitado. O arquivo não é criado por este programa e não é lido de nenhum
    outro lugar do projeto: quem o escreve é a pessoa, uma vez.
    """
    achados: dict[str, str] = {}
    for caminho in ARQUIVOS_DE_CREDENCIAL:
        if not caminho.exists():
            continue
        for linha in caminho.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            if chave.startswith("ANBIMA_"):
                achados.setdefault(chave, valor.strip().strip('"').strip("'"))
    return achados


def credencial() -> tuple[str, str]:
    # O ambiente vence o arquivo: numa máquina de produção a variável é quem
    # manda, e o arquivo é conveniência de quem roda na própria máquina.
    arquivo = _do_arquivo()
    ident = (os.environ.get("ANBIMA_CLIENT_ID") or arquivo.get("ANBIMA_CLIENT_ID", "")).strip()
    segredo = (os.environ.get("ANBIMA_CLIENT_SECRET")
               or arquivo.get("ANBIMA_CLIENT_SECRET", "")).strip()
    if not ident or not segredo:
        raise SemCredencial(
            "Faltam ANBIMA_CLIENT_ID e ANBIMA_CLIENT_SECRET. Ponha as duas no "
            f"arquivo {ARQUIVOS_DE_CREDENCIAL[0].name}, na raiz do repositório, "
            "uma por linha no formato CHAVE=valor. O arquivo já está no "
            ".gitignore. Variável de ambiente também serve e tem precedência. O "
            "repositório não guarda credencial e o programa não pede em prompt.")
    return ident, segredo


def token(base: str, *, abrir=urllib.request.urlopen) -> str:
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


def buscar(base: str, caminho: str, acesso: str, versao: str = "v1", *,
           feed: str = "precos-indices", abrir=urllib.request.urlopen) -> list[dict]:
    """Uma chamada a um feed, numa versão. Devolve a lista crua, sem interpretar."""
    ident, _ = credencial()
    pedido = urllib.request.Request(
        f"{base}/feed/{feed}/{versao}/{caminho}",
        headers={"Authorization": f"Bearer {acesso}", "client_id": ident,
                 "Accept": "application/json"})
    try:
        with abrir(pedido, timeout=TEMPO_LIMITE) as resposta:
            corpo = json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        if erro.code == 404:
            # Rota inexistente nesta versão. Quem chamou decide se tenta outra.
            raise RotaAusente(f"{versao}/{caminho}") from None
        if erro.code == 403:
            raise SystemExit(
                f"{versao}/{caminho}: HTTP 403. O app tem esse produto habilitado?") from None
        raise SystemExit(f"{versao}/{caminho}: HTTP {erro.code}.") from None
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


def buscar_na_melhor_versao(base: str, caminho: str, acesso: str, versoes, *,
                            abrir=urllib.request.urlopen) -> tuple[list[dict], str]:
    """Tenta as versões na ordem dada e devolve a primeira que responder.

    Só o 404 faz descer de versão. Um 403 é outra coisa, o app não tem o produto
    habilitado, e cair para a versão anterior nesse caso esconderia o problema
    de contratação atrás de um resultado vazio.
    """
    ausentes = []
    for versao in versoes:
        try:
            return buscar(base, caminho, acesso, versao, abrir=abrir), versao
        except RotaAusente:
            ausentes.append(versao)
    raise SystemExit(f"{caminho}: rota ausente em {', '.join(ausentes)}.")


def coletar(ambiente: str, versao: str = "auto", *, abrir=urllib.request.urlopen) -> dict:
    base = BASES[ambiente]
    acesso = token(base, abrir=abrir)
    versoes = VERSOES if versao == "auto" else (versao,)
    itens: list[dict] = []
    por_fonte: dict[str, dict] = {}
    for caminho, tipo in FONTES:
        cruas, respondeu = buscar_na_melhor_versao(base, caminho, acesso, versoes, abrir=abrir)
        convertidas = [x for x in (produto(l, tipo) for l in cruas) if x]
        # Qual versão serviu cada rota fica no arquivo. Sem isso, uma migração
        # silenciosa de formato apareceria como mudança de mercado.
        por_fonte[caminho] = {"linhas": len(cruas), "convertidas": len(convertidas),
                              "versao": respondeu}
        itens.extend(convertidas)
    return {
        "source": "ANBIMA Feed, preços e índices, mercado secundário",
        "environment": ambiente,
        "origem": "AUTOMATICA_PUBLICA",
        "rate_source": "taxa indicativa, não a de compra nem a de venda",
        "regime": "valor mobiliário sob a CVM, sem cobertura do FGC",
        "api_version_requested": versao,
        "products": itens,
        "por_fonte": por_fonte,
    }


#: As rotas de fundos, sob outro feed. A documentação pública mostra o padrão
#: /feed/fundos/v1/fundos/, mesmo para o produto que a ANBIMA chama de v2, então
#: aqui vale a mesma disciplina dos preços: tenta a mais nova, cai no 404.
ROTAS_DE_FUNDOS = ("fundos", "fundos/patrimonio-liquido-segmento")


def coletar_fundos(ambiente: str, versao: str = "auto", *,
                   abrir=urllib.request.urlopen) -> dict:
    """O cadastro de fundos, guardado separado das ofertas de propósito.

    Um fundo não tem taxa contratada: tem retorno realizado, taxa de
    administração e come-cotas. Pôr isso na mesma lista de um CDB a 110% do CDI
    compararia um histórico com uma promessa, que é o erro que a régua existe
    para evitar. Então os dois arquivos são distintos, e quem quiser comparar
    fundo com papel precisa dizer sob qual hipótese de retorno futuro, que é uma
    escolha de quem compara e não um dado da ANBIMA.
    """
    base = BASES[ambiente]
    acesso = token(base, abrir=abrir)
    versoes = VERSOES if versao == "auto" else (versao,)
    conteudo: dict[str, dict] = {}
    for rota in ROTAS_DE_FUNDOS:
        ausentes = []
        for tentativa in versoes:
            try:
                linhas = buscar(base, rota, acesso, tentativa, feed="fundos", abrir=abrir)
            except RotaAusente:
                ausentes.append(tentativa)
                continue
            conteudo[rota] = {"linhas": len(linhas), "versao": tentativa, "dados": linhas}
            break
        else:
            conteudo[rota] = {"linhas": 0, "versao": None,
                              "ausente_em": ausentes, "dados": []}
    return {
        "source": "ANBIMA Feed, fundos",
        "environment": ambiente,
        "origem": "AUTOMATICA_PUBLICA",
        "api_version_requested": versao,
        "aviso": ("Retorno de fundo é realizado, não taxa contratada, e carrega "
                  "taxa de administração e come-cotas. Não entra na régua de "
                  "ofertas sem uma hipótese declarada de retorno futuro."),
        "rotas": conteudo,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--ambiente", choices=sorted(BASES),
                   default=os.environ.get("ANBIMA_AMBIENTE", "sandbox"))
    p.add_argument("--versao", choices=("auto", *VERSOES),
                   default=os.environ.get("ANBIMA_VERSAO", "auto"),
                   help="auto tenta a mais nova e cai para a anterior no 404")
    p.add_argument("--produto", choices=("precos", "fundos"), default="precos",
                   help="precos escreve a grade de papéis; fundos, o cadastro")
    args = p.parse_args()

    if args.produto == "fundos":
        documento = coletar_fundos(args.ambiente, args.versao)
        DESTINO_FUNDOS.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                                  encoding="utf-8")
        print(f"{DESTINO_FUNDOS.relative_to(ROOT)} · ambiente {args.ambiente}")
        for rota, corpo in documento["rotas"].items():
            onde = corpo["versao"] or f"ausente em {', '.join(corpo.get('ausente_em', []))}"
            print(f"  {rota}: {corpo['linhas']} linhas · {onde}")
        print("  não entra na régua de ofertas: retorno de fundo é realizado, "
              "não taxa contratada.")
        return

    documento = coletar(args.ambiente, args.versao)
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")

    itens = documento["products"]
    print(f"{DESTINO.relative_to(ROOT)}: {len(itens)} papéis · ambiente {args.ambiente}")
    for caminho, contagem in documento["por_fonte"].items():
        print(f"  {caminho}: {contagem['convertidas']} de {contagem['linhas']} linhas "
              f"· respondeu {contagem['versao']}")
    datas = sorted({x["maturity"] for x in itens})
    if datas:
        print(f"  vencimentos de {datas[0]} a {datas[-1]}")
    print("  regime: valor mobiliário, sem FGC. A alocação recusa sem risco declarado.")


if __name__ == "__main__":
    main()
