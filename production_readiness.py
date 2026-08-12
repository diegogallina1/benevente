"""Readiness gate before a real Benevente research proposal is issued."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from production_policy import load_policy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--output", default="artifacts/production_readiness.json")
    args = parser.parse_args()
    policy = load_policy(args.policy)
    fundamental_file = Path(args.fundamentals)
    if not fundamental_file.exists() or fundamental_file.stat().st_size <= 100:
        raise ValueError("A populated point-in-time fundamentals CSV is required.")
    report = {
        "status": "READY_FOR_HUMAN_REVIEW_ONLY",
        "policy_id": policy.policy_id,
        "fundamental_file": str(fundamental_file.resolve()),
        "requirements": [
            "Generate proposal with value_portfolio_runner.py",
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

