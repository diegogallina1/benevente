"""Freeze one rule, one protocol and one dataset before any result is read.

Everything measured on 2015-2025 in this repository is in-sample. The grid was
searched, the holdout was consulted, and the published rule ranked 57th of 73 on
the criterion that was supposed to select it. No correction to the historical
numbers can undo that: only data that did not exist when the rule was fixed can
test the rule.

This module writes that commitment down. It records the rule, every parameter,
the SHA-256 of every input file, the evaluation window that has not happened
yet, and the criterion that will decide success or failure. It deliberately
computes no performance statistic. A registration that reports a return is not
a registration.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, asdict
from datetime import date
import hashlib
import json
from pathlib import Path


@dataclass(frozen=True)
class SuccessCriterion:
    """What would have to happen for the rule to be judged useful."""
    minimum_years: int = 3
    must_beat_cdi_after_tax: bool = True
    must_beat_investable_market_etf: bool = True
    maximum_acceptable_drawdown: float = .35
    falsification: str = (
        "Failure to clear the CDI after tax over the full prospective window, or a drawdown beyond the stated limit, "
        "refutes the rule. A single good year does not confirm it and a single bad year does not refute it."
    )


def file_digest(path: str | Path) -> dict:
    target = Path(path)
    digest = hashlib.sha256()
    with target.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return {"path": str(target).replace("\\", "/"), "sha256": digest.hexdigest(), "bytes": target.stat().st_size}


def build_registration(rule: str, parameters: dict, inputs: list[str], selection_rationale: str,
                       evaluation_start_year: int, registered_on: str,
                       criterion: SuccessCriterion | None = None) -> dict:
    criterion = criterion or SuccessCriterion()
    payload = {
        "registered_on": registered_on,
        "rule": rule,
        "parameters": parameters,
        "selection_rationale": selection_rationale,
        "evaluation": {
            "prospective_from_year": evaluation_start_year,
            "in_sample_window": "2015-2025",
            "in_sample_status": (
                "Exploratory. The candidate grid, the factor family and the constraint set were all chosen while "
                "these years were visible. Reported historical figures describe the sample, not expected return."
            ),
            "success_criterion": asdict(criterion),
        },
        "inputs": [file_digest(item) for item in inputs],
        "amendment_policy": (
            "Any change to the rule, the parameters or the input files creates a new registration with a new date. "
            "The superseded registration is kept; it is not edited."
        ),
    }
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    payload["registration_sha256"] = hashlib.sha256(body).hexdigest()
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze a single pre-registered rule and its evaluation protocol.")
    parser.add_argument("--rule", default="value_quality",
                        help="Factor identifier as accepted by annual_walk_forward.py.")
    parser.add_argument("--maximum-equity-weight", type=float, default=.55)
    parser.add_argument("--maximum-asset-weight", type=float, default=.12)
    parser.add_argument("--top-assets", type=int, default=5)
    parser.add_argument("--minimum-average-daily-value-brl", type=float, default=10_000_000)
    parser.add_argument("--risk-profile", default="moderado")
    parser.add_argument("--evaluation-start-year", type=int, default=2026)
    parser.add_argument("--registered-on", default=date.today().isoformat())
    parser.add_argument("--selection-rationale", default=(
        "Chosen from the method this repository documents as its baseline, not from any performance ranking. "
        "The rule was fixed before the prospective window opened and no candidate search informed it."))
    parser.add_argument("--input", action="append", default=[], metavar="PATH",
                        help="Input file to hash into the registration; repeatable.")
    parser.add_argument("--output", default="artifacts/preregistration")
    args = parser.parse_args()

    inputs = args.input or [
        "data/prices_b3_total_return_full_2013_2025.csv",
        "data/prices_b3_total_return_full_2013_2025_manifest.json",
        "data/benchmarks_market_2013_2025.csv",
    ]
    parameters = {
        "maximum_equity_weight": args.maximum_equity_weight,
        "maximum_asset_weight": args.maximum_asset_weight,
        "top_assets": args.top_assets,
        "minimum_average_daily_value_brl": args.minimum_average_daily_value_brl,
        "risk_profile": args.risk_profile,
        "review_frequency": "annual, first trading session of the calendar year",
        "cost_model": "B3 regular fee plus participation-dependent slippage, priced per ticker liquidity",
        "tax_model": "15% on realised equity gains, 17.5% on the redeemed defensive sleeve",
    }
    registration = build_registration(args.rule, parameters, inputs, args.selection_rationale,
                                      args.evaluation_start_year, args.registered_on)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / f"registration_{args.registered_on}_{args.rule}.json"
    target.write_text(json.dumps(registration, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"file": str(target), "registration_sha256": registration["registration_sha256"],
                      "rule": args.rule, "prospective_from": args.evaluation_start_year}, indent=2))


if __name__ == "__main__":
    main()
