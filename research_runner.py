"""Reproducible empirical evaluation for Benevente Quant AI.

The runner saves every input and output needed to audit a run. It must not be
used as investment advice or treated as evidence of future performance.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from backtest_engine import BacktestEngine
from config import SystemConfig
from data_loader import PointInTimeDataLoader


def passive_results(prices: pd.Series, decision_dates: pd.Series, rebalance_days: int) -> pd.DataFrame:
    daily = prices.pct_change().dropna()
    wealth, rows = 100.0, []
    for date in decision_dates:
        position = daily.index.get_loc(date)
        period = daily.iloc[position:position + rebalance_days]
        net_return = float((1 + period).prod() - 1)
        wealth *= 1 + net_return
        rows.append({"date": date, "wealth": wealth, "gross_return": net_return, "net_return": net_return,
                     "turnover": 0.0, "friction_cost": 0.0})
    return pd.DataFrame(rows)


def evaluate(config: SystemConfig, start: str, end: str, output: Path, offline: bool = False) -> pd.DataFrame:
    output.mkdir(parents=True, exist_ok=True)
    loader = PointInTimeDataLoader(config)
    prices = loader.fetch_prices(start, end, offline=offline)
    if offline:
        ibovespa = prices["PETR4.SA"].rename("IBOVESPA_PROXY")
        macro = None
        sources = {"mode": "synthetic deterministic test data", "seed": 2026}
    else:
        ibovespa = loader.fetch_ibovespa(start, end)
        macro = loader.fetch_macro_data(start, end)
        sources = {
            "mode": "real market data",
            "b3_prices": "Yahoo Finance via yfinance (auto-adjusted close)",
            "cdi": "Banco Central do Brasil SGS 12 (daily CDI rate)",
            "macro": "Banco Central do Brasil SGS 432 (Selic target) and 433 (IPCA monthly)",
            "downloaded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        }
    prices.to_csv(output / "input_prices.csv")
    ibovespa.to_csv(output / "input_ibovespa.csv")
    if macro is not None:
        macro.to_csv(output / "input_macro.csv")
    (output / "run_metadata.json").write_text(json.dumps({"config": asdict(config), "start": start, "end": end,
                                                             "sources": sources}, indent=2), encoding="utf-8")

    engine = BacktestEngine(prices, config)
    strategies = {
        "Benevente Quant AI": engine.run(macro_data=macro, use_signals=True),
        "MVO clássico": engine.run(macro_data=macro, use_signals=False),
    }
    dates = strategies["Benevente Quant AI"]["date"]
    strategies["CDI"] = passive_results(prices["TITULO_CDI"], dates, config.rebalance_days)
    strategies["Ibovespa"] = passive_results(ibovespa.reindex(prices.index).ffill(), dates, config.rebalance_days)

    metrics_rows = []
    curves = pd.DataFrame(index=dates)
    cdi_period_returns = strategies["CDI"].set_index("date")["net_return"]
    for name, result in strategies.items():
        result.to_csv(output / f"results_{name.lower().replace(' ', '_')}.csv", index=False)
        row = {"strategy": name, **engine.metrics(result, 0.0)}
        excess = result.set_index("date")["net_return"] - cdi_period_returns
        # The research table defines Sharpe consistently as periodic excess return over realised CDI.
        row["sharpe_excess_cdi"] = float(excess.mean() / (excess.std(ddof=1) + 1e-12) * (12 ** 0.5)) if name != "CDI" else float("nan")
        row["sharpe"] = row["sharpe_excess_cdi"]
        metrics_rows.append(row)
        curves[name] = result.set_index("date")["wealth"]
    metrics = pd.DataFrame(metrics_rows).set_index("strategy")
    metrics.to_csv(output / "performance_metrics.csv")
    curves.to_csv(output / "equity_curves.csv")

    ax = curves.plot(figsize=(11, 5), linewidth=2)
    ax.set(title="Benevente Quant AI — Real-data comparison (net returns)", xlabel="Rebalance date", ylabel="Wealth (base 100)")
    ax.grid(alpha=0.25)
    plt.tight_layout(); plt.savefig(output / "performance_comparison.png", dpi=220); plt.close()

    # Sensitivity: execution-cost assumption is a model parameter, not observed cost.
    sensitivity = []
    for cost_bps in (0, 10, 20):
        scenario = replace(config, transaction_cost=cost_bps / 10_000)
        result = BacktestEngine(prices, scenario).run(macro_data=macro, use_signals=True)
        sensitivity.append({"transaction_cost_bps": cost_bps, **BacktestEngine.metrics(result, scenario.risk_free_rate_annual)})
    pd.DataFrame(sensitivity).to_csv(output / "cost_sensitivity.csv", index=False)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Benevente Quant AI with audit artifacts.")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2026-07-01", help="Exclusive end date for yfinance/BCB requests.")
    parser.add_argument("--output", default="artifacts/real_data")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    metrics = evaluate(SystemConfig(), args.start, args.end, Path(args.output), args.offline)
    print(metrics.to_string(float_format=lambda value: f"{value:.4f}"))


if __name__ == "__main__":
    main()
