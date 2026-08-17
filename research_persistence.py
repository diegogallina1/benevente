"""Does keeping a good position beat rebuilding the basket every January?

The published protocol turns over roughly half its book each year. Thirty of
the forty names it ever held lasted a single year; only two lasted three. That
is not the result of a rule that says "sell everything". It is the result of an
optimisation in which nothing rewards keeping a position: the incumbent book
reached the cost estimate but never the objective, so each January the solver
re-derived the portfolio from scratch and the previous holdings had no standing.

This study turns the incentive on and measures it. The optimiser already
supports an L1 penalty on distance from the incumbent book,

    max  mu' w - (gamma/2) w' S w - kappa ||w - w_prev||_1,

and kappa has always been zero on the published path. Here it is swept.

The comparison is run inside the same nested protocol that chooses everything
else, so persistence is not a parameter fitted on the evaluation window: for
decision year t the value of kappa is ranked on years that closed before t, and
year t is then evaluated once. Widening the grid widens the search, so the
deflated Sharpe is recomputed against the larger trial count. A sweep that
reports a winner without paying for the sweep is the exact failure this project
already made once.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass, replace
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import AnnualWalkForwardConfig, AnnualWalkForwardEngine
from config import SystemConfig
from multiple_testing import deflated_sharpe
from total_return_adapter import load_total_return_export

# Zero is the published behaviour: a hard top-N cut in which slipping one rank
# costs the whole position. Each step widens the band inside which an incumbent
# is kept, up to a buffer as large as the basket itself.
BUFFERS = (0, 1, 2, 3, 5, 8)
MINIMUM_SELECTION_YEARS = 3


def _excess_sharpe(net: pd.Series, cdi: pd.Series) -> float:
    excess = (net - cdi).dropna()
    if len(excess) < 2:
        return float("-inf")
    deviation = float(excess.std(ddof=1))
    return float(excess.mean() / deviation) if deviation > 0 else float("-inf")


def _cagr(returns: pd.Series) -> float:
    clean = returns.dropna()
    return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")


def _persistence(holdings: pd.DataFrame) -> dict:
    """How sticky the book actually was, independent of what it returned."""
    equities = holdings[holdings.ticker.ne("TITULO_CDI")]
    baskets = {int(year): set(frame.ticker) for year, frame in equities.groupby("decision_year")}
    years = sorted(baskets)
    kept, total = 0, 0
    for previous, current in zip(years, years[1:]):
        kept += len(baskets[current] & baskets[previous])
        total += len(baskets[previous])
    longest: dict[str, int] = {}
    for ticker in set().union(*baskets.values()) if baskets else set():
        run = 0
        for year in years:
            run = run + 1 if ticker in baskets[year] else 0
            longest[ticker] = max(longest.get(ticker, 0), run)
    return {
        "carryover_rate": kept / total if total else float("nan"),
        "distinct_names": len(longest),
        "names_lasting_one_year": sum(1 for value in longest.values() if value == 1),
        "names_lasting_three_or_more": sum(1 for value in longest.values() if value >= 3),
    }


def evaluate(engine: AnnualWalkForwardEngine, base: AnnualWalkForwardConfig, penalty: float) -> dict:
    results, _, holdings = engine.run(replace(base, retention_buffer=int(penalty)))
    return {"results": results, "holdings": holdings}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep the persistence penalty inside the nested protocol.")
    parser.add_argument("--prices", required=True)
    parser.add_argument("--total-return-manifest", required=True)
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--benchmarks", required=True)
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--factor", default="triple_factor")
    parser.add_argument("--maximum-equity-weight", type=float, default=0.55)
    parser.add_argument("--maximum-asset-weight", type=float, default=0.176)
    parser.add_argument("--top-assets", type=int, default=5)
    parser.add_argument("--output", default="artifacts/persistence")
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

    runs: dict[float, dict] = {}
    for penalty in BUFFERS:
        print(f"Avaliando folga de permanencia = {penalty}…", flush=True)
        runs[penalty] = evaluate(engine, base, penalty)

    matrix = pd.DataFrame({penalty: run["results"].set_index("decision_year").net_return
                           for penalty, run in runs.items()})
    cdi = next(iter(runs.values()))["results"].set_index("decision_year").cdi_net_return
    ibovespa = next(iter(runs.values()))["results"].set_index("decision_year").get("benchmark_IBOVESPA")

    # Escolha aninhada de kappa: cada ano usa apenas os anos ja encerrados.
    rows = []
    for position, year in enumerate(matrix.index):
        if position < MINIMUM_SELECTION_YEARS:
            continue
        history, history_cdi = matrix.iloc[:position], cdi.iloc[:position]
        scores = {penalty: _excess_sharpe(history[penalty], history_cdi) for penalty in matrix.columns}
        choice = max(scores, key=lambda key: (scores[key], -key))
        rows.append({"decision_year": int(year), "selected_buffer": int(choice),
                     "net_return": float(matrix.loc[year, choice]),
                     "cdi_net_return": float(cdi.loc[year]),
                     "benchmark_IBOVESPA": float(ibovespa.loc[year]) if ibovespa is not None else np.nan})
    nested = pd.DataFrame(rows)
    window = nested.decision_year.tolist()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(output / "annual_return_by_penalty.csv")
    nested.to_csv(output / "nested_penalty_selection.csv", index=False)

    fixed = {}
    for penalty, run in runs.items():
        evaluated = run["results"][run["results"].decision_year.isin(window)]
        fixed[penalty] = {
            "cagr": _cagr(evaluated.net_return),
            "excess_sharpe_vs_cdi": _excess_sharpe(evaluated.net_return, evaluated.cdi_net_return),
            "average_turnover": float(evaluated.turnover.mean()),
            "years_beating_cdi": int((evaluated.net_return > evaluated.cdi_net_return).sum()),
            **_persistence(run["holdings"][run["holdings"].decision_year.isin(window)]),
        }

    baseline = matrix.loc[window, 0]
    comparisons = []
    for penalty in matrix.columns:
        if penalty == 0:
            continue
        arm = matrix.loc[window, penalty]
        statistic, p_value = stats.ttest_rel(arm, baseline)
        comparisons.append({"buffer": int(penalty),
                            "mean_annual_difference": float((arm - baseline).mean()),
                            "years_won": int((arm > baseline).sum()),
                            "paired_years": int(len(arm)),
                            "t_statistic": float(statistic), "p_value": float(p_value)})

    sharpes = matrix.loc[window].apply(
        lambda column: column.mean() / column.std(ddof=1) if column.std(ddof=1) else np.nan).dropna()
    deflated = deflated_sharpe(nested.net_return, sharpes.to_numpy())

    summary = {
        "buffers_evaluated": [int(item) for item in BUFFERS],
        "evaluation_window": f"{window[0]}-{window[-1]}",
        "fixed_buffer_arms": {str(key): value for key, value in fixed.items()},
        "nested_choice": {
            "cagr": _cagr(nested.net_return),
            "excess_sharpe_vs_cdi": _excess_sharpe(nested.net_return, nested.cdi_net_return),
            "buffer_by_year": {int(row.decision_year): int(row.selected_buffer)
                                for row in nested.itertuples(index=False)},
        },
        "paired_vs_published_hard_cut": comparisons,
        "deflated_sharpe": asdict(deflated) if is_dataclass(deflated) else deflated,
        "note": ("Only the persistence penalty varies; the factor, the limits, the universe and the panel are "
                 "identical across arms. The published protocol is the kappa = 0 arm."),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    table = pd.DataFrame(fixed).T
    table.index.name = "folga"
    print()
    print(table.to_string())
    print()
    print(f"escolha aninhada da folga: CAGR {summary['nested_choice']['cagr']:.2%}, "
          f"por ano {summary['nested_choice']['buffer_by_year']}")
    for item in comparisons:
        print(f"  folga={item['buffer']} vs corte duro: {item['mean_annual_difference']:+.2%} ao ano, "
              f"p = {item['p_value']:.3f}, venceu em {item['years_won']} de {item['paired_years']}")


if __name__ == "__main__":
    main()
