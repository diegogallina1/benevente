"""Pre-registered annual strategy comparison with one frozen holdout.

This script does not search parameters after observing 2021--2024.  It runs a
small, declared family of economically interpretable signals on the same
point-in-time B3/CVM universe, selects at most one candidate using 2015--2020,
and reports that frozen candidate separately on the later years.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path

import pandas as pd

from advisor import snapshots_from_frame
from annual_walk_forward import AnnualWalkForwardConfig, AnnualWalkForwardEngine
from config import SystemConfig
from model_validation import AnnualHoldoutGate, annual_holdout_readiness
from total_return_adapter import institutional_performance_verified, load_total_return_export


# These are deliberately few and are not expanded after seeing the holdout.
CANDIDATES = ("value_quality", "momentum_12m", "low_volatility", "triple_factor")


def _metrics(rows: pd.DataFrame) -> dict[str, float]:
    wealth = (1 + rows.net_return).prod()
    cdi = (1 + rows.cdi_net_return).prod()
    mvo = (1 + rows.mvo_eligible_net_return).prod()
    path = (1 + rows.net_return).cumprod()
    return {
        "years": float(len(rows)),
        "cumulative_return": float(wealth - 1),
        "cumulative_excess_vs_cdi": float(wealth / cdi - 1),
        "cumulative_excess_vs_mvo": float(wealth / mvo - 1),
        "max_drawdown": float((path / path.cummax() - 1).min()),
        "average_turnover": float(rows.turnover.mean()),
    }


def choose_from_training(candidate_results: dict[str, pd.DataFrame], split_year: int) -> tuple[str, pd.DataFrame]:
    """Select only from pre-split years; retain the baseline if none qualify."""
    rows: list[dict[str, float | str | bool]] = []
    for name, result in candidate_results.items():
        train = result[result.decision_year < split_year].copy()
        metrics = _metrics(train)
        eligible = bool(
            metrics["years"] >= 5
            and metrics["cumulative_excess_vs_cdi"] > 0
            and metrics["cumulative_excess_vs_mvo"] > 0
            and metrics["max_drawdown"] >= -.35
        )
        # Deterministic selection criterion defined before the holdout.  It
        # rewards net excess against both references while penalising turnover.
        selection_score = metrics["cumulative_excess_vs_cdi"] + metrics["cumulative_excess_vs_mvo"] - .10 * metrics["average_turnover"]
        rows.append({"candidate": name, "eligible_for_holdout": eligible,
                     "training_selection_score": selection_score, **{f"train_{key}": value for key, value in metrics.items()}})
    leaderboard = pd.DataFrame(rows).sort_values(
        ["eligible_for_holdout", "training_selection_score", "candidate"], ascending=[False, False, True]
    ).reset_index(drop=True)
    qualified = leaderboard[leaderboard.eligible_for_holdout]
    return (str(qualified.iloc[0].candidate) if not qualified.empty else "value_quality"), leaderboard


def run_experiment(prices: pd.DataFrame, snapshots, split_year: int,
                   protocol: AnnualWalkForwardConfig,
                   input_performance_permitted: bool = False) -> tuple[dict[str, pd.DataFrame], str, pd.DataFrame, dict]:
    engine = AnnualWalkForwardEngine(prices, snapshots, SystemConfig())
    candidate_results: dict[str, pd.DataFrame] = {}
    for factor in CANDIDATES:
        candidate_results[factor], _, _ = engine.run(replace(protocol, factor=factor))
    selected, leaderboard = choose_from_training(candidate_results, split_year)
    approved, holdout = annual_holdout_readiness(
        candidate_results[selected], split_year, input_performance_permitted, AnnualHoldoutGate()
    )
    holdout["candidate"] = selected
    holdout["status"] = "approved" if approved else "research_only"
    return candidate_results, selected, leaderboard, holdout


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a pre-registered annual candidate using only a training period.")
    parser.add_argument("--prices", required=True)
    parser.add_argument("--total-return-manifest", required=True)
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--split-year", type=int, default=2021)
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    parser.add_argument("--maximum-equity-weight", type=float, default=.55)
    parser.add_argument("--maximum-asset-weight", type=float, default=.12)
    parser.add_argument("--top-assets", type=int, default=4)
    parser.add_argument("--output", default="artifacts/yahoo_candidate_experiment")
    args = parser.parse_args()
    price_frame, return_manifest = load_total_return_export(args.prices, args.total_return_manifest)
    snapshots = snapshots_from_frame(pd.read_csv(args.fundamentals, parse_dates=["as_of_date", "available_date"]))
    protocol = AnnualWalkForwardConfig(args.start_year, args.end_year,
                                       maximum_equity_weight=args.maximum_equity_weight,
                                       maximum_asset_weight=args.maximum_asset_weight,
                                       top_assets=args.top_assets)
    source_verified = institutional_performance_verified(return_manifest)
    results, selected, leaderboard, holdout = run_experiment(
        price_frame.set_index("date"), snapshots, args.split_year, protocol, source_verified
    )
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    leaderboard.to_csv(output / "candidate_training_leaderboard.csv", index=False)
    for name, frame in results.items():
        frame.to_csv(output / f"{name}_annual_results.csv", index=False)
    selected_result = results[selected]
    selected_result.to_csv(output / "selected_candidate_annual_results.csv", index=False)
    holdout["total_return_source_tier"] = return_manifest.get("source_tier", "unclassified")
    holdout["institutional_performance_verified"] = source_verified
    (output / "selected_candidate_holdout.json").write_text(json.dumps(holdout, indent=2, ensure_ascii=False), encoding="utf-8")
    (output / "experiment_protocol.json").write_text(json.dumps({
        "candidates": CANDIDATES, "split_year": args.split_year,
        "selection_data": f"decision years < {args.split_year}",
        "holdout_data": f"decision years >= {args.split_year}",
        "selection_rule": "positive net cumulative excess versus CDI and eligible MVO; drawdown >= -35%; then score net excesses minus turnover penalty",
        "source_tier": return_manifest.get("source_tier", "unclassified"),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"selected_candidate": selected, "holdout": holdout}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
