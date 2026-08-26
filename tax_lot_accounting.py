"""Apuração de IR de renda variável por ativo e custo médio, mês a mês.

O modelo tributário publicado até aqui estimava o imposto das vendas de forma
agregada: uma fração realizada por período vezes a alíquota. A lei não funciona
assim. O investidor pessoa física apura por ativo, ao custo médio de aquisição,
consolida as vendas por mês-calendário, aplica a isenção quando as vendas de
ações à vista do mês não passam de vinte mil reais, compensa prejuízos
acumulados e só então recolhe 15% sobre o ganho líquido. ETFs (a perna IVVB11)
pagam 15% sem direito à isenção, na mesma cesta de compensação das operações
comuns.

Este módulo reconstrói o livro diário de cada perfil declarado — decisão anual
de janeiro, deriva de preços dentro do ano, reduções e recomposições da camada
de proteção, perna global fora da camada — e replica essa apuração trade a
trade. As entradas são as mesmas da publicação: ``web/composition.json`` para
pesos e datas de decisão, o painel de retorno total com IVVB11 e TITULO_CDI
para preços e caixa, e o sinal de estresse congelado do registro para o
multiplicador diário.

Limites declarados: o recolhimento é debitado no fechamento do mês em que o
ganho ocorre (o DARF real vence no mês seguinte; a diferença de carrego é
imaterial na janela); o imposto da parcela em CDI segue fora deste livro,
tratado pelo modelo anual existente; e nada aqui substitui a conciliação com
nota de corretagem, que exige operação real.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import argparse
import json

import pandas as pd

from benevente2_event_risk import observable_stress, state_with_hysteresis
from portfolio_risk import risk_profile_spec
from profile_intrayear_risk import FIXED_OVERLAY
from total_return_adapter import load_total_return_export

ROOT = Path(__file__).resolve().parent
COMPOSITION = ROOT / "web" / "composition.json"
PRICES = ROOT / "data" / "prices_b3_with_global_2011_2025.csv"
PRICES_MANIFEST = ROOT / "data" / "prices_b3_with_global_2011_2025_manifest.json"
BENCHMARKS = ROOT / "data" / "benchmarks_market_2011_2025.csv"
OUT = ROOT / "artifacts" / "tax_lot_accounting"

EQUITY_RATE = 0.15
MONTHLY_EXEMPTION_BRL = 20_000.0
# Corretagem e emolumentos entram no custo de aquisição e saem do produto da
# venda; dez pontos-base por perna é a mesma ordem usada na camada de proteção.
TRADE_COST = 10.0 / 10_000
GLOBAL_TICKER = "IVVB11"
CASH_TICKER = "TITULO_CDI"
CAPITALS_BRL = (100_000, 300_000, 1_000_000, 5_000_000)
PROFILES = ("conservador", "equilibrado", "arrojado")


@dataclass
class Position:
    quantity: float = 0.0
    average_cost: float = 0.0  # por unidade, já com custos de compra

    def buy(self, quantity: float, price: float) -> float:
        spend = quantity * price * (1 + TRADE_COST)
        total_cost = self.average_cost * self.quantity + spend
        self.quantity += quantity
        self.average_cost = total_cost / self.quantity if self.quantity > 0 else 0.0
        return spend

    def sell(self, quantity: float, price: float) -> tuple[float, float]:
        quantity = min(quantity, self.quantity)
        proceeds = quantity * price * (1 - TRADE_COST)
        gain = proceeds - quantity * self.average_cost
        self.quantity -= quantity
        if self.quantity <= 1e-12:
            self.quantity, self.average_cost = 0.0, 0.0
        return proceeds, gain


@dataclass
class MonthAccumulator:
    stock_proceeds: float = 0.0
    stock_gain: float = 0.0
    etf_proceeds: float = 0.0
    etf_gain: float = 0.0

    def record(self, proceeds: float, gain: float, is_etf: bool) -> None:
        if is_etf:
            self.etf_proceeds += proceeds
            self.etf_gain += gain
        else:
            self.stock_proceeds += proceeds
            self.stock_gain += gain


def settle_month(acc: MonthAccumulator, loss_carryforward: float) -> dict:
    """A apuração mensal da lei, como uma função pura para poder ser testada.

    Ganho de ações em mês isento não paga e não consome prejuízo acumulado;
    prejuízo de ações compõe a compensação mesmo em mês isento; ETF nunca é
    isento e compensa na mesma cesta.
    """
    exempt = acc.stock_proceeds <= MONTHLY_EXEMPTION_BRL
    exempt_gain = acc.stock_gain if (exempt and acc.stock_gain > 0) else 0.0
    stock_component = 0.0 if exempt_gain else acc.stock_gain
    base = stock_component + acc.etf_gain
    if base <= 0:
        return {"exempt_month": exempt, "exempt_gain": exempt_gain, "taxable_base": base,
                "loss_offset": 0.0, "tax": 0.0, "carryforward_out": loss_carryforward - min(base, 0.0)}
    offset = min(loss_carryforward, base)
    return {"exempt_month": exempt, "exempt_gain": exempt_gain, "taxable_base": base,
            "loss_offset": offset, "tax": EQUITY_RATE * (base - offset),
            "carryforward_out": loss_carryforward - offset}


def _load_inputs() -> tuple[dict, pd.DataFrame, pd.Series]:
    composition = json.loads(COMPOSITION.read_text(encoding="utf-8"))
    prices, _ = load_total_return_export(str(PRICES), str(PRICES_MANIFEST))
    # Sessões sem negociação (suspensão, deslistagem no meio do ano) carregam o
    # último preço válido: é o valor pelo qual a posição seria liquidada e o
    # que impede um NaN de contaminar a apuração do mês.
    panel = prices.set_index("date").sort_index().ffill()
    ibov = (pd.read_csv(BENCHMARKS, parse_dates=["date"]).set_index("date")["IBOVESPA"]
            .reindex(panel.index).ffill())
    return composition, panel, ibov


def multiplier_series(profile: str, ibov: pd.Series) -> pd.Series:
    stress = observable_stress(ibov, FIXED_OVERLAY)
    state = state_with_hysteresis(stress.tradable_stress, FIXED_OVERLAY.recovery_days)
    spec = risk_profile_spec(profile)
    multiplier = pd.Series(1.0, index=ibov.index)
    multiplier.loc[state.eq(1)] = spec.alert_multiplier
    multiplier.loc[state.eq(2)] = spec.severe_multiplier
    return multiplier


def simulate(profile: str, capital_brl: float, composition: dict,
             panel: pd.DataFrame, ibov: pd.Series, apply_tax: bool = True) -> tuple[pd.DataFrame, dict]:
    blocks = sorted(composition["profiles"][profile], key=lambda b: b["decision_date"])
    decisions = {}
    for block in blocks:
        date = pd.Timestamp(block["decision_date"])
        eligible = panel.index[panel.index >= date]
        decisions[eligible[0]] = block

    first = min(decisions)
    dates = panel.index[panel.index >= first]
    multiplier = multiplier_series(profile, ibov).reindex(dates).ffill().fillna(1.0)

    cash = float(capital_brl)
    book: dict[str, Position] = {}
    acc = MonthAccumulator()
    carryforward = 0.0
    rows = []
    previous_multiplier = 1.0

    def value_of(ticker: str, day: pd.Timestamp) -> float:
        position = book.get(ticker)
        if position is None or position.quantity == 0:
            return 0.0
        return position.quantity * float(panel.at[day, ticker])

    def sell(ticker: str, quantity: float, day: pd.Timestamp) -> None:
        nonlocal cash
        price = float(panel.at[day, ticker])
        assert price == price and price > 0, f"preço inválido {ticker} {day}"
        proceeds, gain = book[ticker].sell(quantity, price)
        cash += proceeds
        acc.record(proceeds, gain, is_etf=ticker.startswith(GLOBAL_TICKER))

    def buy(ticker: str, spend_brl: float, day: pd.Timestamp) -> None:
        nonlocal cash
        if spend_brl <= 0:
            return
        spend_brl = min(spend_brl, cash)
        price = float(panel.at[day, ticker])
        quantity = spend_brl / (price * (1 + TRADE_COST))
        cash -= book.setdefault(ticker, Position()).buy(quantity, price)

    for i, day in enumerate(dates):
        if i > 0:
            cdi_factor = float(panel.at[day, CASH_TICKER]) / float(panel.at[dates[i - 1], CASH_TICKER])
            cash *= cdi_factor

        if day in decisions:
            block = decisions[day]
            m_today = float(multiplier.loc[day])
            total = cash + sum(value_of(t, day) for t in list(book))
            targets = {p["ticker"].removesuffix(".SA"): p["weight"] * total * m_today
                       for p in block["positions"]}
            if block.get("global_sleeve"):
                targets[GLOBAL_TICKER] = block["global_sleeve"] * total
            for ticker in list(book):
                held = value_of(ticker, day)
                excess = held - targets.get(ticker, 0.0)
                if excess > 1e-9 and held > 0:
                    sell(ticker, book[ticker].quantity * (excess / held), day)
            for ticker, target in targets.items():
                shortfall = target - value_of(ticker, day)
                if shortfall > 1e-9:
                    buy(ticker, shortfall, day)
            previous_multiplier = m_today
        else:
            m_today = float(multiplier.loc[day])
            if m_today != previous_multiplier and previous_multiplier > 0:
                factor = m_today / previous_multiplier
                stocks = [t for t in book if not t.startswith(GLOBAL_TICKER) and book[t].quantity > 0]
                if factor < 1:
                    for ticker in stocks:
                        sell(ticker, book[ticker].quantity * (1 - factor), day)
                else:
                    values = {t: value_of(t, day) for t in stocks}
                    additional = sum(values.values()) * (factor - 1)
                    total_value = sum(values.values())
                    for ticker, held in values.items():
                        if total_value > 0:
                            buy(ticker, additional * held / total_value, day)
                previous_multiplier = m_today

        is_last = i == len(dates) - 1
        if is_last:
            for ticker in list(book):
                if book[ticker].quantity > 0:
                    sell(ticker, book[ticker].quantity, day)
        month_ends = is_last or day.month != dates[i + 1].month
        if month_ends:
            settlement = settle_month(acc, carryforward)
            carryforward = settlement.pop("carryforward_out")
            if apply_tax:
                cash -= settlement["tax"]
            rows.append({"year": day.year, "month": day.month,
                         "stock_sales_brl": acc.stock_proceeds, "stock_gain_brl": acc.stock_gain,
                         "etf_sales_brl": acc.etf_proceeds, "etf_gain_brl": acc.etf_gain,
                         **settlement, "carryforward_brl": carryforward,
                         "wealth_brl": cash + sum(value_of(t, day) for t in book)})
            acc = MonthAccumulator()

    ledger = pd.DataFrame(rows)
    years = ledger.year.nunique()
    total_realised = ledger.stock_gain_brl.sum() + ledger.etf_gain_brl.sum()
    annual = ledger.groupby("year").agg(gain=("stock_gain_brl", "sum"), etf=("etf_gain_brl", "sum"))
    aggregate_style_tax = float((EQUITY_RATE * (annual.gain + annual.etf).clip(lower=0)).sum())
    summary = {
        "profile": profile, "capital_brl": capital_brl,
        "terminal_wealth_brl": round(float(ledger.wealth_brl.iloc[-1]), 2),
        "cagr_after_equity_tax": round(float((ledger.wealth_brl.iloc[-1] / capital_brl) ** (1 / years) - 1), 6),
        "lot_level_tax_brl": round(float(ledger.tax.sum()), 2),
        "aggregate_annual_tax_brl": round(aggregate_style_tax, 2),
        "exempt_months": int(ledger.exempt_month.sum()),
        "exempt_gain_brl": round(float(ledger.exempt_gain.sum()), 2),
        "loss_offset_brl": round(float(ledger.loss_offset.sum()), 2),
        "final_carryforward_brl": round(float(carryforward), 2),
        "realised_gain_brl": round(float(total_realised), 2),
        "months": int(len(ledger)),
    }
    return ledger, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    composition, panel, ibov = _load_inputs()
    args.out.mkdir(parents=True, exist_ok=True)
    summaries = []
    for profile in PROFILES:
        for capital in CAPITALS_BRL:
            ledger, summary = simulate(profile, capital, composition, panel, ibov)
            _, gross = simulate(profile, capital, composition, panel, ibov, apply_tax=False)
            summary["cagr_before_equity_tax"] = gross["cagr_after_equity_tax"]
            summary["equity_tax_drag_pp"] = round(
                (gross["cagr_after_equity_tax"] - summary["cagr_after_equity_tax"]) * 100, 3)
            ledger.to_csv(args.out / f"ledger_{profile}_{capital}.csv", index=False)
            summaries.append(summary)
            print(f"{profile:<12} R$ {capital:>9,.0f}  imposto por lote R$ {summary['lot_level_tax_brl']:>12,.2f}"
                  f"  (agregado anual R$ {summary['aggregate_annual_tax_brl']:>12,.2f})"
                  f"  meses isentos {summary['exempt_months']:>2}")
    (args.out / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "note": ("Apuração por ativo e custo médio sobre o livro publicado dos três perfis; "
                 "isenção mensal de R$ 20 mil para ações, compensação de prejuízos, ETF sem isenção. "
                 "Caixa em CDI segue no modelo anual existente; sem conciliação com nota de corretagem."),
        "runs": summaries,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
