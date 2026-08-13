"""Issue a research-only/approved report for a frozen annual holdout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from model_validation import AnnualHoldoutGate, annual_holdout_readiness


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a frozen Benevente annual holdout against CDI and MVO.")
    parser.add_argument("--annual-results", required=True)
    parser.add_argument("--input-manifest", required=True, help="input_manifest.json from annual_walk_forward or preflight")
    parser.add_argument("--split-year", type=int, required=True, help="First decision year in the holdout")
    parser.add_argument("--output", default="artifacts/annual_holdout_validation.json")
    args = parser.parse_args()
    source_manifest = json.loads(Path(args.input_manifest).read_text(encoding="utf-8"))
    approved, evidence = annual_holdout_readiness(
        pd.read_csv(args.annual_results), args.split_year,
        bool(source_manifest.get("performance_permitted", False)), AnnualHoldoutGate(),
    )
    report = {"status": "approved" if approved else "research_only", "split_year": args.split_year,
              "input_manifest_status": source_manifest.get("status"), "evidence": evidence}
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if approved else 2)


if __name__ == "__main__":
    main()
