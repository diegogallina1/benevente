"""Does deciding more often pay for itself?

The published protocol decides once a year, in January. The natural objection is
that a year is a long time to hold a book that could be improved sooner. This
study answers the version of that question the allocation study could not: not
"should the equity share move more often", which was already tested and
rejected over 521 weekly observations, but "should the *basket itself* be
reselected more often" — rescreened, reranked and reoptimised.

Everything except the cadence is held fixed: the same rule, the same universe,
the same limits, the same panel. Only the decision dates change.

Three costs rise with frequency, and all three are modelled rather than assumed
away:

execution
    Every review pays the exchange fee plus slippage on the fraction of the
    book it moves. Twelve reviews move more than one.
realisation
    An annual review leaves most of the book in place, so most of the gain is
    deferred. Selling monthly forces realisation, and tax paid this year is
    money that stops compounding.
rate
    The Brazilian fixed-income table is regressive. A sleeve held one month is
    taxed at 22.5%, one quarter at 22.5%, and a year at 17.5%. Comparing
    cadences at a single rate would hide the part of the answer that matters
    most.

The comparison is paired by calendar year, so the eleven annual observations of
each cadence face each other directly rather than through an annualised summary
that could hide which years the difference came from.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import (
    AnnualWalkForwardConfig,
    AnnualWalkForwardEngine,
    BrazilianTaxModel,
)
from config import SystemConfig
from total_return_adapter import load_total_return_export

CADENCES = {"anual": 12, "trimestral": 3, "mensal": 1}


def _period_taxes(results: pd.DataFrame, equity_rate: float = .15) -> pd.DataFrame:
    """Charge tax per decision period, at the rate its holding length implies.

    The engine's own tax pass assumes an annual review. Here the holding length
    is a property of the cadence, so the rate is read from the regressive table
    for each period rather than fixed once for the run.
    """
    frame = results.copy()
    decision = pd.to_datetime(frame.decision_date)
    end = pd.to_datetime(frame.holding_end_exclusive)
    holding_days = (end - decision).dt.days
    # Turnover counts both legs, so half of the *next* review's turnover is the
    # share of this period's gain that actually gets realised. The last period
    # is charged as a full liquidation, the conservative terminal assumption.
    realised = (frame.turnover.shift(-1) / 2).clip(upper=1.0).fillna(1.0)
    cash_rate = holding_days.map(BrazilianTaxModel.fixed_income_rate_for)
    equity_tax = equity_rate * frame.equity_gain_rate.clip(lower=0) * realised
    cash_gain = frame.cash_weight * frame.cdi_net_return
    cash_tax = cash_rate * cash_gain.clip(lower=0) * realised
    frame["holding_days"] = holding_days
    frame["fixed_income_rate_applied"] = cash_rate
    frame["realised_share_for_tax"] = realised
    frame["period_tax"] = equity_tax + cash_tax
    frame["net_return_after_tax"] = frame.net_return - frame.period_tax
    return frame


def _calendar_years(results: pd.DataFrame, column: str) -> pd.Series:
    """Compound the periods of each calendar year into one annual return."""
    frame = results.copy()
    frame["calendar_year"] = pd.to_datetime(frame.decision_date).dt.year
    return frame.groupby("calendar_year")[column].apply(lambda values: float((1 + values).prod() - 1))


def _cagr(returns: pd.Series) -> float:
    clean = returns.dropna()
    return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")


def evaluate(engine: AnnualWalkForwardEngine, base: AnnualWalkForwardConfig,
             months: int, first_evaluated_year: int) -> dict:
    results, _, _ = engine.run(replace(base, rebalance_months=months))
    results = results[pd.to_datetime(results.decision_date).dt.year >= first_evaluated_year].reset_index(drop=True)
    if results.empty:
        raise SystemExit(f"Cadence of {months} month(s) produced no evaluated period.")
    taxed = _period_taxes(results)
    gross = _calendar_years(taxed, "gross_return")
    net = _calendar_years(taxed, "net_return")
    after_tax = _calendar_years(taxed, "net_return_after_tax")
    cdi = _calendar_years(taxed, "cdi_net_return")
    return {
        "periods": int(len(taxed)),
        "periods_per_year": round(12 / months, 4),
        "decisions_per_year": round(len(taxed) / max(len(net), 1), 2),
        "cagr_gross": _cagr(gross),
        "cagr_net_of_cost": _cagr(net),
        "cagr_after_tax": _cagr(after_tax),
        "average_turnover_per_review": float(taxed.turnover.mean()),
        "annual_turnover": float(taxed.turnover.sum() / max(len(net), 1)),
        "annual_execution_cost": float(taxed.estimated_cost_rate.sum() / max(len(net), 1)),
        "annual_tax_drag": float(taxed.period_tax.sum() / max(len(net), 1)),
        "median_holding_days": float(taxed.holding_days.median()),
        "fixed_income_rate_applied": float(taxed.fixed_income_rate_applied.median()),
        "average_realised_share": float(taxed.realised_share_for_tax.mean()),
        "years_beating_cdi": int((net > cdi).sum()),
        "years": int(len(net)),
        "_annual_net": net,
        "_annual_after_tax": after_tax,
    }


def paired_test(faster: pd.Series, annual: pd.Series, label: str) -> dict:
    """Paired comparison by calendar year, against the annual cadence."""
    joined = pd.concat([faster.rename("faster"), annual.rename("annual")], axis=1).dropna()
    difference = joined.faster - joined.annual
    if len(difference) < 3:
        return {"comparison": label, "usable": False}
    statistic, p_value = stats.ttest_rel(joined.faster, joined.annual)
    return {
        "comparison": label,
        "usable": True,
        "paired_years": int(len(difference)),
        "mean_annual_difference": float(difference.mean()),
        "years_faster_won": int((difference > 0).sum()),
        "t_statistic": float(statistic),
        "p_value": float(p_value),
        "reading": ("A cadence only counts as better if its advantage over the annual decision survives a paired "
                    "test across the whole window. A positive mean with a large p-value is noise, not evidence."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare annual, quarterly and monthly reselection of the basket.")
    parser.add_argument("--prices", required=True)
    parser.add_argument("--total-return-manifest", required=True)
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--benchmarks", required=True)
    parser.add_argument("--start-year", type=int, default=2012, help="First year the engine may decide in.")
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--first-evaluated-year", type=int, default=2015,
                        help="Periods before this year are lookback only and are excluded from every statistic.")
    parser.add_argument("--factor", default="triple_factor")
    parser.add_argument("--maximum-equity-weight", type=float, default=0.55)
    parser.add_argument("--maximum-asset-weight", type=float, default=0.176)
    parser.add_argument("--top-assets", type=int, default=5)
    parser.add_argument("--output", default="artifacts/rebalance_frequency")
    args = parser.parse_args()

    prices, _ = load_total_return_export(args.prices, args.total_return_manifest)
    fundamentals = pd.read_csv(args.fundamentals, parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(args.universe, args.mapping)
    benchmarks = pd.read_csv(args.benchmarks, parse_dates=["date"]).set_index("date")
    engine = AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals),
                                     SystemConfig(), evidence, benchmarks)
    base = AnnualWalkForwardConfig(args.start_year, args.end_year, factor=args.factor,
                                   maximum_equity_weight=args.maximum_equity_weight,
                                   maximum_asset_weight=args.maximum_asset_weight,
                                   top_assets=args.top_assets)

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    measured: dict[str, dict] = {}
    for name, months in CADENCES.items():
        print(f"Avaliando cadência {name} ({months} mês/meses)…", flush=True)
        measured[name] = evaluate(engine, base, months, args.first_evaluated_year)

    annual_net = measured["anual"]["_annual_net"]
    annual_after_tax = measured["anual"]["_annual_after_tax"]
    comparisons = []
    for name in ("trimestral", "mensal"):
        comparisons.append(paired_test(measured[name]["_annual_net"], annual_net, f"{name} vs anual, líquido de custo"))
        comparisons.append(paired_test(measured[name]["_annual_after_tax"], annual_after_tax, f"{name} vs anual, após imposto"))

    table = pd.DataFrame({name: {key: value for key, value in item.items() if not key.startswith("_")}
                          for name, item in measured.items()}).T
    table.to_csv(output / "cadence_comparison.csv")
    pd.DataFrame({name: item["_annual_net"] for name, item in measured.items()}).to_csv(output / "annual_net_by_cadence.csv")
    pd.DataFrame({name: item["_annual_after_tax"] for name, item in measured.items()}).to_csv(output / "annual_after_tax_by_cadence.csv")

    summary = {
        "rule_held_fixed": {"factor": args.factor, "maximum_equity_weight": args.maximum_equity_weight,
                            "maximum_asset_weight": args.maximum_asset_weight, "top_assets": args.top_assets},
        "evaluation_window": f"{args.first_evaluated_year}-{args.end_year - 1}",
        "cadences": {name: {key: value for key, value in item.items() if not key.startswith("_")}
                     for name, item in measured.items()},
        "paired_comparisons": comparisons,
        "note": ("Only the cadence varies. The rule, the universe, the limits and the panel are identical across "
                 "arms, so any difference is attributable to how often the basket is reselected and to the cost, "
                 "realisation and tax rate that frequency creates."),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table.to_string())
    print()
    for item in comparisons:
        if item.get("usable"):
            print(f"  {item['comparison']}: {item['mean_annual_difference']:+.2%} ao ano, p = {item['p_value']:.3f}, "
                  f"venceu em {item['years_faster_won']} de {item['paired_years']} anos")


if __name__ == "__main__":
    main()
