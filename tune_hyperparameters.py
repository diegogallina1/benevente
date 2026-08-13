"""Time-split hyperparameter selection for Benevente Quant AI.

Selection uses only rebalance periods before ``--split``. The selected setting
is then evaluated only on rows on/after that date; no holdout observation is
used to choose parameters.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
import pandas as pd

from backtest_engine import BacktestEngine
from config import SystemConfig
from model_validation import (CommercialReadinessGate, SelectionGate, commercial_readiness,
                              excess_sharpe, passes_selection_gate)
from research_runner import passive_results


def rebase(results: pd.DataFrame, base_wealth: float = 100.0) -> pd.DataFrame:
    """Make a standalone period whose wealth starts at ``base_wealth``."""
    standalone = results.copy()
    standalone["wealth"] = base_wealth * (1 + standalone["net_return"]).cumprod()
    return standalone


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="artifacts/real_data")
    parser.add_argument("--split", default="2025-01-01", help="First out-of-sample rebalance date.")
    args = parser.parse_args()
    directory = Path(args.input)
    metadata = json.loads((directory / "run_metadata.json").read_text(encoding="utf-8"))
    config = SystemConfig(**metadata["config"])
    prices = pd.read_csv(directory / "input_prices.csv", index_col=0, parse_dates=True)
    macro = pd.read_csv(directory / "input_macro.csv", index_col=0, parse_dates=True)
    engine = BacktestEngine(prices, config)
    baseline = engine.run(macro_data=macro, use_signals=True)
    cdi = passive_results(prices["TITULO_CDI"], baseline.date, config.rebalance_days)

    rows = []
    gate = SelectionGate()
    for gamma in (1.0, 2.5, 5.0):
        for alpha in (0.10, 0.30, 0.50):
            candidate = replace(config, risk_aversion_gamma=gamma, signal_alpha_influence=alpha)
            result = BacktestEngine(prices, candidate).run(macro_data=macro, use_signals=True)
            train = result[result.date < pd.Timestamp(args.split)]
            train_cdi = cdi[cdi.date < pd.Timestamp(args.split)]
            passed, evidence = passes_selection_gate(train, train_cdi, gate)
            rows.append({"gamma": gamma, "alpha": alpha, "eligible_for_holdout": passed,
                         "train_cagr": BacktestEngine.metrics(train, 0.0)["cagr"], **evidence})
    search = pd.DataFrame(rows).sort_values(["eligible_for_holdout", "training_sharpe_excess_cdi"], ascending=False)
    search.to_csv(directory / "hyperparameter_search.csv", index=False)
    qualified = search.loc[search.eligible_for_holdout]
    # If no candidate clears the gate, keep the pre-registered baseline.  We do
    # not tune a model merely because one historical parameter looked least bad.
    best = qualified.iloc[0] if not qualified.empty else None
    selected = (replace(config, risk_aversion_gamma=float(best.gamma), signal_alpha_influence=float(best.alpha))
                if best is not None else config)
    selected_result = BacktestEngine(prices, selected).run(macro_data=macro, use_signals=True)
    holdout = rebase(selected_result[selected_result.date >= pd.Timestamp(args.split)])
    holdout_cdi = rebase(cdi[cdi.date >= pd.Timestamp(args.split)])
    mvo_result = engine.run(macro_data=macro, use_signals=False)
    holdout_mvo = rebase(mvo_result[mvo_result.date >= pd.Timestamp(args.split)])
    holdout_metrics = BacktestEngine.metrics(holdout, 0.0)
    holdout_metrics.update({"gamma": float(best.gamma) if best is not None else float(config.risk_aversion_gamma),
                            "alpha": float(best.alpha) if best is not None else float(config.signal_alpha_influence),
                            "selection_status": "tuned_candidate" if best is not None else "baseline_retained_no_candidate_passed_training_gate",
                            "split": args.split, "periods": len(holdout), "sharpe_excess_cdi": excess_sharpe(holdout, holdout_cdi)})
    holdout_metrics["sharpe"] = holdout_metrics["sharpe_excess_cdi"]
    approved, readiness = commercial_readiness(holdout, holdout_cdi, holdout_mvo, CommercialReadinessGate())
    holdout_metrics.update(readiness)
    holdout_metrics["approved_for_commercial_alpha_claim"] = approved
    (directory / "holdout_metrics.json").write_text(json.dumps(holdout_metrics, indent=2), encoding="utf-8")
    holdout.to_csv(directory / "results_tuned_holdout.csv", index=False)
    print(search.to_string(index=False, float_format=lambda value: f"{value:.4f}"))
    print(json.dumps(holdout_metrics, indent=2))


if __name__ == "__main__":
    main()
