"""Build annual, point-in-time B3 equity universes from official COTAHIST ZIPs.

Each annual COTAHIST file is a constituent observation for that year, not a
replacement with today's listings.  Downloading is explicit and cached; the
script fails closed when a vintage archive is missing.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from b3_universe import build_universe_snapshot, parse_cotahist


OFFICIAL_COTAHIST_URL = "https://bvmf.bmfbovespa.com.br/InstDados/SerHist/COTAHIST_A{year}.ZIP"


def fetch_cotahist(year: int, cache_dir: str | Path) -> Path:
    """Download one official B3 annual archive if it was not cached already."""
    import requests
    if year < 1986:
        raise ValueError("B3 historical quotation files begin in 1986.")
    cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f"COTAHIST_A{year}.ZIP"
    if archive.exists() and archive.stat().st_size > 1_000:
        return archive
    response = requests.get(OFFICIAL_COTAHIST_URL.format(year=year), timeout=180)
    response.raise_for_status()
    if len(response.content) < 1_000:
        raise RuntimeError(f"Official B3 archive for {year} is unexpectedly small.")
    archive.write_bytes(response.content)
    return archive


def build_historical_b3_universes(start_year: int, end_year: int, cache_dir: str | Path,
                                  liquidity_days: int = 60, download: bool = False,
                                  checkpoint_dir: str | Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return all annual universes and an explicit coverage table.

    The decision is the first session available in January.  Liquidity is
    computed with data at or before that session only, preventing future-year
    membership or turnover from appearing in the decision set.
    """
    if end_year < start_year:
        raise ValueError("end_year must not precede start_year")
    cache = Path(cache_dir)
    checkpoint = Path(checkpoint_dir) if checkpoint_dir else None
    if checkpoint:
        checkpoint.mkdir(parents=True, exist_ok=True)
    universes: list[pd.DataFrame] = []
    coverage: list[dict] = []
    for year in range(start_year, end_year + 1):
        archive = cache / f"COTAHIST_A{year}.ZIP"
        prior_archive = cache / f"COTAHIST_A{year - 1}.ZIP"
        try:
            if not archive.exists() or not prior_archive.exists():
                if not download:
                    missing = archive if not archive.exists() else prior_archive
                    raise FileNotFoundError(f"Missing B3 archive {missing}; use --download after reviewing source scope.")
                archive = fetch_cotahist(year, cache)
                prior_archive = fetch_cotahist(year - 1, cache)
            # The first January session needs the preceding 60 trading days.
            # Therefore liquidity is based on the current and prior annual
            # files, while membership is still observed strictly on decision.
            window_start = pd.Timestamp(year=year - 1, month=10, day=1)
            january_end = pd.Timestamp(year=year, month=1, day=31)
            quotations = pd.concat([
                parse_cotahist(prior_archive, start_date=window_start),
                parse_cotahist(archive, end_date=january_end),
            ], ignore_index=True)
            january = quotations[(quotations.trade_date.dt.year == year) & (quotations.trade_date.dt.month == 1)]
            if january.empty:
                raise ValueError(f"No January sessions in {archive.name}")
            decision = january.trade_date.min()
            snapshot = build_universe_snapshot(quotations, decision, liquidity_days)
            snapshot["universe_year"] = year
            universes.append(snapshot)
            if checkpoint:
                snapshot.to_csv(checkpoint / f"b3_universe_{year}.csv", index=False)
            coverage.append({"universe_year": year, "decision_date": decision.date().isoformat(),
                             "status": "accepted", "instruments": int(len(snapshot)),
                             "equities": int(snapshot.asset_class.eq("equity").sum()),
                             "reason": "", "liquidity_history": f"{year - 1}-{year}"})
        except Exception as exc:
            coverage.append({"universe_year": year, "decision_date": None, "status": "blocked",
                             "instruments": 0, "equities": 0, "reason": str(exc), "liquidity_history": ""})
    return (pd.concat(universes, ignore_index=True) if universes else pd.DataFrame(), pd.DataFrame(coverage))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dated annual B3 universes from official COTAHIST archives.")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--cache-dir", default="work/b3_cache")
    parser.add_argument("--output", default="data/b3_historical_universes.csv")
    parser.add_argument("--coverage-report", default="artifacts/b3_historical_universe_coverage.csv")
    parser.add_argument("--liquidity-days", type=int, default=60)
    parser.add_argument("--checkpoint-dir", help="Write each accepted annual universe immediately for resumable processing.")
    parser.add_argument("--download", action="store_true", help="Download missing archives from B3's official historical endpoint.")
    args = parser.parse_args()
    universe, coverage = build_historical_b3_universes(args.start_year, args.end_year, args.cache_dir,
                                                        args.liquidity_days, args.download, args.checkpoint_dir)
    output, report = Path(args.output), Path(args.coverage_report)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(output, index=False); coverage.to_csv(report, index=False)
    print(f"Built {len(universe)} dated B3 rows; accepted years: {int(coverage.status.eq('accepted').sum())}/{len(coverage)}")


if __name__ == "__main__":
    main()
