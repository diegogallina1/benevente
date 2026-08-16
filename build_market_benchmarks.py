"""Build the external market references the annual protocol is judged against.

Two things were wrong before.  The Ibovespa series was labelled a price index
even though B3 computes it as a total-return index that reinvests proventos, so
the disclaimer attached to every comparison was factually inverted.  And the
only equity comparator was an internal optimiser, which is not something an
investor can buy.

This builder therefore publishes both:

``IBOVESPA``
    The index itself, B3's total-return benchmark. Not directly investable.
``BOVA11``
    The largest Ibovespa ETF, adjusted close. Investable, and already carrying
    its management fee inside the quoted price, so it is the honest bar for a
    strategy that claims to beat the local market.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd


REFERENCES = {
    "IBOVESPA": {
        "symbol": "^BVSP",
        "basis": "total_return_index",
        "investable": False,
        "note": ("B3 computes the Ibovespa as a total-return index: proventos are reinvested in the index. "
                 "It is therefore directly comparable with an adjusted-close equity panel."),
    },
    "BOVA11": {
        "symbol": "BOVA11.SA",
        "basis": "total_return_etf_adjusted_close",
        "investable": True,
        "note": ("iShares Ibovespa ETF. The quoted price is already net of the fund's management fee, so this is "
                 "the investable bar. Brokerage, spread and tax on redemption are still outside the series."),
    },
}


def download(symbol: str, start: str, end: str) -> pd.Series:
    import yfinance as yf

    history = yf.Ticker(symbol).history(start=pd.Timestamp(start).date(),
                                        end=(pd.Timestamp(end) + pd.Timedelta(days=1)).date(),
                                        auto_adjust=False, actions=False, repair=False)
    if history.empty or "Adj Close" not in history:
        raise ValueError(f"No history returned for {symbol}")
    series = pd.to_numeric(history["Adj Close"], errors="coerce")
    series.index = (pd.to_datetime(series.index.astype(str), format="mixed", utc=True, errors="coerce")
                    .tz_convert("America/Sao_Paulo").tz_localize(None).normalize())
    return series[series > 0].dropna()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dated Ibovespa and BOVA11 reference levels.")
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--output", default="data/benchmarks_market_2013_2025.csv")
    parser.add_argument("--manifest", default="data/benchmarks_market_2013_2025_manifest.json")
    args = parser.parse_args()

    series: dict[str, pd.Series] = {}
    coverage: dict[str, dict] = {}
    for name, reference in REFERENCES.items():
        values = download(str(reference["symbol"]), args.start, args.end)
        series[name] = values
        coverage[name] = {**reference, "first_date": str(values.index.min().date()),
                          "last_date": str(values.index.max().date()), "observations": int(len(values))}
    panel = pd.concat(series, axis=1).sort_index()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    panel.reset_index(names="date").to_csv(output, index=False)
    manifest = {
        "extraction_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "provider": "Yahoo Finance via yfinance",
        "references": coverage,
        "comparison_rule": ("Every reference is evaluated on the same decision and holding-end dates as the strategy. "
                            "Comparing different windows is the most common way an equity curve is made to look good."),
    }
    Path(args.manifest).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(coverage, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
