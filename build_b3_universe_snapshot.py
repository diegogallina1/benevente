"""CLI: create a dated B3 universe CSV from the official COTAHIST ZIP."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from b3_universe import build_universe_snapshot, parse_cotahist


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a broad, dated B3 investable-universe snapshot from COTAHIST.")
    parser.add_argument("--cotahist", required=True, help="Official B3 COTAHIST annual ZIP.")
    parser.add_argument("--decision-date", required=True, help="Decision date; no later quote is used.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--liquidity-days", type=int, default=60)
    parser.add_argument("--web-output", help="Optional compact JSON for the public coverage explorer.")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    universe = build_universe_snapshot(parse_cotahist(args.cotahist), args.decision_date, args.liquidity_days)
    universe.to_csv(output, index=False)
    if args.web_output:
        payload = {
            "decision_date": args.decision_date,
            "observed_at": str(universe.observed_at.iloc[0]),
            "instrument_count": int(len(universe)),
            "coverage_by_class": {name: int(value) for name, value in universe.asset_class.value_counts().items()},
            "source": str(universe.source.iloc[0]),
            "instruments": universe[["ticker", "asset_class", "issuer_name", "specification", "close_price_brl", "average_daily_value_brl", "trading_days"]].to_dict(orient="records"),
            "eligibility_note": "O arquivo COTAHIST prova que o instrumento foi negociado. Ele não fornece, sozinho, fundamentos, suitability ou aprovação para uma proposta.",
        }
        web_output = Path(args.web_output); web_output.parent.mkdir(parents=True, exist_ok=True)
        web_output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(universe)} B3 instruments to {output}; coverage: {universe.asset_class.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
