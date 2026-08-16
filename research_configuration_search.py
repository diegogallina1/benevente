"""Search the portfolio configuration space without letting a year see itself.

The request is to find the best configuration and put it live. Ranking every
configuration on the full sample and publishing the winner would repeat the
error this project was audited for: the winner of a wide search is an order
statistic, and the sample that ranked it can no longer test it.

The search here is therefore nested. Every configuration is evaluated once over
the whole period, but the *choice* for decision year ``t`` uses only years that
had already closed by then, ranked by Sharpe of the excess return over CDI. The
realised return of year ``t`` comes from whichever configuration that ranking
picked, and switching configurations is charged a rebalancing cost, because in
a real book it means selling one portfolio and buying another.

Three numbers are published together, and they should be read together:

* the nested result, which is what a manager could actually have earned;
* the full-sample winner, which is what a backtest would have advertised;
* the difference, which is the return that hindsight manufactures.

The issuer cap is derived rather than searched. Setting it to a fixed fraction
of the equity budget divided by the number of holdings guarantees the cap never
binds mechanically, which is what made the previous risk ladder invert: the
aggressive profile had every name pinned at its cap and silently lost the
conviction tilt that the conservative profile kept.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

import numpy as np
import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import (
    AnnualWalkForwardConfig,
    AnnualWalkForwardEngine,
    BrazilianTaxModel,
    apply_annual_taxes,
)
from config import SystemConfig
from multiple_testing import deflated_sharpe
from total_return_adapter import load_total_return_export


# Slack factor on the issuer cap. At 1.6 the five-name book can put sixty per
# cent more in its best name than an equal split would, so the ranking still
# expresses itself, while no single issuer can dominate the sleeve.
ISSUER_CAP_SLACK = 1.6
MAXIMUM_ISSUER_CAP = .25
MINIMUM_SELECTION_YEARS = 3
SWITCHING_TURNOVER = 2.0


def configuration_grid(equity_budgets: tuple[float, ...], asset_counts: tuple[int, ...],
                       factors: tuple[str, ...]) -> list[dict]:
    """Every configuration the nested selection may choose between."""
    grid: list[dict] = []
    for budget in equity_budgets:
        for count in asset_counts:
            cap = min(MAXIMUM_ISSUER_CAP, budget / count * ISSUER_CAP_SLACK)
            for factor in factors:
                grid.append({
                    "name": f"eq{int(round(budget * 100))}_n{count}_{factor}",
                    "maximum_equity_weight": float(budget),
                    "maximum_asset_weight": float(cap),
                    "top_assets": int(count),
                    "factor": factor,
                })
    return grid


def evaluate_grid(engine: AnnualWalkForwardEngine, base: AnnualWalkForwardConfig,
                  grid: list[dict]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """Run every configuration once and collect its annual return series."""
    runs: dict[str, pd.DataFrame] = {}
    failures: list[dict] = []
    for item in grid:
        protocol = replace(base, factor=item["factor"], top_assets=item["top_assets"],
                           maximum_equity_weight=item["maximum_equity_weight"],
                           maximum_asset_weight=item["maximum_asset_weight"])
        try:
            annual, _, _ = engine.run(protocol)
        except Exception as exc:  # a configuration that cannot form a book is not a candidate
            failures.append({"name": item["name"], "reason": str(exc)[:200]})
            continue
        runs[item["name"]] = annual.set_index("decision_year")
    if not runs:
        raise RuntimeError("No configuration produced an evaluable series.")
    if failures:
        print(json.dumps({"skipped_configurations": failures}, ensure_ascii=False, indent=2))
    matrix = pd.DataFrame({name: frame.net_return for name, frame in runs.items()}).sort_index()
    return matrix, runs


def _excess_sharpe(net: pd.Series, cdi: pd.Series) -> float:
    excess = (net - cdi).dropna()
    if len(excess) < 2:
        return float("-inf")
    deviation = float(excess.std(ddof=1))
    return float(excess.mean() / deviation) if deviation > 0 else float("-inf")


def nested_selection(matrix: pd.DataFrame, cdi: pd.Series, cost_rate: float,
                     minimum_years: int = MINIMUM_SELECTION_YEARS) -> pd.DataFrame:
    """Pick each year's configuration from the years that had already closed."""
    rows: list[dict] = []
    previous_choice: str | None = None
    for position, year in enumerate(matrix.index):
        if position < minimum_years:
            continue
        history = matrix.iloc[:position]
        history_cdi = cdi.iloc[:position]
        scores = {name: _excess_sharpe(history[name], history_cdi) for name in matrix.columns}
        ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        choice = ranked[0][0]
        realised = float(matrix.loc[year, choice])
        # Changing configuration means liquidating one book and buying another.
        switching_cost = 0.0 if previous_choice in (None, choice) else cost_rate * SWITCHING_TURNOVER
        rows.append({
            "decision_year": int(year),
            "selected_configuration": choice,
            "training_years": int(position),
            "training_excess_sharpe": float(ranked[0][1]),
            "runner_up": ranked[1][0] if len(ranked) > 1 else None,
            "switched": bool(previous_choice not in (None, choice)),
            "switching_cost": switching_cost,
            "gross_of_switch_return": realised,
            "net_return": realised - switching_cost,
            "cdi_net_return": float(cdi.loc[year]),
        })
        previous_choice = choice
    if not rows:
        raise RuntimeError(f"Need more than {minimum_years} evaluated years to run a nested selection.")
    return pd.DataFrame(rows)


