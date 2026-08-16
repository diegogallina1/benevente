"""Assemble the published run from whichever configuration each year selected.

The nested search decides the configuration for year *t* using only years that
had already closed. The resulting track record is therefore a stitch: 2018 came
from one configuration, 2019 to 2021 from another, and so on. This module builds
the artifacts the site and the paper need from that stitch — annual results,
holdings, transitions and the exact daily value path — instead of publishing any
single configuration's full-sample curve, which nobody could have chosen in
advance.

Switching configurations is a real trade, so the switching cost the search
charged is carried into the daily path on the first session of the year it
happens.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def stitch_annual(selection: pd.DataFrame, runs: dict[str, Path]) -> pd.DataFrame:
    """Take each year's row from the configuration that was chosen for it."""
    rows: list[pd.Series] = []
    for item in selection.itertuples(index=False):
        annual = pd.read_csv(runs[item.selected_configuration] / "annual_results.csv").set_index("decision_year")
        if item.decision_year not in annual.index:
            raise KeyError(f"{item.selected_configuration} has no year {item.decision_year}")
        row = annual.loc[item.decision_year].copy()
        row["decision_year"] = int(item.decision_year)
        row["selected_configuration"] = item.selected_configuration
        row["switching_cost"] = float(item.switching_cost)
        # The published return is net of the cost of leaving last year's book.
        row["gross_of_switch_return"] = float(row["net_return"])
        row["net_return"] = float(row["net_return"]) - float(item.switching_cost)
        rows.append(row)
    stitched = pd.DataFrame(rows).reset_index(drop=True)
    ordered = ["decision_year", *[column for column in stitched.columns if column != "decision_year"]]
    return stitched[ordered]


def stitch_frame(selection: pd.DataFrame, runs: dict[str, Path], filename: str) -> pd.DataFrame:
    """Concatenate a per-year artifact from the configuration chosen that year."""
    parts: list[pd.DataFrame] = []
    for item in selection.itertuples(index=False):
        path = runs[item.selected_configuration] / filename
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if "decision_year" not in frame.columns:
            continue
        part = frame[frame.decision_year.eq(item.decision_year)].copy()
        part["selected_configuration"] = item.selected_configuration
        parts.append(part)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def stitch_daily(selection: pd.DataFrame, runs: dict[str, Path]) -> pd.DataFrame:
    """Chain each year's exact daily path onto the previous year's closing level."""
    level = {"strategy": 100.0, "mvo": 100.0, "cdi": 100.0}
    benchmark_level: dict[str, float] = {}
    output: list[pd.DataFrame] = []
    for item in selection.itertuples(index=False):
        path = runs[item.selected_configuration] / "daily_curve.csv"
        if not path.exists():
            continue
        daily = pd.read_csv(path, parse_dates=["date"])
        year = daily[daily.decision_year.eq(item.decision_year)].copy()
        if year.empty:
            continue
        # The first stored row is already one session into the year, because a
        # return needs two prices. Rebasing on it would silently discard the
        # first session of every year. The correct base is the run's own level
        # at the close of the previous year, or 100 for the run's first year.
        earlier = daily[daily.decision_year.lt(item.decision_year)]
        base = earlier.iloc[-1] if not earlier.empty else None
        for column in ("strategy", "mvo", "cdi"):
            opening = float(base[column]) if base is not None else 100.0
            year[column] = year[column] / opening * level[column]
        for column in year.columns:
            if column in {"date", "decision_year", "strategy", "mvo", "cdi", "selected_configuration"}:
                continue
            opening = float(base[column]) if base is not None and column in base.index else 100.0
            start = benchmark_level.setdefault(column, 100.0)
            year[column] = year[column] / opening * start
        if item.switching_cost:
            year["strategy"] = year["strategy"] * (1 - float(item.switching_cost))
        year["selected_configuration"] = item.selected_configuration
        output.append(year)
        level["strategy"] = float(year["strategy"].iloc[-1])
        level["mvo"] = float(year["mvo"].iloc[-1])
        level["cdi"] = float(year["cdi"].iloc[-1])
        for column in benchmark_level:
            if column in year.columns:
                benchmark_level[column] = float(year[column].iloc[-1])
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the published artifacts of the nested configuration series.")
    parser.add_argument("--selection", default="artifacts/configuration_search/nested_selection_annual.csv")
    parser.add_argument("--runs-root", default="artifacts")
    parser.add_argument("--run-prefix", default="cfg_")
    parser.add_argument("--output", default="artifacts/published_nested")
    args = parser.parse_args()

    selection = pd.read_csv(args.selection)
    root = Path(args.runs_root)
    runs = {name: root / f"{args.run_prefix}{name}" for name in selection.selected_configuration.unique()}
    missing = [str(path) for path in runs.values() if not (path / "annual_results.csv").exists()]
    if missing:
        raise SystemExit(f"Missing configuration runs: {missing}")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    annual = stitch_annual(selection, runs)
    annual.to_csv(output / "annual_results.csv", index=False)
    for filename in ("annual_holdings.csv", "annual_transitions.csv"):
        frame = stitch_frame(selection, runs, filename)
        if not frame.empty:
            frame.to_csv(output / filename, index=False)
    daily = stitch_daily(selection, runs)
    if not daily.empty:
        daily.to_csv(output / "daily_curve.csv", index=False)
    protocol = {
        "factor": "nested_configuration_selection",
        "start_year": int(annual.decision_year.min()),
        "end_year": int(annual.decision_year.max()) + 1,
        "selection_rule": ("For decision year t the configuration is ranked on years before t only, by Sharpe of the "
                           "excess return over CDI. Switching configurations is charged a full-turnover rebalance."),
        "configurations_by_year": {int(row.decision_year): row.selected_configuration for row in selection.itertuples(index=False)},
        "live_configuration": str(selection.selected_configuration.iloc[-1]),
        "in_sample_status": ("The window that ranked the configurations cannot also test them. Evaluation of this rule "
                             "begins with years after the frozen registration."),
    }
    (output / "protocol.json").write_text(json.dumps(protocol, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"years": int(len(annual)), "daily_points": int(len(daily)),
                      "live_configuration": protocol["live_configuration"]}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
