"""Create reviewable B3-ticker/CVM-CNPJ mapping and a coverage report."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from b3_cvm_mapping import (
    coverage_summary, load_b3_isin_database, load_b3_issuer_database, load_cvm_company_master,
    map_b3_equities,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Map a dated B3 equity universe to official CVM company CNPJs.")
    parser.add_argument("--universe", required=True, help="Dated output from build_b3_universe_snapshot.py")
    parser.add_argument("--cvm-master", required=True, help="Official cad_cia_aberta.csv downloaded from CVM")
    parser.add_argument("--output", default="data/b3_cvm_ticker_map.csv")
    parser.add_argument("--coverage-report", default="artifacts/b3_cvm_mapping_coverage.csv")
    parser.add_argument("--manual-overrides", help="Reviewed ticker,cnpj_cia CSV; never infer an ambiguous issuer")
    parser.add_argument("--b3-isin-dir", help="Extracted official B3 ISIN complete database directory")
    args = parser.parse_args()
    universe = pd.read_csv(args.universe)
    master = load_cvm_company_master(args.cvm_master)
    isin_bridge = load_b3_isin_database(args.b3_isin_dir) if args.b3_isin_dir else None
    b3_issuers = load_b3_issuer_database(args.b3_isin_dir) if args.b3_isin_dir else None
    if "universe_year" not in universe.columns:
        mapping = map_b3_equities(universe, master, args.manual_overrides, isin_bridge, b3_issuers)
    else:
        parts = []
        for year, snapshot in universe.groupby("universe_year", sort=True):
            part = map_b3_equities(snapshot, master, args.manual_overrides, isin_bridge, b3_issuers)
            part["universe_year"] = int(year)
            part["decision_date"] = snapshot.decision_date.iloc[0]
            parts.append(part)
        mapping = pd.concat(parts, ignore_index=True)
    output, report = Path(args.output), Path(args.coverage_report)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(output, index=False)
    summary = coverage_summary(mapping)
    if "universe_year" in mapping.columns:
        annual = mapping.groupby(["universe_year", "mapping_status"], dropna=False).size().unstack(fill_value=0)
        annual["equities"] = annual.sum(axis=1)
        annual["accepted_share"] = annual.get("accepted", 0) / annual.equities
        annual.reset_index().to_csv(report.with_name(report.stem + "_annual.csv"), index=False)
    summary.to_csv(report, index=False)
    accepted = int(mapping.mapping_status.eq("accepted").sum())
    print(f"Mapped {accepted}/{len(mapping)} B3 equities as accepted; review the remaining rows in {output}.")


if __name__ == "__main__":
    main()
