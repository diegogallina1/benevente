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
import re
from pathlib import Path

import pandas as pd

from annual_walk_forward import BrazilianTaxModel, apply_annual_taxes

# Written by apply_annual_taxes; dropped before recomputing so a stale copy from
# a single configuration's run can never survive into the published series.
_TAX_OUTPUT_COLUMNS = [
    "realised_share_for_tax", "tax_rate", "net_return_after_tax",
    "mvo_realised_share_for_tax", "mvo_tax_rate", "mvo_net_return_after_tax",
    "cdi_net_return_after_tax",
]


def _configuration_limits(name: str) -> dict:
    """Recover the policy limits encoded in a configuration name.

    Names look like ``eq55_n5_triple_factor``: equity budget, holding count and
    signal. The issuer ceiling is derived from the first two by the same rule
    the search used, so the published protocol always agrees with the run.
    """
    from research_configuration_search import ISSUER_CAP_SLACK, MAXIMUM_ISSUER_CAP

    match = re.match(r"eq(\d+)_n(\d+)_(.+)", name)
    if not match:
        return {}
    equity = int(match.group(1)) / 100
    count = int(match.group(2))
    return {
        "maximum_equity_weight": round(equity, 6),
        "top_assets": count,
        "maximum_asset_weight": round(min(MAXIMUM_ISSUER_CAP, equity / count * ISSUER_CAP_SLACK), 6),
        "signal": match.group(3),
    }


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
    # Tax has to be recomputed on the stitched sequence, not copied from each
    # run. Every configuration's own after-tax column assumes the investor
    # stayed in it for the whole window; the published track switches five
    # times, and a switch realises gains that the copied column never charges.
    # Recomputing here also makes the after-tax series pay the switching cost,
    # which the pre-tax series already paid two lines above.
    stitched = apply_annual_taxes(stitched.drop(columns=_TAX_OUTPUT_COLUMNS, errors="ignore"),
                                  BrazilianTaxModel())
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


def prepend_selection_window(daily: pd.DataFrame, live_run: Path, first_year: int) -> pd.DataFrame:
    """Carry the years that chose the configuration, marked as what they are.

    A chart that starts in the first evaluated year hides the window the search
    ranged over, and a reader reasonably asks what happened before. Splicing the
    live configuration's own curve onto the front answers that — but those years
    cannot be evidence, because they are the years that selected the rule. On
    this panel that distinction is worth about five points of annual return, so
    the segment is tagged and every headline metric keeps ignoring it.
    """
    path = live_run / "daily_curve.csv"
    if not path.exists() or daily.empty:
        return daily.assign(phase="evaluated")
    source = pd.read_csv(path, parse_dates=["date"])
    context = source[source.decision_year < first_year].copy()
    if context.empty:
        return daily.assign(phase="evaluated")
    columns = [column for column in ("strategy", "mvo", "cdi", "equity_sleeve", "IBOVESPA", "BOVA11")
               if column in context.columns and column in daily.columns]
    # Chain the context onto the published series so the level is continuous at
    # the join instead of restarting at 100.
    for column in columns:
        closing = float(context[column].iloc[-1])
        opening = float(daily[column].iloc[0])
        if closing > 0:
            context[column] = context[column] / closing * opening
    context["phase"] = "selection"
    evaluated = daily.assign(phase="evaluated")
    shared = [column for column in evaluated.columns if column in context.columns]
    return (pd.concat([context[shared], evaluated[shared]], ignore_index=True)
            .sort_values("date").reset_index(drop=True))


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
        live_run = runs[str(selection.selected_configuration.iloc[-1])]
        daily = prepend_selection_window(daily, live_run, int(selection.decision_year.min()))
        daily.to_csv(output / "daily_curve.csv", index=False)
    # The live configuration's limits travel with the protocol. Without them the
    # page that prints "até X em renda variável e Y por emissor" has nothing to
    # read and renders NaN, which in a financial product reads as a broken
    # system rather than a missing field.
    live = str(selection.selected_configuration.iloc[-1])
    live_limits = _configuration_limits(live)
    protocol = {
        "factor": "nested_configuration_selection",
        "start_year": int(annual.decision_year.min()),
        "end_year": int(annual.decision_year.max()) + 1,
        **live_limits,
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
