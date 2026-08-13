"""Run the input gate for an annual walk-forward experiment."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from annual_input_contract import validate_annual_inputs, write_manifest
from annual_decision_evidence import load_decision_evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate B3/CVM annual inputs before performance is calculated.")
    parser.add_argument("--prices", required=True)
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--price-basis", required=True, choices=["total_return", "price_return_only"])
    parser.add_argument("--output", default="artifacts/annual_input_manifest.json")
    args = parser.parse_args()
    prices = pd.read_csv(args.prices)
    fundamentals = pd.read_csv(args.fundamentals)
    manifest = validate_annual_inputs(prices, fundamentals, args.price_basis).as_dict()
    _, evidence = load_decision_evidence(args.universe, args.mapping)
    manifest["decision_evidence"] = evidence.to_dict(orient="records")
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(__import__("json").dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{manifest['status']}: {','.join(manifest['reasons']) or 'all input gates passed'}")
    raise SystemExit(0 if manifest["performance_permitted"] else 2)


if __name__ == "__main__":
    main()
