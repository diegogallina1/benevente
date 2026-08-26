"""Mapeia a carteira que o cliente já tem contra o perfil declarado.

A primeira pergunta de qualquer conversa com um cliente novo não é "o que
comprar", é "o que você já tem, e o quanto disso já serve". Ninguém responde
bem essa pergunta hoje: as ferramentas mostram a carteira alvo e deixam a
travessia como exercício de quem assina.

Este módulo faz a travessia explícita. Recebe a posição atual — de onde quer que
ela venha — e o perfil declarado, e devolve o que já está aderente, o que sai, o
que entra e **quanto custa mover**, incluindo o imposto que a venda realiza.

Esse último número é o que muda decisões e é o que ninguém mostra. Uma posição
com ganho grande carrega imposto latente: vendê-la para comprar a cesta do
perfil não é uma troca neutra, é uma troca que começa com quinze por cento do
ganho indo embora. O mapa mostra isso e para por aí — quanto tempo levaria para
"compensar" exigiria projetar retorno futuro, e este projeto mede projeções em
vez de fazê-las.

Origem da posição: o mapa não sabe e não precisa saber de onde ela veio. Aceita
lançamento manual, arquivo, a API da Área do Investidor da B3 (ativos
depositados e registrados na B3, com consentimento do investidor) ou o Open
Finance, quando houver enquadramento para consumi-lo. O que ele exige é que a
origem viaje junto de cada posição, porque um mapa que não sabe se o dado veio
de extrato ou de digitação não é auditável.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json

from fixed_income_catalog import FGC_PER_CONGLOMERATE_BRL, income_tax_rate

EQUITY_TAX_RATE = 0.15
TRADE_COST = 10.0 / 10_000
GLOBAL_TICKER = "IVVB11"


class Source(str, Enum):
    """De onde veio a posição. Viaja com ela até o fim do mapa."""
    B3_INVESTIDOR = "extrato da Área do Investidor da B3"
    OPEN_FINANCE = "Open Finance (compartilhamento de investimentos)"
    ARQUIVO = "arquivo enviado pelo escritório"
    MANUAL = "lançamento manual"


class Bucket(str, Enum):
    ACAO = "ação"
    FUNDO_GLOBAL = "fundo global"
    RENDA_FIXA = "renda fixa"
    CAIXA = "caixa"
    FORA_DO_ESCOPO = "fora do escopo da política"


@dataclass(frozen=True)
class Position:
    ticker: str
    bucket: Bucket
    market_value_brl: float
    cost_basis_brl: float
    source: Source
    conglomerate: str | None = None
    days_held: int = 400
    liquid: bool = True

    @property
    def unrealised_gain_brl(self) -> float:
        return self.market_value_brl - self.cost_basis_brl


@dataclass
class Move:
    ticker: str
    action: str                 # "manter", "reduzir", "vender", "comprar"
    from_brl: float
    to_brl: float
    reason: str
    trade_cost_brl: float = 0.0
    realised_gain_brl: float = 0.0
    tax_brl: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def delta_brl(self) -> float:
        return self.to_brl - self.from_brl


#: Cestas de compensação. Ganhos e prejuízos se encontram dentro de uma cesta e
#: nunca entre cestas: prejuízo em ação não abate imposto de renda fixa, e
#: cripto tem regime próprio. Tratar cada venda isoladamente superestima o
#: imposto — foi o erro da primeira versão, que cobrava alíquota cheia de um
#: ganho enquanto um prejuízo maior era realizado na mesma apuração.
TAX_BUCKETS = {
    Bucket.ACAO: "renda_variavel",
    Bucket.FUNDO_GLOBAL: "renda_variavel",
    Bucket.RENDA_FIXA: "renda_fixa",
    Bucket.CAIXA: "renda_fixa",
    Bucket.FORA_DO_ESCOPO: "fora_do_escopo",
}


def _realised_gain(position: Position, sold_brl: float) -> float:
    """Ganho ou prejuízo de uma venda parcial, ao custo médio."""
    if sold_brl <= 0 or position.market_value_brl <= 0:
        return 0.0
    return position.unrealised_gain_brl * min(1.0, sold_brl / position.market_value_brl)


def _settle(gains: dict, exempt_month: bool, days_held: int) -> dict:
    """Imposto por cesta, depois de compensar ganhos e prejuízos dentro dela."""
    imposto = {}
    for bucket, gain in gains.items():
        if gain <= 0 or bucket == "fora_do_escopo":
            imposto[bucket] = 0.0
        elif bucket == "renda_variavel" and exempt_month:
            imposto[bucket] = 0.0
        else:
            rate = EQUITY_TAX_RATE if bucket == "renda_variavel" else income_tax_rate(days_held)
            imposto[bucket] = gain * rate
    return imposto


def map_portfolio(positions: list[Position], target: dict, *,
                  monthly_stock_sales_brl: float = 0.0) -> dict:
    """Compara a carteira atual com o alvo do perfil e precifica a travessia.

    ``target`` é o livro declarado do perfil: pesos por emissor, fração global e
    caixa. O mapa nunca inventa peso — ele lê o que a política já declarou.
    """
    total = sum(p.market_value_brl for p in positions)
    if total <= 0:
        raise ValueError("Carteira sem valor de mercado.")

    alvo_acoes = {t.removesuffix(".SA"): w for t, w in target["positions"].items()}
    alvo_global = float(target.get("global_sleeve", 0.0))
    alvo_caixa = float(target.get("cash", 0.0))

    atual = {p.ticker.removesuffix(".SA"): p for p in positions}
    # A isenção mensal de vinte mil só existe para ações à vista e é do mês
    # inteiro: se o escritório já vendeu no mês, ela pode não estar disponível.
    vendas_acoes = monthly_stock_sales_brl
    for ticker, alvo in alvo_acoes.items():
        pos = atual.get(ticker)
        if pos and pos.market_value_brl > alvo * total:
            vendas_acoes += pos.market_value_brl - alvo * total
    for ticker, pos in atual.items():
        if pos.bucket is Bucket.ACAO and ticker not in alvo_acoes:
            vendas_acoes += pos.market_value_brl
    mes_isento = vendas_acoes <= 20_000.0

    moves: list[Move] = []
    vendas: list[tuple[Position, float]] = []
    aderente = 0.0

    for ticker, pos in sorted(atual.items()):
        alvo_brl = alvo_acoes.get(ticker, 0.0) * total
        if pos.bucket is Bucket.FUNDO_GLOBAL:
            alvo_brl = alvo_global * total
        elif pos.bucket in (Bucket.CAIXA, Bucket.RENDA_FIXA):
            alvo_brl = pos.market_value_brl  # o caixa é resolvido no fim
        elif pos.bucket is Bucket.FORA_DO_ESCOPO:
            alvo_brl = 0.0

        if pos.bucket in (Bucket.CAIXA, Bucket.RENDA_FIXA):
            aderente += pos.market_value_brl
            continue

        excesso = pos.market_value_brl - alvo_brl
        aderente += min(pos.market_value_brl, alvo_brl)
        tolerancia = max(1.0, total * 1e-4)

        # Uma posição abaixo do alvo precisa ser completada. A primeira versão
        # tratava qualquer não-excesso como "manter" e entregava uma carteira
        # sistematicamente abaixo do peso declarado — o oposto do que um mapa
        # que existe para chegar ao alvo deve fazer.
        if excesso < -tolerancia:
            moves.append(Move(ticker, "comprar", pos.market_value_brl, alvo_brl,
                              "abaixo do peso declarado",
                              round(abs(excesso) * TRADE_COST, 2)))
            continue
        if excesso <= tolerancia:
            moves.append(Move(ticker, "manter", pos.market_value_brl, pos.market_value_brl,
                              "já está no peso do perfil" if alvo_brl > 0 else "posição nula"))
            continue

        vender_tudo = alvo_brl <= 0
        ganho = _realised_gain(pos, excesso)
        custo = excesso * TRADE_COST
        notas = []
        if ganho > 0 and mes_isento and pos.bucket is Bucket.ACAO:
            notas.append("isento pela regra dos vinte mil no mês, se nada mais for vendido")
        if ganho < 0:
            notas.append("prejuízo realizado: abate o ganho das outras vendas da mesma cesta")
        vendas.append((pos, ganho))
        if not pos.liquid:
            notas.append("posição sem liquidez diária: a saída depende do vencimento ou do secundário")
        moves.append(Move(
            ticker, "vender" if vender_tudo else "reduzir",
            pos.market_value_brl, alvo_brl,
            "não está na cesta do perfil" if vender_tudo else "acima do peso declarado",
            round(custo, 2), round(ganho, 2), 0.0, notas))

    for ticker, peso in sorted(alvo_acoes.items()):
        if ticker in atual:
            continue
        alvo_brl = peso * total
        moves.append(Move(ticker, "comprar", 0.0, alvo_brl, "entra pela seleção do perfil",
                          round(alvo_brl * TRADE_COST, 2)))
    if alvo_global > 0 and not any(p.bucket is Bucket.FUNDO_GLOBAL for p in positions):
        moves.append(Move(GLOBAL_TICKER, "comprar", 0.0, alvo_global * total,
                          "perna global declarada pela política",
                          round(alvo_global * total * TRADE_COST, 2)))

    # A apuração é por cesta, não por venda: só depois de somar ganhos e
    # prejuízos é que a alíquota tem sobre o que incidir. O imposto é do
    # conjunto, e rateá-lo por movimento inventaria uma precisão que a lei não
    # tem — cada linha mostra o ganho que realizou, o total aparece na travessia.
    por_cesta: dict[str, float] = {}
    for pos, ganho in vendas:
        cesta = TAX_BUCKETS[pos.bucket]
        por_cesta[cesta] = por_cesta.get(cesta, 0.0) + ganho
    prazo = min((p.days_held for p, _ in vendas if TAX_BUCKETS[p.bucket] == "renda_fixa"), default=400)
    imposto_por_cesta = _settle(por_cesta, mes_isento, prazo)

    custo_total = sum(m.trade_cost_brl for m in moves)
    imposto_total = sum(imposto_por_cesta.values())
    girado = sum(abs(m.delta_brl) for m in moves) / 2

    fgc = {}
    for p in positions:
        if p.bucket is Bucket.RENDA_FIXA and p.conglomerate:
            fgc[p.conglomerate] = fgc.get(p.conglomerate, 0.0) + p.market_value_brl
    estouros = {k: round(v, 2) for k, v in fgc.items() if v > FGC_PER_CONGLOMERATE_BRL}

    return {
        "total_brl": round(total, 2),
        "alignment": round(aderente / total, 4),
        "turnover_brl": round(girado, 2),
        "transition_cost_brl": round(custo_total, 2),
        "transition_tax_brl": round(imposto_total, 2),
        "transition_total_brl": round(custo_total + imposto_total, 2),
        "transition_cost_pct": round((custo_total + imposto_total) / total, 5),
        "exempt_month_assumed": mes_isento,
        "tax_by_bucket": {k: {"realised_gain_brl": round(v, 2),
                              "tax_brl": round(imposto_por_cesta.get(k, 0.0), 2)}
                          for k, v in sorted(por_cesta.items())},
        "fgc_breaches": estouros,
        "sources": sorted({p.source.value for p in positions}),
        "moves": [
            {"ticker": m.ticker, "action": m.action,
             "from_brl": round(m.from_brl, 2), "to_brl": round(m.to_brl, 2),
             "delta_brl": round(m.delta_brl, 2), "reason": m.reason,
             "trade_cost_brl": m.trade_cost_brl, "realised_gain_brl": m.realised_gain_brl,
             "tax_brl": m.tax_brl, "notes": m.notes}
            for m in sorted(moves, key=lambda x: (x.action != "vender", -abs(x.delta_brl)))
        ],
        "honesty": (
            "O custo da travessia inclui o imposto que a venda realiza, que é o número que "
            "costuma faltar. O mapa não estima em quanto tempo a mudança 'se paga': isso exigiria "
            "projetar retorno futuro, e a calibração publicada mostra que projeções desse tipo "
            "erram na direção de quem as faz."),
    }


def load_positions(payload: dict) -> list[Position]:
    """Lê posições de um documento com origem declarada por item."""
    return [Position(
        ticker=item["ticker"], bucket=Bucket(item["bucket"]),
        market_value_brl=float(item["market_value_brl"]),
        cost_basis_brl=float(item.get("cost_basis_brl", item["market_value_brl"])),
        source=Source(item["source"]), conglomerate=item.get("conglomerate"),
        days_held=int(item.get("days_held", 400)), liquid=bool(item.get("liquid", True)),
    ) for item in payload["positions"]]
