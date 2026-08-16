"""Nested yearly choice of factor and equity exposure without look-ahead."""
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
OUT = ROOT / "artifacts" / "adaptive_policy_20260813"
FACTORS = ("value_quality", "triple_factor", "momentum_12m", "low_volatility")
EQUITY_CAPS = (.35, .55, .80, 1.00)


def run_metrics(frame: pd.DataFrame) -> dict[str, float]:
    wealth = float((1 + frame.net_return).prod())
    return {"cagr": wealth ** (1 / len(frame)) - 1, "total": wealth - 1,
            "drawdown": float(((1 + frame.net_return).cumprod().div((1 + frame.net_return).cumprod().cummax()) - 1).min()),
            "turnover": float(frame.turnover.mean())}


def selection_score(frame: pd.DataFrame) -> float:
    metric = run_metrics(frame)
    mvo = float((1 + frame.mvo_eligible_net_return).prod()) ** (1 / len(frame)) - 1
    cdi = float((1 + frame.cdi_net_return).prod()) ** (1 / len(frame)) - 1
    return (metric["cagr"] - mvo) + (metric["cagr"] - cdi) - .35 * abs(metric["drawdown"]) - .05 * metric["turnover"]


def annual_result(engine: AnnualWalkForwardEngine, start: int, end: int, factor: str, cap: float) -> pd.DataFrame:
    protocol = AnnualWalkForwardConfig(start, end, factor=factor, maximum_equity_weight=cap,
                                       maximum_asset_weight=.10, top_assets=10)
    return engine.run(protocol)[0]


def evaluate(engine: AnnualWalkForwardEngine, start: int, end: int, selection_start: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    decisions = []
    yearly = []
    selection_start = start if selection_start is None else selection_start
    # Three decisions are required before selecting a regime. Before that, a
    # fixed conservative baseline prevents a fabricated training winner.
    for year in range(start, end):
        candidates = []
        if year - selection_start < 3:
            chosen = ("value_quality", .35, "baseline_before_three_observations")
        else:
            for factor in FACTORS:
                for cap in EQUITY_CAPS:
                    history = annual_result(engine, selection_start, year, factor, cap)
                    candidates.append({"factor": factor, "equity_cap": cap, "score": selection_score(history)})
            board = pd.DataFrame(candidates).sort_values(["score", "equity_cap"], ascending=[False, True])
            best = board.iloc[0]
            chosen = (str(best.factor), float(best.equity_cap), "selected_from_prior_decisions")
        result = annual_result(engine, year, year + 1, chosen[0], chosen[1])
        yearly.append(result)
        decisions.append({"decision_year": year, "factor": chosen[0], "equity_cap": chosen[1], "status": chosen[2]})
    return pd.concat(yearly, ignore_index=True), pd.DataFrame(decisions)


def summary(frame: pd.DataFrame) -> dict[str, float]:
    def calc(column: str) -> float:
        return float((1 + frame[column]).prod()) ** (1 / len(frame)) - 1
    return {"cagr": calc("net_return"), "mvo_cagr": calc("mvo_eligible_net_return"), "cdi_cagr": calc("cdi_net_return"),
            "excess_mvo": calc("net_return") - calc("mvo_eligible_net_return"),
            "excess_cdi": calc("net_return") - calc("cdi_net_return"),
            "worst_year": float(frame.net_return.min()), "negative_years": int((frame.net_return < 0).sum()),
            "average_turnover": float(frame.turnover.mean())}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    prices, _ = load_total_return_export(ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv", ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    fundamentals = pd.read_csv(ROOT / "data/fundamentals_b3_cvm_full_2013_2025.csv", parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(ROOT / "data/b3_historical_universes.csv", ROOT / "data/b3_historical_cvm_ticker_map.csv")
    engine = AnnualWalkForwardEngine(prices.set_index("date"), snapshots_from_frame(fundamentals), SystemConfig(), evidence)
    train, train_choices = evaluate(engine, 2015, 2021)
    # The 2021 choice may use 2015--2020 outcomes, but never 2021--2025
    # outcomes. Later holdout choices gain only the years already realised.
    holdout, holdout_choices = evaluate(engine, 2021, 2026, selection_start=2015)
    train.to_csv(OUT / "train_annual.csv", index=False); holdout.to_csv(OUT / "holdout_annual.csv", index=False)
    train_choices.to_csv(OUT / "train_choices.csv", index=False); holdout_choices.to_csv(OUT / "holdout_choices.csv", index=False)
    result = {"train": summary(train), "holdout": summary(holdout),
              "passes_holdout": bool(summary(holdout)["excess_mvo"] > 0 and summary(holdout)["excess_cdi"] > 0),
              "rule": "At each January, factor and equity cap are selected using prior decisions only."}
    (OUT / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2)); print(holdout_choices.to_string(index=False))


if __name__ == "__main__":
    main()
