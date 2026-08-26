"""Does review cadence still cost the client once the tax break is modelled?

Two gaps were open. The cadence study compared twelve, three and one month and
never tested six, which is the cadence an advisory committee actually wants.
And every after-tax number in the project charged a flat 15% on realised equity
gains, although ``BrazilianTaxModel`` already carried the personal monthly
exemption on ordinary share sales and simply never used it.

The exemption is a cliff, not a deduction: sell at or under the monthly limit
and the gain is free, sell one real more and the whole gain is taxed. Its size
depends on the client's balance, so cadence cannot be answered once for
everyone. A book small enough to stay under the limit at every review pays no
equity tax at all, and splitting the same annual sale across more reviews is
precisely what puts it under the limit.

That makes this the one place where more frequent reviews can be *good for the
client* rather than merely good for whoever earns the brokerage.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

import pandas as pd

from annual_walk_forward import AnnualWalkForwardConfig, AnnualWalkForwardEngine, BrazilianTaxModel
from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from config import SystemConfig
from profile_ladder import DATA_INPUTS, protocol_for
from total_return_adapter import load_total_return_export

CADENCES = {"anual": 12, "semestral": 6, "trimestral": 3, "mensal": 1}
# Balances that bracket a real advisory book, from a first-time client to one
# far above any exemption.
PORTFOLIO_SIZES_BRL = (100_000, 300_000, 1_000_000, 5_000_000)
PROFILE = "equilibrado"


def build_engine(portfolio_value_brl: float) -> AnnualWalkForwardEngine:
    prices, _ = load_total_return_export(str(DATA_INPUTS["prices"]), str(DATA_INPUTS["total_return_manifest"]))
    fundamentals = pd.read_csv(DATA_INPUTS["fundamentals"], parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(str(DATA_INPUTS["universe"]), str(DATA_INPUTS["mapping"]))
    benchmarks = pd.read_csv(DATA_INPUTS["benchmarks"], parse_dates=["date"]).set_index("date")
    # Execution cost depends on participation in traded value, so the balance
    # has to reach the engine rather than be applied to the result afterwards.
    config = SystemConfig(initial_portfolio_value_brl=portfolio_value_brl)
    return AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals),
                                   config, evidence, benchmarks)


def period_taxes(results: pd.DataFrame, tax_model: BrazilianTaxModel, use_exemption: bool) -> pd.DataFrame:
    """Charge tax per decision period at the rate its holding length implies."""
    frame = results.copy()
    decision = pd.to_datetime(frame.decision_date)
    holding_days = (pd.to_datetime(frame.holding_end_exclusive) - decision).dt.days
    # Turnover counts both legs, so half of the next review's turnover is the
    # share of this period's gain that is actually realised. The last period is
    # charged as a full liquidation, the conservative terminal assumption.
    realised = (frame.turnover.shift(-1) / 2).clip(upper=1.0).fillna(1.0)
    # The sale happens at the next review, so it is valued at the wealth the
    # book had reached by then, not at what it started the period with.
    equity_sales = frame.closing_wealth_brl * (1 - frame.cash_weight) * realised
    equity_rate = (equity_sales.map(tax_model.equity_rate_for_sale) if use_exemption
                   else pd.Series(tax_model.equity_rate, index=frame.index))
    cash_rate = holding_days.map(BrazilianTaxModel.fixed_income_rate_for)
    equity_tax = equity_rate * frame.equity_gain_rate.clip(lower=0) * realised
    cash_tax = cash_rate * (frame.cash_weight * frame.cdi_net_return).clip(lower=0) * realised
    frame["holding_days"] = holding_days
    frame["equity_sales_brl"] = equity_sales
    frame["equity_rate_applied"] = equity_rate
    frame["exempt_review"] = equity_rate.eq(0.0)
    frame["fixed_income_rate_applied"] = cash_rate
    frame["period_tax"] = equity_tax + cash_tax
    frame["net_return_after_tax"] = frame.net_return - frame.period_tax
    return frame


def _calendar_years(frame: pd.DataFrame, column: str) -> pd.Series:
    grouped = frame.assign(calendar_year=pd.to_datetime(frame.decision_date).dt.year)
    return grouped.groupby("calendar_year")[column].apply(lambda values: float((1 + values).prod() - 1))


def _cagr(returns: pd.Series) -> float:
    clean = returns.dropna()
    return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")


def run(output: Path, start_year: int, end_year: int) -> pd.DataFrame:
    tax_model = BrazilianTaxModel()
    rows = []
    for size in PORTFOLIO_SIZES_BRL:
        engine = build_engine(size)
        base = protocol_for(PROFILE, start_year, end_year)
        for name, months in CADENCES.items():
            results, _, _ = engine.run(replace(base, rebalance_months=months))
            flat = period_taxes(results, tax_model, use_exemption=False)
            exempt = period_taxes(results, tax_model, use_exemption=True)
            net = _calendar_years(flat, "net_return")
            cdi = _calendar_years(flat, "cdi_net_return")
            years = max(len(net), 1)
            rows.append({
                "carteira_brl": size, "cadencia": name, "meses": months,
                "revisoes_por_ano": round(len(flat) / years, 2),
                "cagr_liquido": _cagr(net),
                "cagr_pos_ir_plano": _cagr(_calendar_years(flat, "net_return_after_tax")),
                "cagr_pos_ir_com_isencao": _cagr(_calendar_years(exempt, "net_return_after_tax")),
                "revisoes_isentas": float(exempt.exempt_review.mean()),
                "venda_media_brl": float(exempt.equity_sales_brl.mean()),
                "giro_anual": float(flat.turnover.sum() / years),
                "custo_execucao_anual": float(flat.estimated_cost_rate.sum() / years),
                "ir_anual_plano": float(flat.period_tax.sum() / years),
                "ir_anual_com_isencao": float(exempt.period_tax.sum() / years),
                "ganha_cdi": int((net > cdi).sum()), "anos": int(len(net)),
            })
    frame = pd.DataFrame(rows)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "cadence_by_portfolio_size.csv", index=False)
    (output / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "profile": PROFILE,
        "cadences": CADENCES,
        "portfolio_sizes_brl": list(PORTFOLIO_SIZES_BRL),
        "monthly_sale_exemption_brl": tax_model.monthly_sale_exemption_brl,
        "limitations": [
            "The exemption covers ordinary share sales only. An ETF sleeve is taxed regardless of size, so a "
            "book holding the global sleeve gets less relief than this table shows.",
            "Each review is assumed to fall in a distinct calendar month and to be the client's only share "
            "sale that month. A client selling elsewhere in the same month loses the exemption.",
            "The threshold is a legal parameter that changes; it is read from BrazilianTaxModel, not hard-coded here.",
            "Execution cost rises with cadence and is charged; the intra-year path is otherwise unchanged.",
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Cadence against portfolio size, with the monthly exemption.")
    parser.add_argument("--output", default="artifacts/cadence_exemption_v1")
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    frame = run(Path(args.output), args.start_year, args.end_year)
    print(frame.to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
