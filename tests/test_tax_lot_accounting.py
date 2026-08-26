"""A apuração por lote precisa obedecer à lei antes de obedecer à série.

O ponto fraco clássico de um motor tributário é passar nos números agregados
enquanto erra a mecânica: isenção consumindo prejuízo, ETF herdando isenção,
compensação negativa. Os testes unitários cravam a mecânica em casos de
resposta conhecida; a integração roda o livro publicado e verifica as
propriedades que qualquer contador exigiria do resultado.
"""
from pathlib import Path
import json

import pytest

from tax_lot_accounting import (MonthAccumulator, Position, settle_month,
                                _load_inputs, simulate, EQUITY_RATE)

ROOT = Path(__file__).resolve().parents[1]


def month(stock_proceeds=0.0, stock_gain=0.0, etf_proceeds=0.0, etf_gain=0.0):
    acc = MonthAccumulator()
    acc.stock_proceeds, acc.stock_gain = stock_proceeds, stock_gain
    acc.etf_proceeds, acc.etf_gain = etf_proceeds, etf_gain
    return acc


def test_exempt_month_pays_nothing_and_keeps_the_carryforward() -> None:
    out = settle_month(month(stock_proceeds=19_999.0, stock_gain=5_000.0), loss_carryforward=1_000.0)
    assert out["tax"] == 0.0
    assert out["exempt_gain"] == 5_000.0
    assert out["carryforward_out"] == 1_000.0


def test_taxable_month_offsets_losses_before_the_rate() -> None:
    out = settle_month(month(stock_proceeds=50_000.0, stock_gain=10_000.0), loss_carryforward=4_000.0)
    assert out["loss_offset"] == 4_000.0
    assert out["tax"] == pytest.approx(EQUITY_RATE * 6_000.0)
    assert out["carryforward_out"] == 0.0


def test_losses_accumulate_even_in_an_exempt_month() -> None:
    out = settle_month(month(stock_proceeds=5_000.0, stock_gain=-3_000.0), loss_carryforward=0.0)
    assert out["tax"] == 0.0
    assert out["carryforward_out"] == 3_000.0


def test_etf_gain_is_taxed_even_when_stock_sales_are_exempt() -> None:
    out = settle_month(month(stock_proceeds=1_000.0, stock_gain=200.0,
                             etf_proceeds=30_000.0, etf_gain=2_000.0), loss_carryforward=0.0)
    assert out["exempt_gain"] == 200.0
    assert out["tax"] == pytest.approx(EQUITY_RATE * 2_000.0)


def test_average_cost_follows_purchases_and_partial_sales() -> None:
    position = Position()
    position.buy(100.0, 10.0)
    position.buy(100.0, 20.0)
    proceeds, gain = position.sell(100.0, 30.0)
    # custo médio ~15 por unidade (mais custos); o ganho fica perto de 1.500
    assert gain == pytest.approx(100 * 30 - 100 * 15, rel=0.01)
    assert position.quantity == pytest.approx(100.0)


@pytest.fixture(scope="module")
def published_run():
    composition, panel, ibov = _load_inputs()
    ledger, summary = simulate("equilibrado", 300_000, composition, panel, ibov)
    return ledger, summary


def test_published_book_satisfies_accounting_invariants(published_run) -> None:
    ledger, summary = published_run
    assert (ledger.tax >= 0).all()
    assert (ledger.carryforward_brl >= 0).all()
    # Ganho isento só existe em mês isento, por construção da lei.
    assert (ledger.loc[ledger.exempt_gain > 0, "exempt_month"]).all()
    assert summary["terminal_wealth_brl"] > summary["capital_brl"]
    # Isenção e compensação só reduzem: nesta janela o lote fica abaixo do agregado.
    assert summary["lot_level_tax_brl"] <= summary["aggregate_annual_tax_brl"]


def test_artifact_matches_a_fresh_run(published_run) -> None:
    _, summary = published_run
    stored = json.loads((ROOT / "artifacts" / "tax_lot_accounting" / "summary.json").read_text(encoding="utf-8"))
    row = next(r for r in stored["runs"]
               if r["profile"] == "equilibrado" and r["capital_brl"] == 300_000)
    assert row["lot_level_tax_brl"] == pytest.approx(summary["lot_level_tax_brl"], abs=0.01)
