"""Catálogo de renda fixa: rendimento líquido comparável e alocação com FGC.

Um escritório escolhe entre produtos que não são comparáveis do jeito que são
anunciados. Um CDB a 110% do CDI e uma LCI a 92% do CDI não podem ser ordenados
pela taxa: um paga imposto na tabela regressiva e o outro é isento, e qual dos
dois vence depende do prazo. Tesouro Selic paga custódia. Fundo DI paga taxa e
come-cotas. A comparação só existe depois de tudo isso.

O módulo faz duas coisas, e nenhuma delas é prever:

1. Traz todo produto para a mesma régua — rendimento líquido anualizado no
   horizonte declarado, depois de imposto, custódia e taxa.
2. Aloca respeitando o FGC. Duzentos e cinquenta mil reais por conglomerado por
   CPF, um milhão em janela de quatro anos. Emissor sem cobertura entra como
   risco de crédito assumido e declarado, nunca por omissão.

Enquadramento, registrado porque o catálogo mistura regimes: CDB, LCI, LCA, LC e
RDB são captação bancária, sob CMN e Banco Central, com cobertura do FGC.
Debênture, CRI e CRA são valores mobiliários, sob CVM, sem FGC. Título público é
risco soberano, sem FGC porque não precisa. A ordenação por rendimento líquido
atravessa os três regimes; a decisão de alocar, não — e é por isso que a
cobertura e o regime viajam com cada produto em vez de ficarem numa nota de
rodapé.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import json
import math

# Tabela regressiva do imposto de renda sobre aplicações financeiras.
IR_BRACKETS = ((180, 0.225), (360, 0.20), (720, 0.175), (10**9, 0.15))
IOF_DAILY_TABLE = tuple(round(1 - day / 30, 4) for day in range(1, 30))
FGC_PER_CONGLOMERATE_BRL = 250_000.0
FGC_ROLLING_CAP_BRL = 1_000_000.0
FGC_ROLLING_YEARS = 4
BUSINESS_DAYS_PER_YEAR = 252


class Regime(str, Enum):
    """Quem regula o produto — muda o que se pode afirmar sobre ele."""
    BANCARIA = "captação bancária (CMN/BCB)"
    VALOR_MOBILIARIO = "valor mobiliário (CVM)"
    SOBERANO = "título público federal"


class Index(str, Enum):
    CDI = "CDI"
    PREFIXADO = "prefixado"
    IPCA = "IPCA+"
    SELIC = "Selic"


#: Cobertura do FGC e regime por tipo de produto. É a tabela que decide se um
#: produto entra no limite por emissor ou no bolso de risco assumido.
PRODUCT_RULES = {
    "CDB":   {"regime": Regime.BANCARIA, "fgc": True,  "ir": True},
    "RDB":   {"regime": Regime.BANCARIA, "fgc": True,  "ir": True},
    "LC":    {"regime": Regime.BANCARIA, "fgc": True,  "ir": True},
    "LCI":   {"regime": Regime.BANCARIA, "fgc": True,  "ir": False},
    "LCA":   {"regime": Regime.BANCARIA, "fgc": True,  "ir": False},
    "CRI":   {"regime": Regime.VALOR_MOBILIARIO, "fgc": False, "ir": False},
    "CRA":   {"regime": Regime.VALOR_MOBILIARIO, "fgc": False, "ir": False},
    "DEBENTURE": {"regime": Regime.VALOR_MOBILIARIO, "fgc": False, "ir": True},
    "DEBENTURE_INCENTIVADA": {"regime": Regime.VALOR_MOBILIARIO, "fgc": False, "ir": False},
    "TESOURO": {"regime": Regime.SOBERANO, "fgc": False, "ir": True},
}


def income_tax_rate(days: int) -> float:
    for limit, rate in IR_BRACKETS:
        if days <= limit:
            return rate
    return IR_BRACKETS[-1][1]


def iof_factor(days: int) -> float:
    """Fração do rendimento retida por IOF em resgates com menos de trinta dias."""
    if days >= 30:
        return 0.0
    return IOF_DAILY_TABLE[max(days - 1, 0)]


@dataclass(frozen=True)
class Product:
    """Uma oferta concreta, do jeito que chega da grade do distribuidor."""
    name: str
    kind: str
    issuer: str
    conglomerate: str
    index: Index
    rate: float               # fração do índice (1.10 = 110% do CDI) ou taxa a.a.
    maturity: date
    minimum_brl: float = 1_000.0
    daily_liquidity: bool = False
    custody_fee_annual: float = 0.0
    management_fee_annual: float = 0.0
    available_brl: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in PRODUCT_RULES:
            raise ValueError(f"Produto desconhecido: {self.kind}. Conhecidos: {sorted(PRODUCT_RULES)}")

    @property
    def regime(self) -> Regime:
        return PRODUCT_RULES[self.kind]["regime"]

    @property
    def fgc_covered(self) -> bool:
        return PRODUCT_RULES[self.kind]["fgc"]

    @property
    def taxable(self) -> bool:
        return PRODUCT_RULES[self.kind]["ir"]


def gross_annual_yield(product: Product, cdi_annual: float, ipca_annual: float) -> float:
    """Rendimento bruto ao ano, antes de imposto e taxas."""
    if product.index in (Index.CDI, Index.SELIC):
        return cdi_annual * product.rate
    if product.index is Index.PREFIXADO:
        return product.rate
    if product.index is Index.IPCA:
        return (1 + ipca_annual) * (1 + product.rate) - 1
    raise ValueError(f"Índice não suportado: {product.index}")


def net_annual_yield(product: Product, reference: date, cdi_annual: float,
                     ipca_annual: float) -> dict:
    """Rendimento líquido anualizado no horizonte até o vencimento.

    O horizonte é o do próprio papel: comparar um CDB de seis meses com um de
    três anos pela taxa anunciada ignora que o primeiro paga 22,5% de imposto e
    o segundo 15%. Aqui os dois chegam na mesma unidade.
    """
    days = (product.maturity - reference).days
    if days <= 0:
        raise ValueError(f"{product.name} venceu em {product.maturity}.")
    years = days / 365.25

    gross = gross_annual_yield(product, cdi_annual, ipca_annual)
    after_fees = gross - product.custody_fee_annual - product.management_fee_annual
    accumulated = (1 + after_fees) ** years - 1

    tax_rate = income_tax_rate(days) if product.taxable else 0.0
    # O IOF morde o rendimento antes do imposto de renda, e some no trigésimo
    # dia. O que sobra da mordida é a base sobre a qual a tabela regressiva age.
    iof = iof_factor(days) if product.taxable else 0.0
    net_accumulated = accumulated * (1 - iof) * (1 - tax_rate)
    net_annual = (1 + net_accumulated) ** (1 / years) - 1

    return {
        "product": product.name,
        "kind": product.kind,
        "issuer": product.issuer,
        "regime": product.regime.value,
        "fgc_covered": product.fgc_covered,
        "days": days,
        "gross_annual": round(gross, 6),
        "tax_rate": tax_rate,
        "iof_share": round(iof, 4),
        "net_annual": round(net_annual, 6),
        # Fração do CDI *bruto* — o índice do comparador, que ninguém recebe porque
        # índice não paga imposto. Um CDB anunciado a 118% do CDI entrega perto de
        # 101% dele depois da tabela regressiva, e é esse número que se compara.
        "net_over_cdi": round(net_annual / cdi_annual, 4) if cdi_annual else None,
        "daily_liquidity": product.daily_liquidity,
    }


def rank(products: list[Product], reference: date, cdi_annual: float,
         ipca_annual: float = 0.045) -> list[dict]:
    """Ordena por rendimento líquido. O critério é um só e está declarado."""
    scored = [net_annual_yield(p, reference, cdi_annual, ipca_annual) for p in products]
    return sorted(scored, key=lambda row: -row["net_annual"])


@dataclass
class FgcLedger:
    """O que já foi usado do limite do FGC, por conglomerado e na janela móvel.

    Sem esse registro, "respeitar o FGC" é uma intenção. Com ele, é uma conta que
    o comitê pode conferir linha a linha.
    """
    per_conglomerate: dict[str, float] = field(default_factory=dict)
    rolling_used_brl: float = 0.0

    def headroom(self, conglomerate: str) -> float:
        used = self.per_conglomerate.get(conglomerate, 0.0)
        return max(0.0, min(FGC_PER_CONGLOMERATE_BRL - used,
                            FGC_ROLLING_CAP_BRL - self.rolling_used_brl))

    def record(self, conglomerate: str, amount_brl: float) -> None:
        self.per_conglomerate[conglomerate] = self.per_conglomerate.get(conglomerate, 0.0) + amount_brl
        self.rolling_used_brl += amount_brl


def allocate(products: list[Product], amount_brl: float, reference: date, cdi_annual: float,
             ipca_annual: float = 0.045, ledger: FgcLedger | None = None,
             allow_uncovered: bool = False, liquid_floor_brl: float = 0.0) -> dict:
    """Distribui o caixa pelos melhores rendimentos líquidos que o FGC permite.

    A ordem é a do rendimento líquido, mas o limite manda: quando o teto do
    conglomerado acaba, o resto vai para o próximo produto, não para o mesmo
    emissor. Produtos sem cobertura só entram se ``allow_uncovered`` for
    declarado — o risco de crédito é uma escolha, e escolhas ficam registradas.

    ``liquid_floor_brl`` reserva a parcela que a camada de proteção precisa poder
    movimentar: caixa preso num papel de dois anos não recebe nem devolve
    exposição dentro do ano.
    """
    ledger = ledger or FgcLedger()
    ranked = rank(products, reference, cdi_annual, ipca_annual)
    by_name = {p.name: p for p in products}

    allocations, remaining, rejected = [], float(amount_brl), []
    liquid_needed = min(float(liquid_floor_brl), float(amount_brl))

    for row in ranked:
        if remaining <= 0.5:
            break
        product = by_name[row["product"]]
        reason = None
        if not product.fgc_covered and not allow_uncovered:
            reason = "sem cobertura do FGC e risco de crédito não declarado"
        elif remaining - liquid_needed < product.minimum_brl and not product.daily_liquidity:
            reason = "reserva de liquidez da camada de proteção"

        if reason is None:
            room = remaining - (0.0 if product.daily_liquidity else liquid_needed)
            if product.fgc_covered:
                room = min(room, ledger.headroom(product.conglomerate))
            if product.available_brl is not None:
                room = min(room, product.available_brl)
            room = min(room, remaining)
            if room < product.minimum_brl:
                reason = ("teto do FGC no conglomerado esgotado" if product.fgc_covered
                          else "abaixo da aplicação mínima")

        if reason is not None:
            rejected.append({"product": row["product"], "reason": reason})
            continue

        allocations.append({**row, "amount_brl": round(room, 2),
                            "conglomerate": product.conglomerate})
        if product.fgc_covered:
            ledger.record(product.conglomerate, room)
        if product.daily_liquidity:
            liquid_needed = max(0.0, liquid_needed - room)
        remaining -= room

    invested = sum(a["amount_brl"] for a in allocations)
    weighted = (sum(a["amount_brl"] * a["net_annual"] for a in allocations) / invested) if invested else 0.0
    return {
        "reference": str(reference),
        "amount_brl": round(float(amount_brl), 2),
        "allocated_brl": round(invested, 2),
        "unallocated_brl": round(float(amount_brl) - invested, 2),
        "blended_net_annual": round(weighted, 6),
        "blended_over_cdi": round(weighted / cdi_annual, 4) if cdi_annual else None,
        "liquid_reserve_requested_brl": round(float(liquid_floor_brl), 2),
        "allocations": allocations,
        "rejected": rejected,
        "fgc": {"per_conglomerate": {k: round(v, 2) for k, v in ledger.per_conglomerate.items()},
                "rolling_used_brl": round(ledger.rolling_used_brl, 2),
                "per_conglomerate_cap_brl": FGC_PER_CONGLOMERATE_BRL,
                "rolling_cap_brl": FGC_ROLLING_CAP_BRL,
                "rolling_window_years": FGC_ROLLING_YEARS},
    }


def load_catalog(path) -> list[Product]:
    """Lê a grade que o próprio escritório mantém.

    O catálogo é do escritório, não nosso: as taxas mudam por dia, por faixa e
    por segmento, e nenhuma fonte pública as arquiva. O sistema ordena e aloca o
    que recebe, e registra a data do que recebeu.
    """
    payload = json.loads(open(path, encoding="utf-8").read())
    return [Product(
        name=item["name"], kind=item["kind"], issuer=item["issuer"],
        conglomerate=item.get("conglomerate", item["issuer"]),
        index=Index(item.get("index", "CDI")), rate=float(item["rate"]),
        maturity=date.fromisoformat(item["maturity"]),
        minimum_brl=float(item.get("minimum_brl", 1_000.0)),
        daily_liquidity=bool(item.get("daily_liquidity", False)),
        custody_fee_annual=float(item.get("custody_fee_annual", 0.0)),
        management_fee_annual=float(item.get("management_fee_annual", 0.0)),
        available_brl=item.get("available_brl"),
    ) for item in payload["products"]]
