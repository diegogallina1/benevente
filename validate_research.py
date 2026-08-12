"""Independent, file-based quality checks for Benevente Quant AI research artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def validate(directory: Path) -> dict:
    issues: list[str] = []
    prices = pd.read_csv(directory / "input_prices.csv", index_col=0, parse_dates=True)
    checks = {
        "price_rows": len(prices),
        "price_start": str(prices.index.min().date()),
        "price_end": str(prices.index.max().date()),
        "duplicate_price_dates": int(prices.index.duplicated().sum()),
        "null_price_values": int(prices.isna().sum().sum()),
    }
    if checks["duplicate_price_dates"] or checks["null_price_values"]:
        issues.append("Input prices contain duplicate dates or missing values.")

    per_strategy = {}
    for path in directory.glob("results_*.csv"):
        data = pd.read_csv(path, parse_dates=["date"])
        recomputed_wealth = 100 * (1 + data["net_return"]).cumprod()
        max_wealth_difference = float(np.abs(recomputed_wealth - data["wealth"]).max())
        item = {
            "rows": len(data), "duplicate_dates": int(data.date.duplicated().sum()),
            "null_values": int(data.isna().sum().sum()),
            "max_wealth_recalculation_difference": max_wealth_difference,
            "negative_turnover_count": int((data.turnover < 0).sum()),
        }
        per_strategy[path.stem.removeprefix("results_")] = item
        if item["duplicate_dates"] or item["null_values"] or max_wealth_difference > 1e-8 or item["negative_turnover_count"]:
            issues.append(f"Integrity check failed for {path.name}.")

    metrics = pd.read_csv(directory / "performance_metrics.csv")
    checks["strategies"] = metrics.strategy.tolist()
    if set(checks["strategies"]) != {"Benevente Quant AI", "MVO clássico", "CDI", "Ibovespa"}:
        issues.append("Expected benchmark set is incomplete.")
    report = {"assessment": "ready_with_caveats" if not issues else "needs_revision", "checks": checks,
              "strategy_integrity": per_strategy, "issues": issues,
              "required_caveats": [
                  "Yahoo Finance is a secondary market-data source; archive input CSVs with every reported run.",
                  "The universe is fixed and current-ticker based, so survivorship bias remains unless historical constituents are introduced.",
                  "Backtest results are not investment advice and do not predict future performance.",
              ]}
    (directory / "validation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="artifacts/real_data")
    args = parser.parse_args()
    report = validate(Path(args.input))
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["assessment"] == "ready_with_caveats" else 1)

