"""Pre-registered 5-, 10-, and 15-year real-data evaluations.

Each horizon begins with a separate 252-trading-day calibration period. No
parameters are selected using results from the horizon under evaluation.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
import pandas as pd

from backtest_engine import BacktestEngine
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from research_runner import passive_results


HORIZONS = {5: "2021-07-01", 10: "2016-07-01", 15: "2011-07-01"}


def excess_sharpe(result: pd.DataFrame, cdi: pd.DataFrame) -> float:
    excess = result.set_index("date").net_return - cdi.set_index("date").net_return
    return float(excess.mean() / (excess.std(ddof=1) + 1e-12) * (12 ** 0.5))


def evaluate_horizon(years: int, end: str, root: Path, config: SystemConfig) -> list[dict]:
    execution_start = pd.Timestamp(HORIZONS[years])
    # Calendar-year lookback is deliberately longer than the 252 trading-day requirement.
    download_start = (execution_start - pd.DateOffset(years=1)).strftime("%Y-%m-%d")
    folder = root / f"{years}y"
    folder.mkdir(parents=True, exist_ok=True)
    loader = PointInTimeDataLoader(config)
    prices = loader.fetch_prices(download_start, end)
    ibovespa = loader.fetch_ibovespa(download_start, end).reindex(prices.index).ffill()
    macro = loader.fetch_macro_data(download_start, end)
    engine = BacktestEngine(prices, config)
    proposed = engine.run(macro_data=macro, use_signals=True)
    classic = engine.run(macro_data=macro, use_signals=False)
    # First decision occurs only after the independently downloaded lookback.
    proposed = proposed[proposed.date >= execution_start].reset_index(drop=True)
    classic = classic[classic.date >= execution_start].reset_index(drop=True)
    if proposed.empty or classic.empty:
        raise RuntimeError(f"No test periods generated for {years}-year horizon.")
    cdi = passive_results(prices["TITULO_CDI"], proposed.date, config.rebalance_days)
    ibov = passive_results(ibovespa, proposed.date, config.rebalance_days)
    strategies = {"Benevente Quant AI": proposed, "MVO clássico": classic, "CDI": cdi, "Ibovespa": ibov}

    prices.to_csv(folder / "input_prices.csv")
    ibovespa.to_csv(folder / "input_ibovespa.csv")
    macro.to_csv(folder / "input_macro.csv")
    (folder / "metadata.json").write_text(json.dumps({"horizon_years": years, "execution_start": str(execution_start.date()),
        "download_start": download_start, "end_exclusive": end, "config": asdict(config),
        "sources": {"prices": "Yahoo Finance via yfinance", "CDI/macro": "Banco Central do Brasil SGS 12/432/433"}}, indent=2), encoding="utf-8")

    rows = []
    for name, result in strategies.items():
        result.to_csv(folder / f"results_{name.lower().replace(' ', '_')}.csv", index=False)
        metric = engine.metrics(result, 0.0)
        metric["sharpe_excess_cdi"] = excess_sharpe(result, cdi) if name != "CDI" else float("nan")
        metric["strategy"] = name
        metric["horizon_years"] = years
        rows.append(metric)
    metrics = pd.DataFrame(rows)
    metrics.to_csv(folder / "performance_metrics.csv", index=False)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run fixed 5/10/15-year Benevente Quant AI evaluations.")
    parser.add_argument("--end", default="2026-07-01")
    parser.add_argument("--output", default="artifacts/horizons")
    args = parser.parse_args()
    config, root = SystemConfig(), Path(args.output)
    rows = [row for years in HORIZONS for row in evaluate_horizon(years, args.end, root, config)]
    summary = pd.DataFrame(rows).sort_values(["horizon_years", "cumulative_return"], ascending=[True, False])
    summary.to_csv(root / "all_horizons_summary.csv", index=False)
    print(summary[["horizon_years", "strategy", "cumulative_return", "cagr", "annual_volatility", "sharpe_excess_cdi", "max_drawdown"]].to_string(index=False, float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()

