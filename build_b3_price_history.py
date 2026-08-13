"""Build a dated B3 close-price history for the annual decision protocol.

The output is intentionally labelled ``price_return_only``. COTAHIST records
traded prices and the quotation factor, but it is not a total-return series:
cash dividends, interest on capital and every corporate-action entitlement
need an additional official event feed or licensed total-return source before
performance claims may be computed.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from b3_universe import parse_cotahist


def build_price_history(tickers: set[str], start_year: int, end_year: int,
                        cache_dir: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return daily B3 last prices and an annual source/coverage manifest."""
    cache = Path(cache_dir)
    requested = {ticker.removesuffix(".SA") for ticker in tickers if ticker != "TITULO_CDI"}
    frames: list[pd.DataFrame] = []
    report: list[dict] = []
    for year in range(start_year, end_year + 1):
        path = cache / f"COTAHIST_A{year}.ZIP"
        if not path.exists():
            report.append({"year": year, "status": "blocked", "reason": f"missing_b3_archive:{path.name}", "rows": 0})
            continue
        quotes = parse_cotahist(path, tickers=requested)
        quotes = quotes[quotes.market_type.eq("010")].copy()
        if quotes.empty:
            report.append({"year": year, "status": "blocked", "reason": "no_requested_cash_market_quotes", "rows": 0})
            continue
        quotes["ticker"] = quotes.ticker_raw + ".SA"
        quotes["unit_close_brl"] = quotes.close_price_brl / quotes.quotation_factor.replace(0, 1)
        frames.append(quotes[["trade_date", "ticker", "unit_close_brl", "quotation_factor", "isin"]])
        report.append({"year": year, "status": "accepted", "reason": "", "rows": int(len(quotes))})
    if not frames:
        return pd.DataFrame(), pd.DataFrame(report)
    long = pd.concat(frames, ignore_index=True).drop_duplicates(["trade_date", "ticker"], keep="last")
    prices = long.pivot(index="trade_date", columns="ticker", values="unit_close_brl").sort_index()
    # Do not forward-fill across a delisting/listing gap. The downstream
    # annual runner may select only a ticker with complete prior history.
    prices.index.name = "date"
    return prices.reset_index(), pd.DataFrame(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build COTAHIST price-return-only history for dated B3 tickers.")
    parser.add_argument("--fundamentals", required=True, help="Full B3/CVM panel; tickers are read from it.")
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--cache-dir", default="work/b3_cache")
    parser.add_argument("--output", default="data/prices_b3_cotahist_price_return_only.csv")
    parser.add_argument("--coverage-report", default="artifacts/b3_price_history_coverage.csv")
    args = parser.parse_args()
    fundamentals = pd.read_csv(args.fundamentals, dtype={"ticker": str})
    prices, report = build_price_history(set(fundamentals.ticker), args.start_year, args.end_year, args.cache_dir)
    output, coverage = Path(args.output), Path(args.coverage_report)
    output.parent.mkdir(parents=True, exist_ok=True); coverage.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(output, index=False); report.to_csv(coverage, index=False)
    print(f"Wrote {len(prices)} price dates for {max(len(prices.columns) - 1, 0)} B3 tickers. Label: price_return_only.")


if __name__ == "__main__":
    main()
