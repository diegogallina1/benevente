"""Rolling-origin validation for pre-specified conservative candidates."""
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
OUT = ROOT / "artifacts" / "rolling_validation_20260813"


def metrics(frame: pd.DataFrame) -> dict[str, float | int]:
    def calc(column: str) -> float:
        return float((1 + frame[column]).prod()) ** (1 / len(frame)) - 1
    return {
        "years": len(frame), "cagr": calc("net_return"), "mvo_cagr": calc("mvo_eligible_net_return"),
        "cdi_cagr": calc("cdi_net_return"), "excess_mvo": calc("net_return") - calc("mvo_eligible_net_return"),
        "excess_cdi": calc("net_return") - calc("cdi_net_return"),
        "both_year_hit_rate": float(((frame.net_return > frame.mvo_eligible_net_return) & (frame.net_return > frame.cdi_net_return)).mean()),
        "worst_year": float(frame.net_return.min()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices, _ = load_total_return_export(ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv", ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    fundamentals = pd.read_csv(ROOT / "data/fundamentals_b3_cvm_full_2013_2025.csv", parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(ROOT / "data/b3_historical_universes.csv", ROOT / "data/b3_historical_cvm_ticker_map.csv")
    engine = AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals), SystemConfig(), evidence)
    candidates = {
        "low_vol_eq15_asset10": (.15, .10, 5),
        "low_vol_eq25_asset10": (.25, .10, 5),
        "low_vol_eq35_asset10": (.35, .10, 5),
        "low_vol_eq15_asset05": (.15, .05, 5),
    }
    rows: list[dict[str, object]] = []
    # Three independent 3-year end blocks, overlapping only in training,
    # expose regime dependence without re-tuning the candidate in each block.
    for name, (equity, asset, top) in candidates.items():
        for start, end in ((2015, 2018), (2018, 2021), (2021, 2024)):
            cfg = AnnualWalkForwardConfig(start, end, factor="low_volatility", maximum_equity_weight=equity,
                                           maximum_asset_weight=asset, top_assets=top)
            annual, _, _ = engine.run(cfg)
            annual.to_csv(OUT / f"{name}_{start}_{end-1}.csv", index=False)
            rows.append({"candidate": name, "start": start, "end": end - 1, **metrics(annual)})
    report = pd.DataFrame(rows)
    report.to_csv(OUT / "rolling_summary.csv", index=False)
    stability = report.groupby("candidate").agg(
        windows=("start", "count"),
        median_excess_mvo=("excess_mvo", "median"),
        median_excess_cdi=("excess_cdi", "median"),
        minimum_excess_cdi=("excess_cdi", "min"),
        minimum_excess_mvo=("excess_mvo", "min"),
    ).reset_index()
    pass_counts = report.assign(passes=(report.excess_cdi > 0) & (report.excess_mvo > 0)).groupby("candidate").passes.sum()
    stability["pass_both"] = stability.candidate.map(pass_counts).astype(int)
    stability.to_csv(OUT / "stability.csv", index=False)
    print(report.to_string(index=False)); print(stability.to_string(index=False))
    (OUT / "conclusion.json").write_text(json.dumps({"candidates": candidates, "stability": stability.to_dict(orient="records")}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
