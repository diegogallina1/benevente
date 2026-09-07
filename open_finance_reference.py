# -*- coding: utf-8 -*-
"""A régua pública do Open Finance, do lado em que ela existe.

O catálogo de renda fixa deste projeto sempre foi do escritório: a grade chega
por arquivo, o motor ordena e aloca, e ninguém confere a taxa contra nada. A
razão registrada era que captação bancária não tem fonte pública. Isso deixou de
ser inteiro: a API de Dados Abertos de Investimentos do Open Finance publica, por
emissor, a distribuição da remuneração de emissão de CDB, RDB, LCI e LCA.

O que ela publica **não é oferta**. Para cada combinação de emissor, tipo,
indexador, aplicação mínima, prazo de resgate, faixa de vencimento, carência e
público, vêm quatro faixas de frequência: a mediana de cada uma, o percentual de
operações nela, e o mínimo e o máximo observados. Não há papel, não há
vencimento, não há como comprar. Há como responder a uma pergunta que o sistema
não sabia responder: **a taxa que o escritório mandou está onde, dentro do que
esse emissor de fato emitiu?**

O que este módulo recusa a fazer, e por quê:

* **Não interpola percentil.** Sabendo quatro medianas e os extremos, não se
  conhece a borda das faixas. Um percentil calculado com isso teria a mesma cara
  de um percentil medido e apareceria na mesma linha da tela — é a mesma recusa
  que rege o custo de aquisição em ``b3_connection``.
* **Não mistura emissores.** Taxa maior de emissor pior não é oferta melhor, é
  outro risco de crédito. Comparar uma oferta com a distribuição do mercado
  inteiro apagaria exatamente a informação que decide.
* **Não confere CDI+.** A própria especificação manda descartar operação com
  taxa mista em CDI, DI e SELIC, então a distribuição não cobre oferta cotada
  como CDI + spread. Recusar é a resposta certa; converter para percentual do
  CDI com o CDI de hoje produziria um número que muda de verdade amanhã.
* **Não confere papel de crédito nem Tesouro.** ``credit-fixed-incomes``,
  ``variable-incomes`` e ``treasure-titles`` trazem só ``custodyFee`` e
  ``loadingRate`` — o que a instituição cobra, nunca a taxa do papel. Isso
  também é útil, e está aqui como o que é: taxa de serviço.

A data é a da coleta. A API não devolve período de referência em campo nenhum, e
supor "mês corrente" seria inventar a metade mais importante de um dado datado.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import json
import re
import unicodedata

from fixed_income_catalog import Index, Product

ROOT = Path(__file__).resolve().parent
COLHEITA_PADRAO = ROOT / "data" / "dados_abertos_open_finance.json"

#: De um índice do catálogo para o indexador da API. O que não está aqui não tem
#: contraparte publicada, e a ausência é uma recusa declarada, não um esquecimento.
INDEXADOR = {
    Index.CDI: "CDI",
    Index.SELIC: "SELIC",
    Index.IPCA: "IPCA",
    Index.PREFIXADO: "PRE_FIXADO",
}
#: A API descarta taxa mista. Cotação em CDI + spread não tem onde ser conferida.
SEM_CONTRAPARTE = {
    Index.CDI_MAIS: "a especificação manda ignorar operação com taxa mista em "
                    "CDI, DI e SELIC: não existe distribuição para CDI + spread",
}
#: Só captação bancária tem distribuição de remuneração nos dados abertos.
TIPOS_COM_DISTRIBUICAO = ("CDB", "RDB", "LCI", "LCA")
#: As faixas de prazo da API, em dias corridos.
FAIXAS_DE_PRAZO = ((360, "1_360"), (1080, "361_1080"))
FAIXA_LONGA = "1081+"


def faixa_de_prazo(dias: int) -> str:
    for limite, nome in FAIXAS_DE_PRAZO:
        if dias <= limite:
            return nome
    return FAIXA_LONGA


def _fracao(valor) -> float | None:
    """Os números vêm como texto com seis casas. Vazio é ausência, não zero."""
    if valor is None or valor == "":
        return None
    try:
        return float(str(valor).strip())
    except ValueError:
        return None


#: Forma jurídica não é identidade: "Banco B S.A." e "Banco B SA" são o mesmo
#: emissor, e dois emissores diferentes nunca diferem só nisso. A lista é curta
#: de propósito — cada entrada a mais é uma chance de casar bancos distintos.
FORMAS_JURIDICAS = ("s a", "sa", "ltda", "eireli")


def _chave(nome: str) -> str:
    """Nome de emissor comparável: sem acento, sem pontuação, sem forma jurídica.

    Casar emissor por nome é o segundo melhor, e é frágil: nome de fantasia,
    conglomerado e razão social não coincidem, e o payload traz a razão social. O
    melhor é CNPJ, que a API publica em ``issuerInstitutionCnpjNumber`` e o
    catálogo do escritório não carrega. Quem tiver o número passa por parâmetro;
    quem não tiver casa por nome sabendo que casa por nome.
    """
    limpo = unicodedata.normalize("NFKD", str(nome or ""))
    limpo = "".join(c for c in limpo if not unicodedata.combining(c))
    limpo = re.sub(r"[^a-z0-9]+", " ", limpo.lower()).strip()
    mudou = True
    while mudou:
        mudou = False
        for forma in FORMAS_JURIDICAS:
            if limpo.endswith(f" {forma}"):
                limpo, mudou = limpo[: -len(forma) - 1].strip(), True
    return limpo


@dataclass(frozen=True)
class Faixa:
    """Uma das quatro faixas de frequência: a mediana e o peso dela."""
    intervalo: str
    mediana: float
    percentual_operacoes: float


@dataclass(frozen=True)
class Distribuicao:
    faixas: tuple[Faixa, ...]
    minimo: float
    maximo: float

    def medianas_abaixo(self, valor: float) -> tuple[int, float]:
        """Quantas faixas têm mediana abaixo do valor, e quanto pesam.

        É o que dá para afirmar sem inventar borda de faixa: não "esta oferta
        está no percentil 80", e sim "as faixas cuja mediana fica abaixo dela
        somam 80% das operações". A primeira frase é uma estimativa disfarçada;
        a segunda é leitura direta do que veio.
        """
        abaixo = [f for f in self.faixas if f.mediana < valor]
        return len(abaixo), round(sum(f.percentual_operacoes for f in abaixo), 6)


@dataclass(frozen=True)
class EmissaoBancaria:
    """Uma linha de ``bank-fixed-incomes``. A identidade inteira viaja com ela."""
    marca: str
    distribuidor_cnpj: str
    emissor_cnpj: str
    emissor_nome: str
    tipo: str
    indexador: str
    minimo_brl: float | None
    resgate: str
    faixa_vencimento: str
    faixa_carencia: str
    publico: str
    remuneracao: Distribuicao


@dataclass(frozen=True)
class TaxaDeServico:
    """Custódia e carregamento cobrados pela instituição, não taxa de papel."""
    marca: str
    distribuidor_cnpj: str
    familia: str
    tipo: str
    publico: str
    custodia: Distribuicao
    carregamento: Distribuicao


@dataclass(frozen=True)
class TermosDeFundo:
    """O que a ANBIMA não tem: os termos do fundo **naquele** distribuidor."""
    marca: str
    distribuidor_cnpj: str
    nome: str
    cnpj: str
    isin: str
    categoria_anbima: str
    tributacao: str
    taxa_administracao_maxima: float | None
    taxa_entrada: float | None
    taxa_saida: float | None
    taxa_performance: float | None
    performance_benchmark: str
    aplicacao_minima_brl: float | None
    resgate_cotizacao_dias: int | None
    resgate_liquidacao_dias: int | None
    carencia_dias: int | None


@dataclass(frozen=True)
class Colheita:
    colhido_em: str
    emissoes: tuple[EmissaoBancaria, ...]
    taxas: tuple[TaxaDeServico, ...]
    fundos: tuple[TermosDeFundo, ...]
    descartadas: tuple[str, ...]


def _distribuicao(bruto) -> Distribuicao | None:
    if not isinstance(bruto, dict):
        return None
    minimo, maximo = _fracao(bruto.get("minimum")), _fracao(bruto.get("maximum"))
    faixas = []
    for preco in bruto.get("prices") or []:
        if not isinstance(preco, dict) or not preco.get("interval"):
            continue
        mediana, peso = _fracao(preco.get("value")), _fracao(preco.get("operationRate"))
        if mediana is None or peso is None:
            continue
        faixas.append(Faixa(str(preco["interval"]), mediana, peso))
    if not faixas or minimo is None or maximo is None:
        return None
    return Distribuicao(tuple(faixas), minimo, maximo)


def _emissao(linha: dict, participante: dict) -> EmissaoBancaria | None:
    condicoes = linha.get("investmentConditions") or {}
    indice = linha.get("index") or {}
    remuneracao = _distribuicao(indice.get("issueRemunerationRate"))
    if remuneracao is None:
        return None
    return EmissaoBancaria(
        marca=participante.get("marca", ""),
        distribuidor_cnpj=participante.get("cnpj", ""),
        emissor_cnpj=re.sub(r"\D", "", str(linha.get("issuerInstitutionCnpjNumber") or "")),
        emissor_nome=str(linha.get("issuerInstitutionName") or ""),
        tipo=str(linha.get("investmentType") or ""),
        indexador=str(indice.get("indexer") or ""),
        minimo_brl=_fracao(condicoes.get("minimumAmount")),
        resgate=str(condicoes.get("redemptionTerm") or ""),
        faixa_vencimento=str(condicoes.get("expirationPeriod") or ""),
        faixa_carencia=str(condicoes.get("gracePeriod") or ""),
        publico=str(linha.get("targetAudience") or ""),
        remuneracao=remuneracao,
    )


def _taxa(linha: dict, participante: dict, familia: str) -> TaxaDeServico | None:
    custodia = _distribuicao(linha.get("custodyFee"))
    carregamento = _distribuicao(linha.get("loadingRate"))
    if custodia is None or carregamento is None:
        return None
    return TaxaDeServico(
        marca=participante.get("marca", ""),
        distribuidor_cnpj=participante.get("cnpj", ""),
        familia=familia,
        tipo=str(linha.get("investmentType") or ""),
        publico=str(linha.get("targetAudience") or ""),
        custodia=custodia,
        carregamento=carregamento,
    )


def _inteiro(valor) -> int | None:
    return int(valor) if isinstance(valor, int) else None


def _fundo(linha: dict, participante: dict) -> TermosDeFundo | None:
    cnpj = re.sub(r"\D", "", str(linha.get("cnpjNumber") or ""))
    if len(cnpj) != 14:
        return None
    condicoes = linha.get("generalConditions") or {}
    resgate = condicoes.get("redemption") or {}
    taxas = linha.get("fees") or {}
    performance = taxas.get("performanceFee") or {}
    minimo = (condicoes.get("minimumAmount") or {}).get("value")
    return TermosDeFundo(
        marca=participante.get("marca", ""),
        distribuidor_cnpj=participante.get("cnpj", ""),
        nome=str(linha.get("name") or ""),
        cnpj=cnpj,
        isin=str(linha.get("isinCode") or ""),
        categoria_anbima=str(linha.get("anbimaCategory") or ""),
        tributacao=str(linha.get("taxation") or ""),
        taxa_administracao_maxima=_fracao(taxas.get("maxAdminFee")),
        taxa_entrada=_fracao(taxas.get("entryFee")),
        taxa_saida=_fracao(taxas.get("exitFee")),
        taxa_performance=_fracao(performance.get("amount")),
        performance_benchmark=str(performance.get("benchmark") or ""),
        aplicacao_minima_brl=_fracao(minimo),
        resgate_cotizacao_dias=_inteiro(resgate.get("quotationDays")),
        resgate_liquidacao_dias=_inteiro(resgate.get("paymentDays")),
        carencia_dias=_inteiro(resgate.get("graceDays")),
    )


#: De que recurso sai que família de taxa de serviço.
FAMILIA_DE_TAXA = {"credit-fixed-incomes": "RENDA_FIXA_CREDITO",
                   "variable-incomes": "RENDA_VARIAVEL",
                   "treasure-titles": "TESOURO"}


def carregar(caminho: str | Path = COLHEITA_PADRAO) -> Colheita:
    """Lê o documento do coletor. Linha malformada é contada, não engolida."""
    documento = json.loads(Path(caminho).read_text(encoding="utf-8"))
    emissoes, taxas, fundos, descartadas = [], [], [], []
    for participante in documento.get("participantes") or []:
        recursos = participante.get("recursos") or {}
        for nome, corpo in recursos.items():
            for linha in (corpo or {}).get("dados") or []:
                if not isinstance(linha, dict):
                    descartadas.append(f"{participante.get('organizacao')}/{nome}: não é objeto")
                    continue
                if nome == "bank-fixed-incomes":
                    convertida = _emissao(linha, participante)
                    destino = emissoes
                elif nome == "funds":
                    convertida = _fundo(linha, participante)
                    destino = fundos
                elif nome in FAMILIA_DE_TAXA:
                    convertida = _taxa(linha, participante, FAMILIA_DE_TAXA[nome])
                    destino = taxas
                else:
                    continue
                if convertida is None:
                    descartadas.append(
                        f"{participante.get('organizacao')}/{nome}: linha sem os "
                        f"campos obrigatórios da especificação")
                    continue
                destino.append(convertida)
    return Colheita(colhido_em=str(documento.get("colhido_em") or ""),
                    emissoes=tuple(emissoes), taxas=tuple(taxas),
                    fundos=tuple(fundos), descartadas=tuple(descartadas))


@dataclass(frozen=True)
class Comparacao:
    """Uma oferta contra uma linha da distribuição. Nada é agregado entre linhas."""
    emissao: EmissaoBancaria
    taxa_da_oferta: float
    abaixo_do_minimo: bool
    acima_do_maximo: bool
    medianas_abaixo: int
    peso_das_medianas_abaixo: float

    @property
    def leitura(self) -> str:
        if self.abaixo_do_minimo:
            return (f"abaixo do mínimo que {self.emissao.emissor_nome} emitiu "
                    f"({self.emissao.remuneracao.minimo:.6f})")
        if self.acima_do_maximo:
            return (f"acima do máximo que {self.emissao.emissor_nome} emitiu "
                    f"({self.emissao.remuneracao.maximo:.6f})")
        return (f"{self.medianas_abaixo} de {len(self.emissao.remuneracao.faixas)} "
                f"faixas têm mediana abaixo desta oferta, somando "
                f"{self.peso_das_medianas_abaixo:.1%} das operações")


@dataclass(frozen=True)
class Conferencia:
    """O resultado. Ou tem linhas comparáveis, ou tem o motivo de não ter."""
    produto: str
    recusa: str | None
    comparacoes: tuple[Comparacao, ...]

    @property
    def conferivel(self) -> bool:
        return self.recusa is None and bool(self.comparacoes)


def _resgates_aceitos(produto: Product) -> tuple[str, ...]:
    """Liquidez diária do catálogo cobre dois termos da API, e só esses.

    ``DIARIA_PRAZO_CARENCIA`` é diária depois da carência, que o catálogo não
    sabe expressar. Aceitá-lo junto com ``DIARIA`` é mais honesto que escolher
    um dos dois: a linha comparada vai nomeada no resultado.
    """
    if produto.daily_liquidity:
        return ("DIARIA", "DIARIA_PRAZO_CARENCIA")
    return ("DATA_VENCIMENTO",)


def conferir(produto: Product, referencia: date, emissoes,
             *, publico: str = "PESSOA_NATURAL",
             emissor_cnpj: str | None = None) -> Conferencia:
    """Onde a taxa desta oferta cai, dentro do que o emissor dela emitiu.

    O casamento é por emissor, tipo, indexador, faixa de vencimento, termo de
    resgate e público. A aplicação mínima da linha **não** filtra: ela é parte
    da identidade da linha e vai no resultado, mas descartar por desigualdade
    jogaria fora justamente a linha mais parecida com a oferta.
    """
    # A ordem das recusas importa: para uma debênture cotada em CDI+ as duas
    # valem, e a que ajuda quem lê é a do tipo — ela diz que não existe fonte,
    # e não que faltou uma conversão de indexador.
    if produto.kind not in TIPOS_COM_DISTRIBUICAO:
        return Conferencia(
            produto.name,
            f"os dados abertos só publicam distribuição de remuneração para "
            f"{', '.join(TIPOS_COM_DISTRIBUICAO)}; {produto.kind} não tem "
            f"contraparte pública de taxa", ())
    if produto.index in SEM_CONTRAPARTE:
        return Conferencia(produto.name, SEM_CONTRAPARTE[produto.index], ())
    indexador = INDEXADOR.get(produto.index)
    if indexador is None:
        return Conferencia(produto.name,
                           f"índice {produto.index.value} sem indexador equivalente "
                           f"na especificação", ())

    dias = (produto.maturity - referencia).days
    if dias <= 0:
        raise ValueError(f"{produto.name} venceu em {produto.maturity}.")
    faixa = faixa_de_prazo(dias)
    aceitos = _resgates_aceitos(produto)
    alvo_cnpj = re.sub(r"\D", "", emissor_cnpj or "")
    alvo_nome = _chave(produto.issuer)

    escolhidas = []
    for emissao in emissoes:
        if emissao.tipo != produto.kind or emissao.indexador != indexador:
            continue
        if emissao.faixa_vencimento != faixa or emissao.publico != publico:
            continue
        if emissao.resgate not in aceitos:
            continue
        casa = (emissao.emissor_cnpj == alvo_cnpj if alvo_cnpj
                else _chave(emissao.emissor_nome) == alvo_nome)
        if not casa:
            continue
        quantas, peso = emissao.remuneracao.medianas_abaixo(produto.rate)
        escolhidas.append(Comparacao(
            emissao=emissao,
            taxa_da_oferta=produto.rate,
            abaixo_do_minimo=produto.rate < emissao.remuneracao.minimo,
            acima_do_maximo=produto.rate > emissao.remuneracao.maximo,
            medianas_abaixo=quantas,
            peso_das_medianas_abaixo=peso,
        ))

    if not escolhidas:
        por = f"CNPJ {alvo_cnpj}" if alvo_cnpj else f"nome “{produto.issuer}”"
        return Conferencia(
            produto.name,
            f"nenhuma linha publicada para {por} em {produto.kind}/{indexador}, "
            f"vencimento na faixa {faixa}, resgate {'/'.join(aceitos)}, "
            f"público {publico}", ())
    return Conferencia(produto.name, None, tuple(escolhidas))


def termos_de_distribuicao(cnpj: str, fundos) -> tuple[TermosDeFundo, ...]:
    """Os termos de um fundo em cada distribuidor que o publica.

    ``fund_comparator`` compara cota realizada e avisa, no próprio docstring, que
    cada fundo tem taxa, tributação, elegibilidade e liquidez próprias. Estes são
    esses termos, com fonte pública e datada — e por distribuidor, porque o mesmo
    fundo tem mínimo e taxa de entrada diferentes em cada um.
    """
    alvo = re.sub(r"\D", "", str(cnpj))
    return tuple(f for f in fundos if f.cnpj == alvo)


def taxas_de_servico(colheita: Colheita, familia: str) -> tuple[TaxaDeServico, ...]:
    """Custódia e carregamento por família. Não é taxa de papel, e não vira uma."""
    return tuple(t for t in colheita.taxas if t.familia == familia)
