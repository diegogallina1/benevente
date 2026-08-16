"""Exploratory robustness tests for the low-volatility signal.

This script is deliberately separate from candidate selection.  It varies only
portfolio guardrails and evaluates every decision with information available at
that January.  Results are for rejection and stability analysis, not for
choosing a production rule after observing the last period.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import AnnualWalkForwardConfig, AnnualWalkForwardEngine
from config import SystemConfig
from total_return_adapter import load_total_return_export


ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "low_volatility_robustness_20260813"


def cagr(frame: pd.DataFrame, column: str) -> float:
    return float((1 + frame[column]).prod()) ** (1 / len(frame)) - 1


def describe(frame: pd.DataFrame) -> dict[str, float | int]:
    equity = frame.target_equity_weight
    candidate = cagr(frame, "net_return")
    mvo = cagr(frame, "mvo_eligible_net_return")
    cdi = cagr(frame, "cdi_net_return")
    relative_mvo = (1 + frame.net_return).cumprod() / (1 + frame.mvo_eligible_net_return).cumprod()
    relative_cdi = (1 + frame.net_return).cumprod() / (1 + frame.cdi_net_return).cumprod()
    return {
        "years": len(frame), "cagr": candidate, "mvo_cagr": mvo, "cdi_cagr": cdi,
        "excess_mvo_cagr": candidate - mvo, "excess_cdi_cagr": candidate - cdi,
        "annual_both_hit_rate": float(((frame.net_return > frame.mvo_eligible_net_return) &
                                         (frame.net_return > frame.cdi_net_return)).mean()),
        "worst_year": float(frame.net_return.min()),
        "relative_mvo_drawdown": float((relative_mvo / relative_mvo.cummax() - 1).min()),
        "relative_cdi_drawdown": float((relative_cdi / relative_cdi.cummax() - 1).min()),
        "average_equity_weight": float(equity.mean()), "average_turnover": float(frame.turnover.mean()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices, _ = load_total_return_export(
        ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv",
        ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json",
    )
    fundamentals = pd.read_csv(ROOT / "data/fundamentals_b3_cvm_full_2013_2025.csv",
                               parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(ROOT / "data/b3_historical_universes.csv",
                                         ROOT / "data/b3_historical_cvm_ticker_map.csv")
    engine = AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals), SystemConfig(), evidence)
    rows: list[dict[str, object]] = []
    # The grid stresses allocation and concentration around the observed
    # low-volatility signal.  It intentionally does not tune factor weights.
    # Compact, meaningful stress grid: the 5% cap tests wider diversification;
    # 10% recovers the original candidate; the combinations span 15–45% equity.
    for equity_cap in (.15, .25, .35, .45):
        for asset_cap in (.05, .10):
            for top_assets in (5, 10):
                name = f"lv_eq{int(equity_cap*100)}_cap{int(asset_cap*1000):03d}_top{top_assets}"
                for split, start, end in (("train", 2015, 2021), ("holdout", 2021, 2026)):
                    cfg = AnnualWalkForwardConfig(start, end, factor="low_volatility",
                                                   maximum_equity_weight=equity_cap,
                                                   maximum_asset_weight=asset_cap,
                                                   top_assets=top_assets)
                    annual, _, holdings = engine.run(cfg)
                    annual.to_csv(OUT / f"{name}_{split}_annual.csv", index=False)
                    holdings.to_csv(OUT / f"{name}_{split}_holdings.csv", index=False)
                    rows.append({"name": name, "equity_cap": equity_cap, "asset_cap": asset_cap,
                                 "top_assets": top_assets, "split": split, **describe(annual)})
    report = pd.DataFrame(rows)
    report.to_csv(OUT / "summary.csv", index=False)
    train = report[report.split.eq("train")].set_index("name")
    holdout = report[report.split.eq("holdout")].set_index("name")
    combined = train.add_prefix("train_").join(holdout.add_prefix("holdout_"))
    combined["passes_both_blocks"] = ((combined.train_excess_mvo_cagr > 0) &
                                       (combined.train_excess_cdi_cagr > 0) &
                                       (combined.holdout_excess_mvo_cagr > 0) &
                                       (combined.holdout_excess_cdi_cagr > 0))
    combined["robustness_score"] = (combined.train_excess_mvo_cagr.clip(lower=0) +
                                    combined.train_excess_cdi_cagr.clip(lower=0) +
                                    combined.holdout_excess_mvo_cagr.clip(lower=0) +
                                    combined.holdout_excess_cdi_cagr.clip(lower=0) -
                                    .25 * (combined.train_relative_cdi_drawdown.abs() +
                                           combined.holdout_relative_cdi_drawdown.abs()) -
                                    .05 * (combined.train_average_turnover + combined.holdout_average_turnover))
    combined.sort_values(["passes_both_blocks", "robustness_score"], ascending=False).to_csv(OUT / "combined.csv")
    conclusion = {
        "purpose": "exploratory guardrail robustness, not post-hoc production selection",
        "number_of_rules": int(len(combined)),
        "both_blocks_pass_count": int(combined.passes_both_blocks.sum()),
        "best_rows": combined.sort_values(["passes_both_blocks", "robustness_score"], ascending=False).head(10).reset_index().to_dict(orient="records"),
    }
    (OUT / "conclusion.json").write_text(json.dumps(conclusion, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(conclusion, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