def attach_references(selection: pd.DataFrame, runs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Carry the independent references of whichever run supplied each year."""
    reference_columns = ["mvo_eligible_net_return", "benchmark_IBOVESPA", "benchmark_BOVA11",
                         "cdi_net_return_after_tax", "turnover", "equity_gain_rate", "cash_weight"]
    enriched = selection.copy()
    for column in reference_columns:
        values = []
        for row in selection.itertuples(index=False):
            frame = runs[row.selected_configuration]
            values.append(float(frame.loc[row.decision_year, column]) if column in frame.columns else np.nan)
        enriched[column] = values
    enriched["mvo_turnover"] = enriched.turnover
    enriched["mvo_equity_gain_rate"] = enriched.equity_gain_rate
    enriched["mvo_cash_weight"] = enriched.cash_weight
    return apply_annual_taxes(enriched, BrazilianTaxModel())


def main() -> None:
    parser = argparse.ArgumentParser(description="Nested search over the portfolio configuration space.")
    parser.add_argument("--prices", required=True)
    parser.add_argument("--total-return-manifest", required=True)
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--benchmarks", required=True)
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--equity-budgets", default="0.55,0.75,0.95")
    parser.add_argument("--asset-counts", default="5,8,12")
    parser.add_argument("--factors", default="value_quality,triple_factor,momentum_12m")
    parser.add_argument("--output", default="artifacts/configuration_search")
    args = parser.parse_args()

    prices, _ = load_total_return_export(args.prices, args.total_return_manifest)
    fundamentals = pd.read_csv(args.fundamentals, parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(args.universe, args.mapping)
    benchmarks = pd.read_csv(args.benchmarks, parse_dates=["date"]).set_index("date")
    engine = AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals),
                                     SystemConfig(), evidence, benchmarks)
    base = AnnualWalkForwardConfig(args.start_year, args.end_year)
    grid = configuration_grid(
        tuple(float(item) for item in args.equity_budgets.split(",")),
        tuple(int(item) for item in args.asset_counts.split(",")),
        tuple(item.strip() for item in args.factors.split(",")),
    )
    print(f"Evaluating {len(grid)} configurations.")
    matrix, runs = evaluate_grid(engine, base, grid)
    cdi = next(iter(runs.values())).cdi_net_return.reindex(matrix.index)
    cost_rate = float(np.nanmean([frame.estimated_cost_rate.mean() for frame in runs.values()]))
    selection = nested_selection(matrix, cdi, cost_rate)
    selection = attach_references(selection, runs)

    def cagr(series: pd.Series) -> float:
        clean = series.dropna()
        return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")

    window = selection.decision_year.tolist()
    aligned = matrix.loc[window]
    full_sample = aligned.apply(lambda column: _excess_sharpe(column, cdi.loc[window]))
    hindsight_name = str(full_sample.idxmax())
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(output / "configuration_annual_returns.csv")
    selection.to_csv(output / "nested_selection_annual.csv", index=False)
    sharpes = matrix.loc[window].apply(lambda column: column.mean() / column.std(ddof=1) if column.std(ddof=1) else np.nan).dropna()
    deflated = deflated_sharpe(selection.net_return, sharpes.to_numpy())
    summary = {
        "configurations_evaluated": int(matrix.shape[1]),
        "years_evaluated": int(len(selection)),
        "evaluation_window": f"{window[0]}-{window[-1]}",
        "nested": {
            "cagr": cagr(selection.net_return),
            "cagr_after_tax": cagr(selection.net_return_after_tax),
            "excess_sharpe_vs_cdi": _excess_sharpe(selection.net_return, selection.cdi_net_return),
            "years_beating_cdi": int((selection.net_return > selection.cdi_net_return).sum()),
            "years_beating_mvo": int((selection.net_return > selection.mvo_eligible_net_return).sum()),
            "years_beating_ibovespa": int((selection.net_return > selection.benchmark_IBOVESPA).sum()),
            "years_beating_bova11": int((selection.net_return > selection.benchmark_BOVA11).sum()),
            "configuration_switches": int(selection.switched.sum()),
            "final_configuration": str(selection.selected_configuration.iloc[-1]),
        },
        "references": {
            "cdi_cagr": cagr(selection.cdi_net_return),
            "mvo_cagr": cagr(selection.mvo_eligible_net_return),
            "ibovespa_cagr": cagr(selection.benchmark_IBOVESPA),
            "bova11_cagr": cagr(selection.benchmark_BOVA11),
        },
        "hindsight": {
            "full_sample_best_configuration": hindsight_name,
            "full_sample_best_cagr": cagr(aligned[hindsight_name]),
            "premium_over_nested": cagr(aligned[hindsight_name]) - cagr(selection.net_return),
            "warning": ("This row is what publishing the search winner would have advertised. It is not achievable: "
                        "the ranking that produced it used the years it is measured on."),
        },
        "deflated_sharpe": deflated.as_dict(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
