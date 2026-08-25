"""Add B3-listed global equity ETFs to the total-return panel.

Every diversification axis tested so far draws from the same ranking of the
same market: the sixth to twentieth Brazilian names are 0.93 correlated with
the top five, so adding them buys variety and not protection. A fund that holds
the S&P 500 in reais is the first candidate exposure in this project that is
not another draw from the B3 factor ranking.

The ETF is *declared*, never selected. It has no CVM filing, so it cannot pass
the fundamental screen and must not be smuggled past it: it enters the panel as
a priced instrument with no fundamental snapshot, which is exactly what keeps
the factor from ever choosing it.

The quoted adjusted close already carries the fund's management fee and its
reinvested distributions. It is a public feed, so this panel inherits the
parent's ``public_reproducible_research`` tier and supports no commercial
performance claim.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json

import pandas as pd

from build_market_benchmarks import download
from total_return_adapter import file_sha256

# Only IVVB11 has enough history for the evaluated window. The other two are
# recorded here because a reader will ask, and the answer is a date, not an
# opinion: they list in 2021 and cannot inform a 2015 decision.
GLOBAL_ETFS = {
    "IVVB11": {"symbol": "IVVB11.SA", "exposure": "S&P 500 in BRL, unhedged",
               "listed": "2014-04-29", "usable_from_decision_year": 2016},
    "NASD11": {"symbol": "NASD11.SA", "exposure": "Nasdaq-100 in BRL, unhedged",
               "listed": "2021-05-24", "usable_from_decision_year": 2023},
    "ACWI11": {"symbol": "ACWI11.SA", "exposure": "MSCI ACWI in BRL, unhedged",
               "listed": "2021-01-29", "usable_from_decision_year": 2023},
}


def build(parent_prices: Path, parent_manifest: Path, output: Path, manifest_output: Path,
          tickers: tuple[str, ...]) -> dict:
    parent = json.loads(parent_manifest.read_text(encoding="utf-8"))
    if file_sha256(parent_prices) != parent["file_sha256"]:
        raise ValueError("Parent total-return export does not match its manifest; refusing to extend it")
    panel = pd.read_csv(parent_prices, parse_dates=["date"]).sort_values("date").reset_index(drop=True)

    coverage: dict[str, dict] = {}
    for ticker in tickers:
        if ticker in panel.columns:
            raise ValueError(f"{ticker} already exists in the parent panel")
        series = download(GLOBAL_ETFS[ticker]["symbol"], str(panel.date.min().date()), str(panel.date.max().date()))
        # Align to the panel's own trading calendar. A session the panel does
        # not have is a session the strategy could not have traded on.
        aligned = series.reindex(panel.date)
        panel[ticker] = aligned.to_numpy()
        observed = aligned.dropna()
        coverage[ticker] = {
            **GLOBAL_ETFS[ticker],
            "sessions": int(len(observed)),
            "first_session": str(observed.index.min().date()),
            "last_session": str(observed.index.max().date()),
            "panel_sessions_missing_before_listing": int(len(aligned) - len(observed)),
        }

    output.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False)
    manifest = {
        **parent,
        "extraction_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": parent["provider"] + "; B3-listed global ETFs from Yahoo Finance adjusted close",
        "file_sha256": file_sha256(output),
        "ticker_count": int(panel.shape[1] - 1),
        "parent_panel": str(parent_prices).replace("\\", "/"),
        "parent_file_sha256": parent["file_sha256"],
        "global_etfs": coverage,
        "global_etf_status": (
            "Declared exposure, never selected. These instruments have no CVM filing and therefore no fundamental "
            "snapshot, so the factor screen cannot reach them. Their adjusted close already carries the fund fee "
            "and reinvested distributions."
        ),
        "research_restriction": parent["research_restriction"] + " Global ETF levels are a public adjusted-close "
                               "feed and carry no primary reconciliation of their own.",
    }
    manifest_output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Extend the total-return panel with B3-listed global ETFs.")
    parser.add_argument("--parent-prices", default="data/prices_b3_total_return_full_2011_2025.csv")
    parser.add_argument("--parent-manifest", default="data/prices_b3_total_return_full_2011_2025_manifest.json")
    parser.add_argument("--output", default="data/prices_b3_with_global_2011_2025.csv")
    parser.add_argument("--manifest", default="data/prices_b3_with_global_2011_2025_manifest.json")
    parser.add_argument("--tickers", default="IVVB11")
    args = parser.parse_args()
    manifest = build(Path(args.parent_prices), Path(args.parent_manifest), Path(args.output),
                     Path(args.manifest), tuple(item.strip() for item in args.tickers.split(",") if item.strip()))
    print(json.dumps({"ticker_count": manifest["ticker_count"], "global_etfs": manifest["global_etfs"]},
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
