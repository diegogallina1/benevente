"""Consolidate checkpointed B3/CVM panels into one auditable research input."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def consolidate(panel_paths: list[str | Path], coverage_paths: list[str | Path], universe_path: str | Path,
                mapping_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a unique fundamental panel plus annual B3/CVM coverage counts."""
    panels = [pd.read_csv(path) for path in panel_paths]
    coverage = [pd.read_csv(path) for path in coverage_paths]
    fundamentals = pd.concat(panels, ignore_index=True).sort_values(["decision_date", "ticker"])
    gates = pd.concat(coverage, ignore_index=True).sort_values(["decision_date", "ticker"])
    if fundamentals.duplicated(["decision_date", "ticker"]).any() or gates.duplicated(["decision_date", "ticker"]).any():
        raise ValueError("Checkpoint files contain duplicate decision-date/ticker rows")
    universe = pd.read_csv(universe_path)
    mapping = pd.read_csv(mapping_path)
    total_instruments = universe.groupby("universe_year").size().rename("b3_instruments")
    equities = universe[universe.asset_class.eq("equity")].groupby("universe_year").size().rename("b3_equities")
    mapped = (mapping[mapping.mapping_status.eq("accepted")].groupby("universe_year").size()
              .rename("identifier_accepted"))
    fundamental = gates[gates.status.eq("accepted")].copy()
    fundamental["universe_year"] = pd.to_datetime(fundamental.decision_date).dt.year
    fundamental = fundamental.groupby("universe_year").size().rename("fundamental_accepted")
    blocked = gates[gates.status.eq("blocked")].copy()
    blocked["universe_year"] = pd.to_datetime(blocked.decision_date).dt.year
    blocked = blocked.groupby("universe_year").size().rename("fundamental_blocked")
    summary = pd.concat([total_instruments, equities, mapped, fundamental, blocked], axis=1).fillna(0).reset_index()
    summary["identifier_accepted_share"] = summary.identifier_accepted / summary.b3_equities
    summary["fundamental_accepted_share_of_mapped"] = summary.fundamental_accepted / summary.identifier_accepted
    summary["fundamental_accepted_share_of_equities"] = summary.fundamental_accepted / summary.b3_equities
    return fundamentals.reset_index(drop=True), summary.sort_values("universe_year").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Consolidate full-universe B3/CVM checkpoints.")
    parser.add_argument("--panel", action="append", required=True, help="One or more fundamental checkpoint CSVs")
    parser.add_argument("--coverage", action="append", required=True, help="Matching coverage-report CSVs")
    parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--output", default="data/fundamentals_b3_cvm_full_2013_2025.csv")
    parser.add_argument("--summary", default="data/b3_cvm_historical_coverage_summary.csv")
    args = parser.parse_args()
    if len(args.panel) != len(args.coverage):
        raise ValueError("Each fundamental checkpoint must have one matching coverage report")
    panel, summary = consolidate(args.panel, args.coverage, args.universe, args.mapping)
    output, summary_path = Path(args.output), Path(args.summary)
    output.parent.mkdir(parents=True, exist_ok=True); summary_path.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False); summary.to_csv(summary_path, index=False)
    print(f"Consolidated {len(panel)} accepted snapshots. Panel: {output}; annual coverage: {summary_path}")


if __name__ == "__main__":
    main()
