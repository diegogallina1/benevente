"""Measure what hindsight selection is worth on this factor family.

The nested protocol picks each year's factor using only years that had already
closed. A researcher reading the full-sample table instead would have picked the
best row. The difference between those two numbers, on the identical evaluation
window, is the return that hindsight manufactures — and it is the quantity a
reader needs in order to discount any published backtest, including this one.

The comparison is restricted to the years the nested protocol can evaluate,
because it spends its first years training. Comparing a hindsight winner over a
longer window against a nested rule over a shorter one would confound selection
bias with a different market period.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _cagr(series: pd.Series) -> float:
    clean = series.dropna()
    return float((1 + clean).prod() ** (1 / len(clean)) - 1) if len(clean) else float("nan")


def build(family: dict[str, Path], nested: Path) -> tuple[pd.DataFrame, dict]:
    nested_annual = pd.read_csv(nested / "annual_results.csv")
    first_year = int(nested_annual.decision_year.min())
    rows: list[dict] = []
    for name, directory in {**family, "nested_annual_selection": nested}.items():
        annual = pd.read_csv(directory / "annual_results.csv")
        annual = annual[annual.decision_year >= first_year]
        if annual.empty:
            continue
        rows.append({
            "strategy": name,
            "years": int(len(annual)),
            "cagr": _cagr(annual.net_return),
            "cagr_after_tax": _cagr(annual.net_return_after_tax),
            "cdi_cagr": _cagr(annual.cdi_net_return),
            "ibovespa_cagr": _cagr(annual.benchmark_IBOVESPA),
            "years_beating_cdi": int((annual.net_return > annual.cdi_net_return).sum()),
            "years_beating_ibovespa": int((annual.net_return > annual.benchmark_IBOVESPA).sum()),
        })
    table = pd.DataFrame(rows).sort_values("cagr", ascending=False).reset_index(drop=True)
    hindsight = table[table.strategy.ne("nested_annual_selection")].iloc[0]
    honest = table[table.strategy.eq("nested_annual_selection")].iloc[0]
    summary = {
        "evaluation_window_first_year": first_year,
        "years_evaluated": int(honest.years),
        "candidates_in_family": int(len(family)),
        "hindsight_winner": str(hindsight.strategy),
        "hindsight_winner_cagr": float(hindsight.cagr),
        "nested_selection_cagr": float(honest.cagr),
        "hindsight_premium": float(hindsight.cagr - honest.cagr),
        "reading": (
            "The nested rule never saw the year it was evaluated on. The difference against the best full-sample row "
            "is what a researcher would have added to the reported result purely by choosing after the fact."
        ),
    }
    return table, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Quantify the hindsight premium of full-sample factor selection.")
    parser.add_argument("--family-glob", default="artifacts/family_*")
    parser.add_argument("--nested", default="artifacts/v3_adaptive_moderado")
    parser.add_argument("--output", default="artifacts/selection_bias")
    args = parser.parse_args()
    family = {path.name.split("family_", 1)[-1]: path for path in sorted(Path().glob(args.family_glob)) if path.is_dir()}
    if not family:
        raise SystemExit(f"No family runs matched {args.family_glob}")
    table, summary = build(family, Path(args.nested))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    table.to_csv(output / "selection_bias_table.csv", index=False)
    (output / "selection_bias_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(table.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
