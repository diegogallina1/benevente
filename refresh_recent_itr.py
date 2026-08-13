"""Refresh recent CVM ITR fundamentals for every eligible mapped B3 issuer."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from cvm_itr import CvmItrClient
from live_issuer_map import load_live_issuer_map
from market_snapshot import load_market_snapshots


def _sha256(path: str | Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def refresh_recent_itr(itr_year: int, decision_date: pd.Timestamp, market_snapshot_path: str | Path,
                       issuer_map_path: str | Path, max_age_days: int = 120,
                       client: CvmItrClient | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    market = load_market_snapshots(market_snapshot_path, decision_date, max_age_days)
    mapping = load_live_issuer_map(issuer_map_path, set(market), decision_date, max_age_days)
    itr = client or CvmItrClient()
    rows: list[dict] = []
    coverage = mapping.coverage.to_dict("records")
    for issuer in mapping.issuers:
        try:
            snapshot = itr.live_snapshots(itr_year, decision_date, {issuer.ticker: market[issuer.ticker]}, (issuer,))[0]
            record = snapshot.model_dump()
            record.update({"decision_date": str(decision_date.date()), "itr_year": itr_year,
                           "snapshot_vintage": "recent CVM ITR/DFP, B3/CVM map and market snapshot dated at decision"})
            rows.append(record)
        except Exception as exc:
            for item in coverage:
                if item["ticker"] == issuer.ticker:
                    item.update({"status": "blocked", "reason": str(exc)})
                    break
    manifest = {
        "decision_date": str(decision_date.date()), "itr_year": itr_year,
        "market_snapshot_sha256": _sha256(market_snapshot_path),
        "issuer_map_sha256": _sha256(issuer_map_path),
        "eligible_mapped_issuers": len(mapping.issuers), "accepted_snapshots": len(rows),
        "status": "ready" if rows else "blocked",
    }
    return pd.DataFrame(rows), pd.DataFrame(coverage), manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh dated CVM ITR/DFP snapshots; no orders are sent.")
    parser.add_argument("--itr-year", type=int, required=True)
    parser.add_argument("--decision-date", required=True)
    parser.add_argument("--market-snapshot", required=True)
    parser.add_argument("--issuer-map", required=True, help="Dated accepted B3 ticker-to-CNPJ mapping CSV")
    parser.add_argument("--max-age-days", type=int, default=120)
    parser.add_argument("--output", default="artifacts/recent_itr/fundamentals.csv")
    parser.add_argument("--coverage-report", default="artifacts/recent_itr/coverage.csv")
    parser.add_argument("--manifest", default="artifacts/recent_itr/refresh_manifest.json")
    args = parser.parse_args()
    rows, coverage, manifest = refresh_recent_itr(
        args.itr_year, pd.Timestamp(args.decision_date), args.market_snapshot, args.issuer_map, args.max_age_days,
    )
    for filename, frame in ((args.output, rows), (args.coverage_report, coverage)):
        destination = Path(filename); destination.parent.mkdir(parents=True, exist_ok=True); frame.to_csv(destination, index=False)
    destination = Path(args.manifest); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    raise SystemExit(0 if manifest["status"] == "ready" else 2)


if __name__ == "__main__":
    main()
