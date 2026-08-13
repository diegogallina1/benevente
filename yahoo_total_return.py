"""Reproducible B3 total-return research panel from Yahoo Finance and BCB CDI.

Yahoo's ``Adj Close`` is used exactly as delivered as a total-return proxy.
The per-ticker history, cash-dividend and split observations returned by
``yfinance`` are archived beside a coverage report.  The official B3 COTAHIST
panel remains the dated universe and unadjusted-price reconciliation source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from time import sleep
from typing import Callable

import pandas as pd

from brapi_total_return import _fetch_cdi


def _symbol(ticker: str) -> str:
    value = str(ticker).upper().strip()
    return value if value.endswith(".SA") else value + ".SA"


def _ticker_from_symbol(symbol: str) -> str:
    """Return the canonical B3 ticker used by the fundamentals panel.

    Yahoo requires the ``.SA`` market suffix.  The provider symbol is kept in
    the coverage report, while the exported panel uses the bare B3 code.
    """
    return str(symbol).upper().removesuffix(".SA")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_history(frame: pd.DataFrame, symbol: str, start: pd.Timestamp,
                       end: pd.Timestamp) -> tuple[pd.Series, pd.DataFrame]:
    if frame.empty or "Adj Close" not in frame.columns:
        raise ValueError("Yahoo returned no adjusted-close history")
    copy = frame.copy()
    # Historical Yahoo CSVs cross Brazilian daylight-saving periods, therefore
    # their stored ISO timestamps have mixed UTC offsets. Parse them together
    # as UTC before converting to the local trading date.
    copy.index = (pd.to_datetime(copy.index.astype(str), format="mixed", utc=True, errors="coerce")
                  .tz_convert("America/Sao_Paulo").tz_localize(None).normalize())
    copy = copy[~copy.index.isna()]
    copy = copy.loc[(copy.index >= start) & (copy.index <= end)]
    adjusted = pd.to_numeric(copy["Adj Close"], errors="coerce")
    adjusted = adjusted.where(adjusted > 0).dropna()
    if adjusted.empty:
        raise ValueError("Yahoo returned no positive adjusted-close values in the requested window")
    if adjusted.index.duplicated().any():
        raise ValueError("Yahoo returned duplicate dates")
    return adjusted.rename(symbol), copy


def _events_from_history(history: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    if "Dividends" in history:
        dividends = pd.to_numeric(history["Dividends"], errors="coerce").fillna(0)
        rows.append(pd.DataFrame({"date": dividends.index, "event_type": "cash_dividend", "value": dividends}).query("value != 0"))
    if "Stock Splits" in history:
        splits = pd.to_numeric(history["Stock Splits"], errors="coerce").fillna(0)
        rows.append(pd.DataFrame({"date": splits.index, "event_type": "stock_split", "value": splits}).query("value != 0"))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["date", "event_type", "value"])


def _history_from_yahoo(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    import yfinance as yf
    # yfinance's end is exclusive. Preserve corporate actions in the archive.
    return yf.Ticker(symbol).history(start=start.date(), end=(end + pd.Timedelta(days=1)).date(),
                                     auto_adjust=False, actions=True, repair=False)


def _cached_or_download(symbol: str, start: pd.Timestamp, end: pd.Timestamp,
                        raw_root: Path, fetch_history: Callable[[str, pd.Timestamp, pd.Timestamp], pd.DataFrame],
                        resume: bool) -> tuple[pd.DataFrame, bool]:
    history_path = raw_root / "history" / f"{symbol}.csv"
    if resume and history_path.exists():
        # An empty CSV from a transient Yahoo response is not a successful
        # cache entry; retry it in a later controlled batch.
        cached = pd.read_csv(history_path)
        if "date" in cached and "Adj Close" in cached and not cached.empty:
            return cached.set_index("date"), True
    history = fetch_history(symbol, start, end)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    output = history.copy()
    output.index.name = "date"
    output.reset_index().to_csv(history_path, index=False)
    return history, False


def build_yahoo_total_return(tickers: list[str], start: str | pd.Timestamp, end: str | pd.Timestamp,
                             output_path: str | Path, manifest_path: str | Path,
                             coverage_path: str | Path, raw_dir: str | Path,
                             pause_seconds: float = 0.1, resume: bool = True,
                             download_limit: int | None = None,
                             fetch_history: Callable[[str, pd.Timestamp, pd.Timestamp], pd.DataFrame] = _history_from_yahoo) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Build a sparse, dated adjusted-close panel; failures stay in coverage."""
    start_date, end_date = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end_date <= start_date:
        raise ValueError("end date must be after start date")
    symbols = sorted({_symbol(item) for item in tickers if str(item).strip()})
    if not symbols:
        raise ValueError("At least one B3 ticker is required")
    output, manifest_file, coverage_file, raw_root = map(Path, (output_path, manifest_path, coverage_path, raw_dir))
    raw_root.mkdir(parents=True, exist_ok=True)
    curves: list[pd.Series] = []
    rows: list[dict[str, object]] = []
    newly_downloaded = 0
    for count, symbol in enumerate(symbols, start=1):
        ticker = _ticker_from_symbol(symbol)
        row: dict[str, object] = {"ticker": ticker, "source_symbol": symbol, "status": "blocked", "reason": ""}
        try:
            cache_exists = (raw_root / "history" / f"{symbol}.csv").exists()
            if resume and not cache_exists and download_limit is not None and newly_downloaded >= download_limit:
                row.update({"status": "deferred", "reason": "download_batch_limit"})
                rows.append(row)
                continue
            history, from_cache = _cached_or_download(symbol, start_date, end_date, raw_root, fetch_history, resume)
            newly_downloaded += int(not from_cache)
            adjusted, normalised = _normalise_history(history, ticker, start_date, end_date)
            events = _events_from_history(normalised)
            event_path = raw_root / "events" / f"{symbol}.csv"
            event_path.parent.mkdir(parents=True, exist_ok=True)
            events.to_csv(event_path, index=False)
            curves.append(adjusted)
            row.update({"status": "accepted", "from_cache": from_cache,
                        "first_date": str(adjusted.index.min().date()), "last_date": str(adjusted.index.max().date()),
                        "adjusted_close_rows": len(adjusted),
                        "cash_dividend_events": int(events.event_type.eq("cash_dividend").sum()),
                        "stock_split_events": int(events.event_type.eq("stock_split").sum())})
        except Exception as exc:  # retain all unavailable/delisted Yahoo symbols for audit
            row["reason"] = str(exc)
        rows.append(row)
        if pause_seconds and count < len(symbols):
            sleep(pause_seconds)
    if not curves:
        raise RuntimeError("Yahoo returned no eligible adjusted-close series")
    cdi = _fetch_cdi(start_date, end_date, raw_root / "bcb_sgs_12_cdi.json")
    panel = pd.concat(curves + [cdi], axis=1, sort=True).sort_index()
    sessions = panel.drop(columns="TITULO_CDI", errors="ignore").dropna(how="all").index
    panel = panel.reindex(sessions)
    panel["TITULO_CDI"] = panel["TITULO_CDI"].ffill().bfill()
    output.parent.mkdir(parents=True, exist_ok=True)
    coverage_file.parent.mkdir(parents=True, exist_ok=True)
    panel.reset_index(names="date").to_csv(output, index=False)
    coverage = pd.DataFrame(rows).sort_values("ticker")
    coverage.to_csv(coverage_file, index=False)
    import yfinance
    manifest = {
        "price_basis": "total_return",
        "source_tier": "public_reproducible_research",
        "provider": "Yahoo Finance via yfinance adjusted close",
        "provider_library_version": getattr(yfinance, "__version__", "unknown"),
        "extraction_timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "coverage_start": str(panel.index.min().date()), "coverage_end": str(panel.index.max().date()),
        "corporate_actions": "Yahoo adjusted close; archived yfinance action observations for cash dividends and stock splits. JCP classification is not supplied separately by Yahoo.",
        "cdi_source": "Banco Central do Brasil SGS 12 (CDI diário), raw response archived",
        "file_sha256": _sha256(output), "coverage_report": str(coverage_file), "raw_response_directory": str(raw_root),
        "requested_tickers": len(symbols), "accepted_tickers": int(coverage.status.eq("accepted").sum()),
        "blocked_tickers": int(coverage.status.ne("accepted").sum()),
        "deferred_tickers": int(coverage.status.eq("deferred").sum()),
        "newly_downloaded_tickers": newly_downloaded,
        "b3_reconciliation_source": "Official B3 COTAHIST is retained for dated universe and unadjusted-price reconciliation.",
        "research_restriction": "Public reproducible secondary source; reconcile event samples against B3/CVM primary records before institutional or commercial claims.",
    }
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return panel.reset_index(names="date"), coverage, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public reproducible B3 adjusted-close total-return input from Yahoo Finance.")
    parser.add_argument("--fundamentals", required=True)
    parser.add_argument("--start", default="2013-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--output", default="data/prices_yahoo_adjusted_total_return_2013_2025.csv")
    parser.add_argument("--manifest", default="data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    parser.add_argument("--coverage-report", default="artifacts/yahoo_adjusted_total_return_coverage.csv")
    parser.add_argument("--raw-dir", default="work/yahoo_total_return")
    parser.add_argument("--max-tickers", type=int)
    parser.add_argument("--pause-seconds", type=float, default=.1)
    parser.add_argument("--download-limit", type=int,
                        help="Maximum uncached tickers to download this run; rerun to resume safely.")
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    frame = pd.read_csv(args.fundamentals, dtype={"ticker": str})
    if "ticker" not in frame:
        raise ValueError("Fundamental panel requires ticker column")
    tickers = sorted(frame.ticker.dropna().unique())
    if args.max_tickers:
        tickers = tickers[:args.max_tickers]
    _, coverage, manifest = build_yahoo_total_return(
        tickers, args.start, args.end, args.output, args.manifest, args.coverage_report,
        args.raw_dir, args.pause_seconds, not args.no_resume, args.download_limit,
    )
    print(json.dumps({"accepted_tickers": int(coverage.status.eq("accepted").sum()), **manifest}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
