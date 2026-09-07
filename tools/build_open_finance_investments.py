# -*- coding: utf-8 -*-
"""Os dados abertos de investimentos do Open Finance, colhidos sem credencial.

O Open Finance brasileiro tem duas famílias de API, e confundi-las é o erro que
este arquivo existe para não cometer.

A família de **dados de clientes** devolve posição, saldo e movimentação. Na
especificação ela pede ``OAuth2AuthorizationCode`` com os escopos ``openid``,
``consent:consentId`` e o da própria API, o que exige ser instituição autorizada
pelo Banco Central, registrada no diretório, com certificado e consentimento do
titular. Não é o que este coletor faz, e nada aqui aproxima disso.

A família de **dados abertos** — ``/open-banking/opendata-investments/v1`` — não
tem esquema de segurança nenhum na especificação: os únicos parâmetros são
``page`` e ``pageSize``. É GET público. São cinco recursos: ``funds``,
``bank-fixed-incomes`` (CDB, RDB, LCI, LCA), ``credit-fixed-incomes``
(debênture, CRI, CRA), ``variable-incomes`` (ações e fundos de índice) e
``treasure-titles``.

**O que isto não é.** Não é livro de ofertas. ``bank-fixed-incomes`` não devolve
"CDB do Banco X a 110% do CDI vencendo em 2028". Devolve, por emissor, tipo,
indexador, aplicação mínima, prazo de resgate, faixa de vencimento, carência e
público, uma *distribuição de frequência em quatro faixas* da remuneração de
emissão: a mediana de cada faixa e o percentual de operações nela, mais o mínimo
e o máximo observados. Não dá para comprar a partir disso, e não dá para montar
catálogo com isso. Dá para conferir a grade que o escritório mandou contra o que
o próprio emissor de fato emitiu — que é o uso, e está em
``open_finance_reference.py``.

Os três recursos restantes de renda fixa e variável trazem só ``custodyFee`` e
``loadingRate``: o que a instituição cobra, nunca a taxa do papel. A taxa de
debênture, CRI e CRA continua vindo da ANBIMA e o Tesouro do Tesouro
Transparente. ``funds`` é o único que é cadastro de verdade, e traz o que a
ANBIMA não tem: os termos **por distribuidor**.

**Sobre a data.** Nenhum payload tem campo de período de referência. A
especificação não devolve data nenhuma, então a datação é a da coleta, e é isso
que vai gravado — com o hash do conteúdo, para uma coleta seguinte provar que
mudou em vez de alegar.

**Sobre credencial.** Não há. Este programa não lê variável de ambiente de
segredo, não monta cabeçalho de autorização e não tem para onde vazar chave. Se
algum dia precisar de uma, é porque passou a chamar a outra família de API, e aí
o problema não é de código.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit
import argparse
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "data" / "dados_abertos_open_finance.json"

#: O diretório de participantes é público e é o único lugar onde os endereços de
#: cada instituição estão declarados. Não existe endpoint central: cada
#: participante serve os dados abertos no host dele.
DIRETORIO = "https://data.directory.openbankingbrasil.org.br/participants"

#: O que identifica um endereço de dados abertos de investimentos. A busca é
#: pelo **caminho**, não pelo nome da família: o campo ``ApiFamilyType`` do
#: diretório não pôde ser conferido de onde este coletor foi escrito, e casar
#: por um nome suposto devolveria zero participante sem dizer por quê. O caminho
#: está na especificação e é estável.
MARCA = "/opendata-investments/"
#: Os cinco recursos, com o nome que cada um tem na especificação.
RECURSOS = ("funds", "bank-fixed-incomes", "credit-fixed-incomes",
            "variable-incomes", "treasure-titles")

#: O teto documentado de ``page-size`` é mil, e é o que se pede. O que vier
#: menor que isso encerra a paginação, como no coletor da ANBIMA.
POR_PAGINA = 1000
#: Trava contra paginação que não converge. Uma instituição não tem vinte mil
#: linhas de dados abertos de investimento; se tiver, é melhor falhar alto.
PAGINAS_MAXIMAS = 20
TEMPO_LIMITE = 30
#: Pausa entre chamadas. O 429 e o 529 estão na especificação, e o coletor
#: percorre centenas de hosts de terceiros: ir devagar é a diferença entre um
#: leitor e um incômodo.
PAUSA_PADRAO = 0.2


class RecursoIndisponivel(RuntimeError):
    """O host respondeu, mas não com dado: 404, 429, 5xx.

    Não derruba a coleta. Cada instituição serve o próprio host, e um host fora
    do ar não pode transformar o resultado dos outros trezentos em nada.
    """


def _abrir_json(url: str, *, abrir=urllib.request.urlopen):
    pedido = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with abrir(pedido, timeout=TEMPO_LIMITE) as resposta:
            return json.loads(resposta.read().decode("utf-8"))
    except urllib.error.HTTPError as erro:
        raise RecursoIndisponivel(f"HTTP {erro.code}") from None
    except urllib.error.URLError as erro:
        raise RecursoIndisponivel(f"rede: {erro.reason}") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Um host que devolve HTML de portal em vez de JSON não está servindo a
        # API. Dizer "resposta não é JSON" é mais útil que estourar um traceback
        # de decodificação no meio de trezentas instituições.
        raise RecursoIndisponivel("resposta não é JSON") from None


def _versao_do_caminho(url: str) -> str:
    """A versão que o próprio endereço declara depois da marca, ou ``v1``."""
    depois = url.split(MARCA, 1)[1] if MARCA in url else ""
    primeiro = depois.split("/", 1)[0]
    return primeiro if re.fullmatch(r"v\d+", primeiro) else "v1"


def base_do_endpoint(url: str) -> str | None:
    """Reduz um endereço do diretório à base dos cinco recursos.

    O diretório publica ora a base, ora o endereço completo de um recurso. As
    duas formas viram a mesma base, senão o mesmo participante entraria uma vez
    por recurso publicado.
    """
    if not isinstance(url, str) or MARCA not in url:
        return None
    prefixo = url.split(MARCA, 1)[0]
    if not urlsplit(prefixo).scheme:
        return None
    return f"{prefixo}{MARCA}{_versao_do_caminho(url)}"


def _servidores(organizacao: dict) -> list:
    """Os servidores de autorização, aceitando as duas formas do diretório."""
    dos_servidores = organizacao.get("AuthorisationServers")
    if isinstance(dos_servidores, list):
        return dos_servidores
    # Algumas cópias do diretório trazem os recursos direto na organização.
    return [organizacao] if organizacao.get("ApiResources") else []


def _ativo(registro: dict) -> bool:
    """Só o que o diretório marca como ativo. Ausência do campo não reprova.

    Reprovar por campo ausente descartaria participante bom por causa de uma
    variação de dump; reprovar por ``Inactive`` descarta o que o próprio
    diretório já disse que não vale.
    """
    estado = str(registro.get("Status") or "").strip().lower()
    return estado in ("", "active")


def bases_publicadas(diretorio) -> list[dict]:
    """As bases de dados abertos de investimento, uma por participante.

    Devolve marca, CNPJ e base. O CNPJ vem do diretório porque é ele que liga o
    participante ao emissor citado dentro do payload, e sem essa ligação a
    conferência de uma oferta vira comparação por nome de fantasia.
    """
    organizacoes = diretorio
    if isinstance(diretorio, dict):
        for campo in ("data", "content", "participants"):
            if isinstance(diretorio.get(campo), list):
                organizacoes = diretorio[campo]
                break
    if not isinstance(organizacoes, list):
        return []

    achados: dict[str, dict] = {}
    for organizacao in organizacoes:
        if not isinstance(organizacao, dict) or not _ativo(organizacao):
            continue
        nome = str(organizacao.get("OrganisationName")
                   or organizacao.get("LegalEntityName") or "").strip()
        cnpj = re.sub(r"\D", "", str(organizacao.get("RegistrationNumber") or ""))
        for servidor in _servidores(organizacao):
            if not isinstance(servidor, dict) or not _ativo(servidor):
                continue
            for recurso in servidor.get("ApiResources") or []:
                if not isinstance(recurso, dict) or not _ativo(recurso):
                    continue
                for endereco in recurso.get("ApiDiscoveryEndpoints") or []:
                    url = endereco.get("ApiEndpoint") if isinstance(endereco, dict) else endereco
                    base = base_do_endpoint(url)
                    if base and base not in achados:
                        achados[base] = {
                            "marca": str(servidor.get("CustomerFriendlyName") or nome),
                            "organizacao": nome,
                            "cnpj": cnpj,
                            "base": base,
                            "familia": str(recurso.get("ApiFamilyType") or ""),
                            "versao_declarada": str(recurso.get("ApiVersion") or ""),
                        }
    return sorted(achados.values(), key=lambda x: (x["organizacao"], x["base"]))


def _itens(corpo) -> tuple[list, dict]:
    """Separa ``data`` do envelope. O envelope é quem sabe se acabou."""
    if isinstance(corpo, list):
        return corpo, {}
    if not isinstance(corpo, dict):
        return [], {}
    dados = corpo.get("data")
    if isinstance(dados, list):
        return dados, {k: v for k, v in corpo.items() if k != "data"}
    return [], corpo


def buscar_recurso(base: str, recurso: str, *, abrir=urllib.request.urlopen,
                   pausa: float = 0.0) -> list[dict]:
    """Todas as páginas de um recurso.

    A defesa contra host que ignora ``page`` é a mesma do coletor da ANBIMA, e
    pela mesma razão: repetir a primeira página vinte vezes produz um resultado
    grande e errado, que é pior que um erro.
    """
    tudo: list = []
    anterior = None
    for pagina in range(1, PAGINAS_MAXIMAS + 1):
        corpo = _abrir_json(f"{base}/{recurso}?page={pagina}&page-size={POR_PAGINA}",
                            abrir=abrir)
        itens, envelope = _itens(corpo)
        assinatura = json.dumps(itens, ensure_ascii=False, sort_keys=True)[:4000]
        if anterior is not None and assinatura == anterior:
            break
        anterior = assinatura
        tudo.extend(itens)
        total = (envelope.get("meta") or {}).get("totalPages")
        if isinstance(total, int) and pagina >= total:
            break
        if len(itens) < POR_PAGINA:
            break
        if pausa:
            time.sleep(pausa)
    else:
        raise RecursoIndisponivel(
            f"paginação passou de {PAGINAS_MAXIMAS} páginas sem terminar")
    return tudo


def _impressao(itens: list) -> str:
    """Hash do conteúdo, para uma coleta seguinte provar que mudou."""
    bruto = json.dumps(itens, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(bruto).hexdigest()


def coletar(*, abrir=urllib.request.urlopen, diretorio=None, limite: int | None = None,
            recursos=RECURSOS, filtro: str = "", pausa: float = PAUSA_PADRAO) -> dict:
    """Percorre os participantes e devolve o documento datado.

    O que falhou fica nomeado no arquivo com o motivo. Coleta parcial silenciosa
    é o modo mais fácil de publicar uma régua torta: quem lê vê trezentos
    participantes e não sabe que quarenta não responderam.
    """
    if diretorio is None:
        diretorio = _abrir_json(DIRETORIO, abrir=abrir)
    publicadas = bases_publicadas(diretorio)
    participantes = publicadas
    if filtro:
        alvo = filtro.lower()
        participantes = [p for p in participantes
                         if alvo in p["organizacao"].lower() or alvo in p["marca"].lower()]
    if limite is not None:
        participantes = participantes[:limite]

    colhidos, falhas = [], []
    for participante in participantes:
        registro = {**participante, "recursos": {}}
        for recurso in recursos:
            try:
                itens = buscar_recurso(participante["base"], recurso, abrir=abrir,
                                       pausa=pausa)
            except RecursoIndisponivel as parou:
                registro["recursos"][recurso] = {"linhas": 0, "falhou": str(parou)}
                falhas.append(f"{participante['organizacao']}/{recurso}: {parou}")
                continue
            registro["recursos"][recurso] = {"linhas": len(itens),
                                             "sha256": _impressao(itens),
                                             "dados": itens}
            if pausa:
                time.sleep(pausa)
        colhidos.append(registro)

    return {
        "fonte": "Open Finance Brasil, API de Dados Abertos de Investimentos "
                 "(/open-banking/opendata-investments/v1)",
        "origem": "AUTOMATICA_PUBLICA",
        "credencial": "nenhuma: a especificação de dados abertos não tem esquema "
                      "de segurança, e este coletor não envia cabeçalho de autorização",
        "colhido_em": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "aviso_de_data": "O payload da API não tem campo de período de referência. "
                         "A data acima é a da coleta, não a da apuração declarada "
                         "pela instituição.",
        "aviso_de_uso": "bank-fixed-incomes traz distribuição de frequência da "
                        "remuneração de emissão, não oferta comprável. Serve para "
                        "conferir uma grade recebida, nunca para montar catálogo. "
                        "credit-fixed-incomes, variable-incomes e treasure-titles "
                        "trazem apenas taxa de custódia e de carregamento cobradas "
                        "pela instituição, nunca a taxa do papel.",
        "diretorio": DIRETORIO,
        "participantes_no_diretorio": len(publicadas),
        "participantes_colhidos": len(colhidos),
        "falhas": falhas,
        "participantes": colhidos,
    }


def _quantos(documento) -> int:
    if not isinstance(documento, dict):
        return 0
    total = 0
    for participante in documento.get("participantes") or []:
        for corpo in (participante.get("recursos") or {}).values():
            total += int(corpo.get("linhas") or 0)
    return total


def gravar(destino: Path, documento: dict) -> None:
    """Escreve, menos quando isso apagaria uma coleta boa com uma vazia.

    A regra é a mesma do coletor da ANBIMA, e nasceu do mesmo acidente: uma
    rodada com a paginação quebrada gravou zero por cima de mil linhas e o
    arquivo ficou com cara de resultado.
    """
    anterior = {}
    if destino.exists():
        try:
            anterior = json.loads(destino.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            anterior = {}
    if _quantos(anterior) and not _quantos(documento):
        raise SystemExit(
            f"{destino.name} tem {_quantos(anterior)} registros e esta coleta não "
            f"trouxe nenhum. O arquivo fica como está. Resolva a causa, ou apague "
            f"o arquivo se quiser mesmo gravar o vazio.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--diretorio-local", type=Path,
                   help="cópia salva do diretório de participantes, para rodar "
                        "sem alcançar data.directory.openbankingbrasil.org.br")
    p.add_argument("--limite", type=int,
                   help="quantos participantes percorrer. Sem isto, todos")
    p.add_argument("--participante", default="",
                   help="filtra por trecho do nome da organização ou da marca")
    p.add_argument("--recurso", choices=RECURSOS, action="append",
                   help="pode repetir. Sem isto, os cinco")
    p.add_argument("--pausa", type=float, default=PAUSA_PADRAO,
                   help="segundos entre chamadas, para não incomodar os hosts")
    p.add_argument("--saida", type=Path, default=DESTINO)
    p.add_argument("--listar", action="store_true",
                   help="só imprime quem publica dados abertos, sem colher nada")
    args = p.parse_args()

    diretorio = None
    if args.diretorio_local:
        diretorio = json.loads(args.diretorio_local.read_text(encoding="utf-8"))
    else:
        # O diretório é o único ponto sem o qual nada acontece, e ele cair é
        # coisa de rede, não de código. Traceback aqui só assusta quem roda.
        try:
            diretorio = _abrir_json(DIRETORIO)
        except RecursoIndisponivel as parou:
            raise SystemExit(
                f"o diretório de participantes não respondeu ({parou}). Ele é "
                f"público: {DIRETORIO}. Salve uma cópia e rode com "
                f"--diretorio-local se a rede daqui não o alcança.") from None

    if args.listar:
        publicadas = bases_publicadas(diretorio)
        plural = "participante publica" if len(publicadas) == 1 else "participantes publicam"
        print(f"{len(publicadas)} {plural} {MARCA}")
        for participante in publicadas[:args.limite or len(publicadas)]:
            print(f"  {participante['organizacao']} · {participante['base']}")
        return

    documento = coletar(diretorio=diretorio, limite=args.limite,
                        recursos=tuple(args.recurso) if args.recurso else RECURSOS,
                        filtro=args.participante, pausa=args.pausa)
    gravar(args.saida, documento)

    print(f"{args.saida} · colhido em {documento['colhido_em']}")
    print(f"  {documento['participantes_colhidos']} de "
          f"{documento['participantes_no_diretorio']} participantes")
    for recurso in RECURSOS:
        linhas = sum((p["recursos"].get(recurso) or {}).get("linhas", 0)
                     for p in documento["participantes"])
        print(f"  {recurso}: {linhas} linhas")
    if documento["falhas"]:
        print(f"  {len(documento['falhas'])} falhas, nomeadas no arquivo. "
              f"Primeira: {documento['falhas'][0]}")
    print("  bank-fixed-incomes é distribuição de taxa de emissão, não oferta "
          "comprável. Não vira catálogo.")


if __name__ == "__main__":
    main()
