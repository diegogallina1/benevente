"""Pre-registered grid research for annual Benevente candidate rules.

Candidates are scored only on 2015--2020.  The 2021--2025 result is exported
separately and is never used to choose a candidate.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import AnnualWalkForwardConfig, AnnualWalkForwardEngine
from config import SystemConfig
from total_return_adapter import load_total_return_export


ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "research_grid_20260813"


def metrics(frame: pd.DataFrame) -> dict[str, float]:
    def annual(column: str) -> tuple[float, float]:
        wealth = float((1 + frame[column]).prod())
        return wealth ** (1 / len(frame)) - 1, wealth - 1

    candidate_cagr, candidate_total = annual("net_return")
    mvo_cagr, _ = annual("mvo_eligible_net_return")
    cdi_cagr, _ = annual("cdi_net_return")
    wealth = (1 + frame.net_return).cumprod()
    return {
        "years": len(frame), "candidate_cagr": candidate_cagr,
        "candidate_total": candidate_total, "mvo_cagr": mvo_cagr,
        "cdi_cagr": cdi_cagr, "excess_mvo_cagr": candidate_cagr - mvo_cagr,
        "excess_cdi_cagr": candidate_cagr - cdi_cagr,
        "worst_annual_return": float(frame.net_return.min()),
        "negative_years": int((frame.net_return < 0).sum()),
        "average_turnover": float(frame.turnover.mean()),
        "max_drawdown_annual": float((wealth / wealth.cummax() - 1).min()),
    }


def selection_score(row: dict[str, float]) -> float:
    """Declared train-only objective: alpha, drawdown and turnover."""
    return row["excess_mvo_cagr"] + row["excess_cdi_cagr"] - .35 * abs(row["max_drawdown_annual"]) - .05 * row["average_turnover"]


def candidates() -> list[dict[str, object]]:
    grid: list[dict[str, object]] = []
    for factor in ("value_quality", "triple_factor", "momentum_12m", "low_volatility"):
        for equity in (.35, .55, .80, 1.00):
            grid.append({"name": f"{factor}_eq{int(equity * 100)}", "factor": factor,
                         "equity_cap": equity, "asset_cap": .10, "top_assets": 10})
    for top_assets, asset_cap in ((8, .125), (10, .10), (12, 1 / 12)):
        grid.append({"name": f"triple_diversified_{top_assets}", "factor": "triple_factor",
                     "equity_cap": 1.00, "asset_cap": asset_cap, "top_assets": top_assets})
    return grid


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
    for candidate in candidates():
        for split, start, end in (("train", 2015, 2021), ("holdout", 2021, 2026)):
            protocol = AnnualWalkForwardConfig(start, end, factor=str(candidate["factor"]),
                                                maximum_equity_weight=float(candidate["equity_cap"]),
                                                maximum_asset_weight=float(candidate["asset_cap"]),
                                                top_assets=int(candidate["top_assets"]))
            result, _, holdings = engine.run(protocol)
            result.to_csv(OUT / f"{candidate['name']}_{split}_annual.csv", index=False)
            holdings.to_csv(OUT / f"{candidate['name']}_{split}_holdings.csv", index=False)
            row = {**candidate, "split": split, **metrics(result)}
            rows.append(row)
    report = pd.DataFrame(rows)
    train = report.loc[report.split.eq("train")].copy()
    train["selection_score"] = train.apply(selection_score, axis=1)
    report = report.merge(train[["name", "selection_score"]], on="name", how="left")
    report.to_csv(OUT / "grid_summary.csv", index=False)
    winner = train.sort_values(["selection_score", "candidate_cagr"], ascending=False).iloc[0].to_dict()
    holdout = report[(report.name == winner["name"]) & report.split.eq("holdout")].iloc[0].to_dict()
    conclusion = {
        "selection_period": "2015-2020", "holdout_period": "2021-2025",
        "winner_selected_on_train_only": winner, "winner_holdout": holdout,
        "passes_cdi_and_mvo_holdout": bool(holdout["excess_cdi_cagr"] > 0 and holdout["excess_mvo_cagr"] > 0),
        "rule": "Reject a candidate if it does not exceed both CDI and the comparable MVO in the holdout.",
    }
    (OUT / "selection_conclusion.json").write_text(json.dumps(conclusion, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    print(report.to_string(index=False))
    print(json.dumps(conclusion, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    main()
