"""Create reviewable B3-ticker/CVM-CNPJ mapping and a coverage report."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from b3_cvm_mapping import coverage_summary, load_cvm_company_master, map_b3_equities


def main() -> None:
    parser = argparse.ArgumentParser(description="Map a dated B3 equity universe to official CVM company CNPJs.")
    parser.add_argument("--universe", required=True, help="Dated output from build_b3_universe_snapshot.py")
    parser.add_argument("--cvm-master", required=True, help="Official cad_cia_aberta.csv downloaded from CVM")
    parser.add_argument("--output", default="data/b3_cvm_ticker_map.csv")
    parser.add_argument("--coverage-report", default="artifacts/b3_cvm_mapping_coverage.csv")
    parser.add_argument("--manual-overrides", help="Reviewed ticker,cnpj_cia CSV; never infer an ambiguous issuer")
    args = parser.parse_args()
    mapping = map_b3_equities(pd.read_csv(args.universe), load_cvm_company_master(args.cvm_master), args.manual_overrides)
    output, report = Path(args.output), Path(args.coverage_report)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(output, index=False)
    coverage_summary(mapping).to_csv(report, index=False)
    accepted = int(mapping.mapping_status.eq("accepted").sum())
    print(f"Mapped {accepted}/{len(mapping)} B3 equities as accepted; review the remaining rows in {output}.")


if __name__ == "__main__":
    main()
