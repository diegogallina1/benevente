"""Tabulate every pre-declared factor on the same corrected panel.

This table is descriptive, not a selection device. Reading it and then
publishing the row with the highest CAGR is the same error the audit found in
the signal grid: the winner of a seven-way comparison is an order statistic, and
the sample that ranked it can no longer test it.

The strategy that goes live is chosen by the nested annual protocol instead,
which ranks the family using only years that had already closed. This file
exists so a reader can see the whole family the nested selection ranged over.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def _cagr(series: pd.Series) -> float:
    clean = series.dropna()
    return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")


def _max_drawdown(series: pd.Series) -> float:
    wealth = (1 + series.dropna()).cumprod()
    return float((wealth / wealth.cummax() - 1).min()) if len(wealth) else float("nan")


def build(runs: dict[str, Path]) -> pd.DataFrame:
    rows: list[dict] = []
    for factor, directory in sorted(runs.items()):
        annual = pd.read_csv(directory / "annual_results.csv")
        row = {
            "factor": factor,
            "years": int(len(annual)),
            "cagr": _cagr(annual.net_return),
            "cagr_after_tax": _cagr(annual.net_return_after_tax) if "net_return_after_tax" in annual else np.nan,
            "annual_volatility": float(annual.net_return.std(ddof=1)),
            "max_drawdown": _max_drawdown(annual.net_return),
            "worst_year": float(annual.net_return.min()),
            "average_turnover": float(annual.turnover.mean()),
            "average_cost_rate": float(annual.estimated_cost_rate.mean()),
        }
        for column, label in (("cdi_net_return", "cdi"), ("mvo_eligible_net_return", "mvo"),
                              ("benchmark_IBOVESPA", "ibovespa"), ("benchmark_BOVA11", "bova11")):
            if column not in annual:
                continue
            row[f"years_beating_{label}"] = int((annual.net_return > annual[column]).sum())
            row[f"excess_vs_{label}"] = _cagr(annual.net_return) - _cagr(annual[column])
        rows.append(row)
    return pd.DataFrame(rows).sort_values("cagr", ascending=False).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Tabulate the pre-declared factor family on one panel.")
    parser.add_argument("--runs-glob", default="artifacts/family_*",
                        help="Directories produced by annual_walk_forward.py, one per factor.")
    parser.add_argument("--output", default="artifacts/factor_family/factor_family_table.csv")
    args = parser.parse_args()
    runs = {path.name.split("family_", 1)[-1]: path for path in sorted(Path().glob(args.runs_glob)) if path.is_dir()}
    if not runs:
        raise SystemExit(f"No runs matched {args.runs_glob}")
    table = build(runs)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    notice = {
        "candidates": int(len(table)),
        "purpose": "descriptive_only",
        "warning": ("Selecting the top row of this table as the live strategy would consume the sample that ranked "
                    "it. The live rule is chosen by the nested annual protocol in artifacts/v3_adaptive_*."),
        "best_by_cagr": str(table.iloc[0].factor),
        "spread_in_cagr": float(table.cagr.max() - table.cagr.min()),
    }
    output.with_name("selection_notice.json").write_text(json.dumps(notice, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(json.dumps(notice, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
