"""Readiness gate before a real Benevente research proposal is issued."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from production_policy import load_policy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--market-snapshot", required=True)
    parser.add_argument("--price-history", required=True)
    parser.add_argument("--output", default="artifacts/production_readiness.json")
    args = parser.parse_args()
    policy = load_policy(args.policy)
    market_file = Path(args.market_snapshot)
    price_file = Path(args.price_history)
    for label, candidate in (("market snapshot", market_file), ("price history", price_file)):
        if not candidate.exists() or candidate.stat().st_size <= 100:
            raise ValueError(f"A populated {label} CSV is required.")
    report = {
        "status": "INPUTS_PRESENT_REQUIRES_LIVE_CVM_AND_POLICY_VALIDATION",
        "policy_id": policy.policy_id,
        "market_snapshot_file": str(market_file.resolve()),
        "price_history_file": str(price_file.resolve()),
        "requirements": [
            "Generate proposal with live_proposal_runner.py using current CVM ITR/DFP data",
            "The runner must validate filing availability, market-data age, price-history coverage, eligibility, liquidity and cost limits",
            "Independent human approval of every proposed order",
            "Enter orders manually in the broker platform",
            "Import broker notes and reconcile estimated versus actual fees",
        ],
    }
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
