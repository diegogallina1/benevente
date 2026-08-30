"""Mapeia a carteira que o cliente já tem contra o perfil declarado.

A primeira pergunta de qualquer conversa com um cliente novo não é "o que
comprar", é "o que você já tem, e o quanto disso já serve". Ninguém responde
bem essa pergunta hoje: as ferramentas mostram a carteira alvo e deixam a
mudança como exercício de quem assina.

Este módulo torna a mudança explícita. Recebe a posição atual — de onde quer que
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

from b3_connection import Qualidade
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
    FORA_DO_ESCOPO = "fora do que a política escolhe"


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
    #: De onde veio o custo. A conexão com a B3 não entrega preço médio — ele é
    #: reconstruído das negociações, e a base dela começa em 01/11/2019. Uma
    #: posição mais antiga chega sem custo defensável, e o imposto dela não pode
    #: ser somado como se fosse medido.
    cost_quality: Qualidade = Qualidade.DECLARADO

    @property
    def unrealised_gain_brl(self) -> float:
        return self.market_value_brl - self.cost_basis_brl

    @property
    def tax_computable(self) -> bool:
        return self.cost_quality.apura_imposto


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


def _settle(gains: dict, exempt_month: bool, days_held: int,
            carried_loss_brl: float = 0.0) -> dict:
    """Imposto por cesta, depois de compensar ganhos e prejuízos dentro dela.

    ``carried_loss_brl`` é prejuízo de meses anteriores em renda variável, que a
    lei deixa carregar sem prazo. Ignorá-lo superestima o custo do plano
    justamente para quem já perdeu dinheiro — o cliente que menos pode pagar por
    uma conta inflada.
    """
    imposto = {}
    for bucket, gain in gains.items():
        if bucket == "renda_variavel":
            gain -= max(0.0, carried_loss_brl)
        if gain <= 0 or bucket == "fora_do_escopo":
            imposto[bucket] = 0.0
        elif bucket == "renda_variavel" and exempt_month:
            imposto[bucket] = 0.0
        else:
            rate = EQUITY_TAX_RATE if bucket == "renda_variavel" else income_tax_rate(days_held)
            imposto[bucket] = gain * rate
    return imposto


def _apura(vendas: list[tuple[Position, float, float]], exempt_month: bool,
           carried_loss_brl: float) -> tuple[dict, dict, list]:
    """Separa o que dá para apurar do que não dá, e só então calcula.

    Uma posição sem custo defensável não entra na soma. A tentação é estimar o
    custo para fechar a conta, mas o imposto estimado se parece com o medido,
    aparece na mesma linha e leva à mesma decisão de vender. Fica de fora e
    aparece nomeado.

    ``vendas`` traz ``(posição, ganho, valor vendido)``. O valor vendido importa
    porque a lacuna tem o tamanho do que está saindo, não o da posição inteira:
    um plano que reduz catorze mil reais de uma posição de cento e oitenta mil
    não tem cento e oitenta mil de imposto pendente.
    """
    apuraveis = [(p, g) for p, g, _ in vendas if p.tax_computable]
    pendentes = [{"ticker": p.ticker.removesuffix(".SA"),
                  "sale_brl": round(v, 2),
                  # Fração da posição que está saindo: o cliente informa quanto
                  # pagou pela posição inteira, e o ganho é ao custo médio.
                  "sale_fraction": round(v / p.market_value_brl, 6)
                  if p.market_value_brl > 0 else 0.0,
                  "bucket": TAX_BUCKETS[p.bucket],
                  "cost_quality": p.cost_quality.value}
                 for p, _, v in vendas if not p.tax_computable]

    por_cesta: dict[str, float] = {}
    for pos, ganho in apuraveis:
        cesta = TAX_BUCKETS[pos.bucket]
        por_cesta[cesta] = por_cesta.get(cesta, 0.0) + ganho
    prazo = min((p.days_held for p, _ in apuraveis
                 if TAX_BUCKETS[p.bucket] == "renda_fixa"), default=400)
    return por_cesta, _settle(por_cesta, exempt_month, prazo, carried_loss_brl), pendentes


def _resolucao(pendentes: list, por_cesta: dict, imposto: dict, custo_execucao: float,
               exempt_month: bool, carried_loss_brl: float, prazo: int = 400) -> dict:
    """O que a tela precisa para fechar a conta quando o custo chegar.

    A tentação seria reescrever a apuração em JavaScript para o campo responder
    na hora. Duas implementações da mesma regra divergem — e divergem em
    silêncio, porque as duas continuam plausíveis. Então o módulo entrega os
    parâmetros e a tela faz só a aritmética final, com um teste comparando o
    resultado dela com o desta função em vários valores de custo.
    """
    if not pendentes:
        return {}
    cestas_pendentes = {p["bucket"] for p in pendentes}
    return {
        "positions": pendentes,
        "buckets": {
            cesta: {
                "other_gain_brl": round(por_cesta.get(cesta, 0.0), 2),
                "rate": (EQUITY_TAX_RATE if cesta == "renda_variavel"
                         else 0.0 if cesta == "fora_do_escopo" else income_tax_rate(prazo)),
                "exempt_month": bool(exempt_month) and cesta == "renda_variavel",
                "carried_loss_brl": round(carried_loss_brl, 2) if cesta == "renda_variavel" else 0.0,
            } for cesta in sorted(cestas_pendentes)
        },
        # Tudo que não muda quando o custo informado muda: execução mais o
        # imposto das cestas que não têm pendência.
        "fixed_brl": round(custo_execucao + sum(v for k, v in imposto.items()
                                                if k not in cestas_pendentes), 2),
    }


def map_portfolio(positions: list[Position], target: dict, *,
                  monthly_stock_sales_brl: float = 0.0,
                  carried_loss_brl: float = 0.0,
                  locked_tickers: tuple[str, ...] = ()) -> dict:
    """Caminho A — adequar: leva a carteira ao livro declarado do perfil.

    ``target`` é o livro declarado do perfil: pesos por emissor, fração global e
    caixa. O mapa nunca inventa peso — ele lê o que a política já declarou.

    ``locked_tickers`` são posições que o cliente declarou que não vende. Elas
    permanecem e a carteira fica, por causa delas, distante do alvo. O mapa
    prefere registrar isso a fingir que a restrição não existe.
    """
    travadas = {t.removesuffix(".SA").upper() for t in locked_tickers}
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
        if pos and ticker not in travadas and pos.market_value_brl > alvo * total:
            vendas_acoes += pos.market_value_brl - alvo * total
    for ticker, pos in atual.items():
        if pos.bucket is Bucket.ACAO and ticker not in alvo_acoes and ticker not in travadas:
            vendas_acoes += pos.market_value_brl
    mes_isento = vendas_acoes <= 20_000.0

    moves: list[Move] = []
    vendas: list[tuple[Position, float, float]] = []
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

        if ticker in travadas and excesso > tolerancia:
            moves.append(Move(ticker, "manter", pos.market_value_brl, pos.market_value_brl,
                              "travada pelo cliente", notes=[
                                  f"fica {excesso / total * 100:.1f} ponto(s) acima do peso do "
                                  f"perfil; a carteira não chega ao alvo enquanto ela ficar"]))
            continue

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
        # Com custo parcial, market_value menos cost_basis não é o ganho: é o
        # ganho que existiria se o custo conhecido fosse o custo todo. Publicar
        # esse número seria inventar, e ele é grande justamente onde mais engana.
        ganho = _realised_gain(pos, excesso) if pos.tax_computable else 0.0
        custo = excesso * TRADE_COST
        notas = []
        if not pos.tax_computable:
            notas.append("imposto ainda não calculado: falta informar quanto você pagou")
        if ganho > 0 and mes_isento and pos.bucket is Bucket.ACAO:
            notas.append("isento pela regra dos vinte mil no mês, se nada mais for vendido")
        # Prejuízo fora do escopo não abate nada aqui: a cesta dele não se
        # encontra com a de ações. Dizer o contrário seria prometer um crédito
        # que a lei não dá.
        if ganho < 0 and pos.bucket is not Bucket.FORA_DO_ESCOPO:
            notas.append("prejuízo realizado: abate o ganho das outras vendas do mesmo tipo")
        vendas.append((pos, ganho, excesso))
        if not pos.liquid:
            notas.append("posição sem liquidez diária: a saída depende do vencimento ou do secundário")
        # "Não está na cesta" só cabe em ativo que a política avalia. Dizer isso
        # de um ativo fora do escopo sugere que ele foi analisado e reprovado —
        # ele não foi olhado, e a diferença importa para quem lê depois.
        if pos.bucket is Bucket.FORA_DO_ESCOPO:
            motivo = "fora do que a política escolhe"
            notas.append("regime tributário próprio: o imposto desta venda não é apurado aqui")
        else:
            motivo = "não faz parte da carteira do perfil" if vender_tudo else "acima do peso declarado"
        moves.append(Move(
            ticker, "vender" if vender_tudo else "reduzir",
            pos.market_value_brl, alvo_brl, motivo,
            round(custo, 2), round(ganho, 2), 0.0, notas))

    for ticker, peso in sorted(alvo_acoes.items()):
        if ticker in atual:
            continue
        alvo_brl = peso * total
        moves.append(Move(ticker, "comprar", 0.0, alvo_brl, "entra pela seleção do perfil",
                          round(alvo_brl * TRADE_COST, 2)))
    if alvo_global > 0 and not any(p.bucket is Bucket.FUNDO_GLOBAL for p in positions):
        moves.append(Move(GLOBAL_TICKER, "comprar", 0.0, alvo_global * total,
                          "fatia em bolsa dos EUA, declarada pela política",
                          round(alvo_global * total * TRADE_COST, 2)))

    # A apuração é por cesta, não por venda: só depois de somar ganhos e
    # prejuízos é que a alíquota tem sobre o que incidir. O imposto é do
    # conjunto, e rateá-lo por movimento inventaria uma precisão que a lei não
    # tem — cada linha mostra o ganho que realizou, o total aparece no fechamento.
    por_cesta, imposto_por_cesta, sem_custo = _apura(vendas, mes_isento, carried_loss_brl)

    custo_total = sum(m.trade_cost_brl for m in moves)
    imposto_total = sum(imposto_por_cesta.values())
    girado = sum(abs(m.delta_brl) for m in moves) / 2

    fgc = {}
    for p in positions:
        if p.bucket is Bucket.RENDA_FIXA and p.conglomerate:
            fgc[p.conglomerate] = fgc.get(p.conglomerate, 0.0) + p.market_value_brl
    estouros = {k: round(v, 2) for k, v in fgc.items() if v > FGC_PER_CONGLOMERATE_BRL}

    return {
        "path": "adequar",
        "path_label": "Adequar a carteira ao perfil",
        "modules": ["Módulo 1 — Seleção", "Módulo 2 — Proteção"],
        "track_record_applies": True,
        "carried_loss_brl": round(carried_loss_brl, 2),
        "locked_tickers": sorted(travadas),
        "total_brl": round(total, 2),
        "alignment": round(aderente / total, 4),
        "turnover_brl": round(girado, 2),
        "transition_cost_brl": round(custo_total, 2),
        "transition_tax_brl": round(imposto_total, 2),
        "transition_total_brl": round(custo_total + imposto_total, 2),
        "transition_cost_pct": round((custo_total + imposto_total) / total, 5),
        "exempt_month_assumed": mes_isento,
        # Um imposto parcial precisa dizer que é parcial na mesma estrutura em
        # que é publicado. Deixar isso para uma nota de rodapé é como não dizer.
        "tax_is_complete": not sem_custo,
        "positions_without_cost_basis": sem_custo,
        # Quanto está sendo vendido sem que o imposto possa ser apurado. Sem
        # este número, "imposto parcial" não tem tamanho, e um total pequeno ao
        # lado de uma ressalva pequena é lido como total pequeno.
        "unpriced_sale_brl": round(sum(p["sale_brl"] for p in sem_custo), 2),
        "pending_resolution": _resolucao(sem_custo, por_cesta, imposto_por_cesta,
                                         custo_total, mes_isento, carried_loss_brl),
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
            "O custo inclui o imposto que a venda realiza, que é o número que costuma faltar. "
            "E não dizemos em quanto tempo a mudança se paga: isso exigiria prever retorno, e "
            "projeções assim erram a favor de quem as faz."),
    }


def adapt_portfolio(positions: list[Position], target: dict, *,
                    monthly_stock_sales_brl: float = 0.0,
                    carried_loss_brl: float = 0.0,
                    locked_tickers: tuple[str, ...] = ()) -> dict:
    """Caminho B — manter a seleção do cliente e aplicar só o Módulo 2.

    A oferta comercialmente fácil seria "fique com a sua carteira e ganhe o
    nosso retorno". Ela é falsa, e vale ser explícito sobre por quê: o retorno
    publicado foi medido na escada declarada, que é seleção **mais** proteção.
    Uma carteira que mantém a seleção de outra pessoa recebe metade do método, e
    nenhum número deste projeto descreve o resultado dessa metade.

    O que este caminho aplica são os limites que não são preferência de gosto,
    são teto de risco, e que valem para qualquer cesta de ações:

    * o orçamento de ações do perfil, que define quanto pode oscilar;
    * o teto de concentração por emissor que a própria política declara;
    * a cobertura do FGC na renda fixa;
    * a camada de proteção, que passa a observar e a cortar exposição nos
      estados declarados.

    Nada sai por "não estar na cesta". Custa pouco, mexe pouco, e entrega menos
    do que o outro caminho — as três coisas ao mesmo tempo, o que é justamente o
    que faz dele uma escolha e não um consolo.
    """
    total = sum(p.market_value_brl for p in positions)
    if total <= 0:
        raise ValueError("Carteira sem valor de mercado.")

    travadas = {t.removesuffix(".SA").upper() for t in locked_tickers}
    alvo_acoes = {t.removesuffix(".SA"): w for t, w in target["positions"].items()}
    orcamento_acoes = sum(alvo_acoes.values()) + float(target.get("global_sleeve", 0.0))

    variavel = [p for p in positions if p.bucket in (Bucket.ACAO, Bucket.FUNDO_GLOBAL)]
    exposicao = sum(p.market_value_brl for p in variavel) / total

    # O teto de concentração não pode ser o peso declarado da política. Aquele
    # número (perto de dez por cento) é o que sobra ao dividir o orçamento entre
    # oito emissores; aplicá-lo a quem tem três nomes não seria disciplina de
    # concentração, seria obrigar a refazer a carteira por uma porta que promete
    # não a refazer. O limite aqui é relativo à carteira do próprio cliente:
    # nenhum emissor acima do dobro do peso médio dos que ele já tem. É um
    # limite escolhido para este caminho, não um número medido no histórico, e o
    # dossiê diz isso com todas as letras.
    teto_emissor = (2.0 * exposicao / len(variavel)) if variavel else 1.0

    moves: list[Move] = []
    vendas: list[tuple[Position, float, float]] = []
    # Corte proporcional para caber no orçamento: sem o Módulo 1 não existe
    # critério para dizer qual emissor é pior, então nenhum é escolhido.
    corte = max(0.0, (exposicao - orcamento_acoes) / exposicao) if exposicao > orcamento_acoes else 0.0

    for pos in sorted(positions, key=lambda p: p.ticker):
        ticker = pos.ticker.removesuffix(".SA")
        if pos.bucket is Bucket.FORA_DO_ESCOPO:
            moves.append(Move(ticker, "manter", pos.market_value_brl, pos.market_value_brl,
                              "fora do que a política escolhe",
                              notes=["a camada de proteção não observa nem cobre esta posição"]))
            continue
        if pos.bucket in (Bucket.CAIXA, Bucket.RENDA_FIXA):
            moves.append(Move(ticker, "manter", pos.market_value_brl, pos.market_value_brl,
                              "renda fixa mantida"))
            continue

        alvo_brl = pos.market_value_brl * (1.0 - corte)
        motivo = "dentro dos limites do perfil"
        if corte > 0:
            motivo = "orçamento de ações do perfil"
        if alvo_brl > teto_emissor * total:
            alvo_brl = teto_emissor * total
            motivo = "teto de concentração por emissor"

        excesso = pos.market_value_brl - alvo_brl
        if excesso <= max(1.0, total * 1e-4):
            moves.append(Move(ticker, "manter", pos.market_value_brl, pos.market_value_brl,
                              "dentro dos limites do perfil"))
            continue
        if ticker in travadas:
            moves.append(Move(ticker, "manter", pos.market_value_brl, pos.market_value_brl,
                              "travada pelo cliente",
                              notes=[f"excede o limite em {excesso / total * 100:.1f} ponto(s) e "
                                     f"permanece por decisão do cliente"]))
            continue

        ganho = _realised_gain(pos, excesso) if pos.tax_computable else 0.0
        vendas.append((pos, ganho, excesso))
        if not pos.tax_computable:
            notas = ["imposto ainda não calculado: falta informar quanto você pagou"]
        elif ganho < 0:
            notas = ["prejuízo realizado: abate o ganho das outras vendas do mesmo tipo"]
        else:
            notas = []
        moves.append(Move(ticker, "reduzir", pos.market_value_brl, alvo_brl, motivo,
                          round(excesso * TRADE_COST, 2), round(ganho, 2), 0.0, notas))

    vendas_acoes = monthly_stock_sales_brl + sum(
        m.from_brl - m.to_brl for m in moves if m.action == "reduzir")
    mes_isento = vendas_acoes <= 20_000.0

    por_cesta, imposto_por_cesta, sem_custo = _apura(vendas, mes_isento, carried_loss_brl)

    custo_total = sum(m.trade_cost_brl for m in moves)
    imposto_total = sum(imposto_por_cesta.values())
    girado = sum(abs(m.delta_brl) for m in moves) / 2

    fgc = {}
    for p in positions:
        if p.bucket is Bucket.RENDA_FIXA and p.conglomerate:
            fgc[p.conglomerate] = fgc.get(p.conglomerate, 0.0) + p.market_value_brl
    estouros = {k: round(v, 2) for k, v in fgc.items() if v > FGC_PER_CONGLOMERATE_BRL}

    fora = sum(p.market_value_brl for p in positions if p.bucket is Bucket.FORA_DO_ESCOPO)
    coberto = sum(m.to_brl for m in moves
                  if next(p for p in positions if p.ticker.removesuffix(".SA") == m.ticker).bucket
                  in (Bucket.ACAO, Bucket.FUNDO_GLOBAL))

    # Prejuízo que este caminho deixa por realizar. Manter uma posição perdedora
    # não é neutro quando outra venda paga imposto na mesma cesta: o crédito
    # existe, está ali, e não usá-lo tem preço. É o tipo de conta que costuma
    # aparecer só na declaração do ano seguinte, tarde demais para decidir.
    vendidos = {m.ticker for m in moves if m.action in ("reduzir", "vender")}
    latente = sum(-p.unrealised_gain_brl for p in variavel
                  if p.unrealised_gain_brl < 0 and p.ticker.removesuffix(".SA") not in vendidos)
    # Nunca mais que o imposto que este caminho de fato paga: um crédito só vale
    # o que existe para abater, e num mês isento ele não vale nada hoje.
    economia = min(latente * EQUITY_TAX_RATE, imposto_por_cesta.get("renda_variavel", 0.0))
    abaixo = exposicao < orcamento_acoes

    return {
        "path": "adaptar",
        "path_label": "Manter a carteira e aplicar a proteção",
        "modules": ["Módulo 2 — Proteção"],
        "track_record_applies": False,
        "carried_loss_brl": round(carried_loss_brl, 2),
        "locked_tickers": sorted(travadas),
        "total_brl": round(total, 2),
        "alignment": 1.0,
        "equity_before": round(exposicao, 4),
        "equity_budget": round(orcamento_acoes, 4),
        "equity_after": round(coberto / total, 4),
        "equity_below_budget": bool(abaixo),
        "issuer_cap": round(teto_emissor, 4),
        "issuer_cap_rule": ("dobro do peso médio dos emissores que o cliente já tem; limite "
                            "escolhido para este caminho, não medido no histórico"),
        "unrealised_loss_kept_brl": round(latente, 2),
        "tax_left_on_table_brl": round(max(0.0, economia), 2),
        "out_of_scope_brl": round(fora, 2),
        "turnover_brl": round(girado, 2),
        "transition_cost_brl": round(custo_total, 2),
        "transition_tax_brl": round(imposto_total, 2),
        "transition_total_brl": round(custo_total + imposto_total, 2),
        "transition_cost_pct": round((custo_total + imposto_total) / total, 5),
        "exempt_month_assumed": mes_isento,
        # Um imposto parcial precisa dizer que é parcial na mesma estrutura em
        # que é publicado. Deixar isso para uma nota de rodapé é como não dizer.
        "tax_is_complete": not sem_custo,
        "positions_without_cost_basis": sem_custo,
        # Quanto está sendo vendido sem que o imposto possa ser apurado. Sem
        # este número, "imposto parcial" não tem tamanho, e um total pequeno ao
        # lado de uma ressalva pequena é lido como total pequeno.
        "unpriced_sale_brl": round(sum(p["sale_brl"] for p in sem_custo), 2),
        "pending_resolution": _resolucao(sem_custo, por_cesta, imposto_por_cesta,
                                         custo_total, mes_isento, carried_loss_brl),
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
            for m in sorted(moves, key=lambda x: (x.action == "manter", -abs(x.delta_brl)))
        ],
        "honesty": (
            "Aqui os seus ativos ficam e ganham a proteção nas quedas. O retorno que a "
            "Benevente publica foi medido escolhendo os ativos e protegendo, junto, então ele "
            "não descreve esta carteira. Dá para dizer o que a proteção faz — reduzir a "
            "exposição quando o mercado cai —, não quanto ela renderia aqui."),
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
