from __future__ import annotations
import argparse
import json
from pathlib import Path
import matplotlib
# The command is expected to run in CI and servers without a desktop session.
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from backtest_engine import BacktestEngine
from config import SystemConfig
from data_loader import PointInTimeDataLoader


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Benevente Quant AI reproducible backtest.")
    parser.add_argument("--offline", action="store_true", help="Use deterministic synthetic market data.")
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2026-06-30")
    parser.add_argument("--output", default="artifacts")
    args = parser.parse_args()
    config, output = SystemConfig(), Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    prices = PointInTimeDataLoader(config).fetch_prices(args.start, args.end, offline=args.offline)
    engine = BacktestEngine(prices, config)
    results = engine.run()
    metrics = engine.metrics(results, config.risk_free_rate_annual)
    results.to_csv(output / "backtest_results.csv", index=False)
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    plt.style.use("seaborn-v0_8-whitegrid")
    ax = results.plot(x="date", y="wealth", legend=False, figsize=(10, 5), color="#166534", linewidth=2)
    ax.axhline(config.initial_wealth, color="gray", linestyle="--", linewidth=1)
    ax.set(title="Benevente Quant AI: Equity Curve (net of modelled frictions)", xlabel="Date", ylabel="Wealth")
    plt.tight_layout(); plt.savefig(output / "equity_curve.png", dpi=200); plt.close()
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
