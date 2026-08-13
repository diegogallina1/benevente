"""Build a reproducible B3 total-return research panel from brapi public data.

``adjustedClose`` is consumed exactly as supplied by brapi.  Cash dividends,
JCP, stock dividends, subscriptions and splits are retained as raw response
evidence, not reverse engineered from a price-only source.  This is a public
research source; it is intentionally labelled below the B3/licensed audit tier.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from time import sleep
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request

import pandas as pd


BRAPI_ROOT = "https://brapi.dev/api/v2/stocks"
BCB_CDI_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"


def _ticker_symbol(ticker: str) -> str:
    return str(ticker).upper().strip().removesuffix(".SA")


def _download_json(url: str) -> tuple[bytes, dict]:
    """Fetch a public or authenticated brapi response without leaking a token."""
    headers = {"User-Agent": "Benevente-Quant-AI/1.0 research contact: repository", "Accept": "application/json"}
    token = brapi_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    # requests consistently supports the BCB SGS API's content negotiation
    # while retaining the same plain HTTPS request contract for brapi.
    import requests
    response = requests.get(url, headers=headers, timeout=120)
    response.raise_for_status()
    raw = response.content
    return raw, json.loads(raw.decode("utf-8"))


def brapi_token() -> str:
    """Read BRAPI_TOKEN from the environment or ignored .env.local, if present."""
    token = os.getenv("BRAPI_TOKEN", "").strip()
    if token:
        return token
    local = Path(".env.local")
    if not local.exists():
        return ""
    for line in local.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().partition("=")
        if separator and key.strip() == "BRAPI_TOKEN":
            return value.strip().strip('"').strip("'")
    return ""


def _date_from_brapi(timestamp: object) -> pd.Timestamp:
    return (pd.Timestamp(int(timestamp), unit="s", tz="UTC")
            .tz_convert("America/Sao_Paulo").tz_localize(None).normalize())


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_raw(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _historical_url(ticker: str) -> str:
    return f"{BRAPI_ROOT}/historical?" + urlencode({"symbols": _ticker_symbol(ticker), "range": "max", "interval": "1d"})


def _events_url(ticker: str) -> str:
    return f"{BRAPI_ROOT}/dividends?" + urlencode({"symbols": _ticker_symbol(ticker)})


def _extract_price_series(payload: dict, ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> tuple[pd.Series, dict[str, int]]:
    results = payload.get("results") or []
    if not results or not isinstance(results[0], dict):
        raise ValueError("brapi historical response has no result")
    data = results[0].get("data") or {}
    records = data.get("historicalDataPrice") or []
    rows = []
    missing_adjusted = 0
    for record in records:
        date = _date_from_brapi(record.get("date"))
        value = record.get("adjustedClose")
        if value is None:
            missing_adjusted += 1
            continue
        try:
            value = float(value)
        except (TypeError, ValueError):
            missing_adjusted += 1
            continue
        if value > 0 and start <= date <= end:
            rows.append((date, value))
    series = pd.Series(dict(rows), name=ticker, dtype=float).sort_index()
    if series.index.duplicated().any():
        raise ValueError(f"brapi returned duplicate adjusted-close dates for {ticker}")
    return series, {"raw_price_rows": len(records), "missing_adjusted_close": missing_adjusted,
                    "accepted_adjusted_close_rows": len(series)}


def _event_counts(payload: dict) -> dict[str, int]:
    results = payload.get("results") or []
    data = results[0].get("data") if results and isinstance(results[0], dict) else {}
    data = data or {}
    return {
        "cash_dividends_jcp_events": len(data.get("cashDividends") or []),
        "stock_dividend_split_events": len(data.get("stockDividends") or []),
        "subscription_events": len(data.get("subscriptions") or []),
    }


def _fetch_cdi(start: pd.Timestamp, end: pd.Timestamp, raw_path: Path,
               fetch: Callable[[str], tuple[bytes, dict]] = _download_json) -> pd.Series:
    payloads: list[object] = []
    raw_parts: list[bytes] = []
    # SGS can reject a large calendar interval. Request one year at a time so
    # both error recovery and the raw audit trail are granular.
    for year in range(start.year, end.year + 1):
        left, right = max(start, pd.Timestamp(year=year, month=1, day=1)), min(end, pd.Timestamp(year=year, month=12, day=31))
        params = urlencode({"formato": "json", "dataInicial": left.strftime("%d/%m/%Y"), "dataFinal": right.strftime("%d/%m/%Y")})
        raw, payload = fetch(f"{BCB_CDI_URL}?{params}")
        raw_parts.append(raw)
        if isinstance(payload, list):
            payloads.extend(payload)
    _write_raw(raw_path, b"[" + b",".join(part.strip().removeprefix(b"[").removesuffix(b"]") for part in raw_parts) + b"]")
    if not payloads:
        raise ValueError("BCB SGS 12 returned no CDI observations")
    frame = pd.DataFrame(payloads)
    dates = pd.to_datetime(frame["data"], dayfirst=True, errors="coerce")
    rates = pd.to_numeric(frame["valor"].astype(str).str.replace(",", ".", regex=False), errors="coerce") / 100
    cdi = pd.Series(rates.to_numpy(), index=dates).dropna().sort_index()
    if cdi.empty or (cdi <= -1).any():
        raise ValueError("BCB SGS 12 has invalid CDI rates")
    return (100 * (1 + cdi).cumprod()).rename("TITULO_CDI")


def build_brapi_total_return(tickers: list[str], start: str | pd.Timestamp, end: str | pd.Timestamp,
                             output_path: str | Path, manifest_path: str | Path,
                             coverage_path: str | Path, raw_dir: str | Path,
                             pause_seconds: float = 0.0,
                             fetch: Callable[[str], tuple[bytes, dict]] = _download_json) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Download adjusted closes plus raw event evidence for a declared ticker set."""
    start_date, end_date = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    if end_date <= start_date:
        raise ValueError("end date must be after start date")
    normalized = sorted({_ticker_symbol(ticker) for ticker in tickers if _ticker_symbol(ticker)})
    if not normalized:
        raise ValueError("At least one B3 ticker is required")
    output, manifest_file, coverage_file, raw_root = map(Path, (output_path, manifest_path, coverage_path, raw_dir))
    raw_root.mkdir(parents=True, exist_ok=True)
    series_list: list[pd.Series] = []
    coverage: list[dict[str, object]] = []
    for number, ticker in enumerate(normalized, start=1):
        row: dict[str, object] = {"ticker": ticker + ".SA", "status": "blocked", "reason": ""}
        try:
            price_url, event_url = _historical_url(ticker), _events_url(ticker)
            raw_price, price_payload = fetch(price_url)
            raw_event, event_payload = fetch(event_url)
            _write_raw(raw_root / "historical" / f"{ticker}.json", raw_price)
            _write_raw(raw_root / "events" / f"{ticker}.json", raw_event)
            price_series, stats = _extract_price_series(price_payload, ticker + ".SA", start_date, end_date)
            if price_series.empty:
                raise ValueError("no adjustedClose in requested window")
            series_list.append(price_series)
            row.update({"status": "accepted", "historical_url": price_url, "events_url": event_url,
                        "first_date": str(price_series.index.min().date()), "last_date": str(price_series.index.max().date()),
                        **stats, **_event_counts(event_payload)})
        except Exception as exc:  # preserve every source failure for review
            row["reason"] = str(exc)
        coverage.append(row)
        if pause_seconds and number < len(normalized):
            sleep(pause_seconds)
    if not series_list:
        raise RuntimeError("brapi returned no eligible adjusted-close series")
    cdi = _fetch_cdi(start_date, end_date, raw_root / "bcb_sgs_12_cdi.json", fetch)
    prices = pd.concat(series_list + [cdi], axis=1).sort_index()
    # The B3 calendar is defined by tradeable series; CDI is carried to a B3
    # session if SGS did not publish a separate observation for that session.
    equity_dates = prices.drop(columns="TITULO_CDI", errors="ignore").dropna(how="all").index
    prices = prices.reindex(equity_dates)
    prices["TITULO_CDI"] = prices["TITULO_CDI"].ffill().bfill()
    prices = prices.reset_index(names="date")
    output.parent.mkdir(parents=True, exist_ok=True)
    coverage_file.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(output, index=False)
    coverage_frame = pd.DataFrame(coverage).sort_values("ticker")
    coverage_frame.to_csv(coverage_file, index=False)
    extracted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    accepted = int(coverage_frame.status.eq("accepted").sum())
    manifest = {
        "price_basis": "total_return",
        "source_tier": "public_reproducible_research",
        "provider": "brapi.dev /api/v2/stocks/historical adjustedClose",
        "extraction_timestamp": extracted_at,
        "coverage_start": str(pd.Timestamp(prices.date.min()).date()),
        "coverage_end": str(pd.Timestamp(prices.date.max()).date()),
        "corporate_actions": "brapi adjustedClose; raw brapi cashDividends (dividendos/JCP), stockDividends (bonificações/desdobramentos/grupamentos) and subscriptions archived per ticker",
        "cdi_source": "Banco Central do Brasil SGS 12 (CDI diário), raw response archived",
        "file_sha256": _sha256(output),
        "coverage_report": str(coverage_file),
        "raw_response_directory": str(raw_root),
        "requested_tickers": len(normalized),
        "accepted_tickers": accepted,
        "blocked_tickers": len(normalized) - accepted,
        "research_restriction": "Public reproducible source. Reconcile with first-party B3/CVM corporate-event records before institutional or commercial claims.",
    }
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    manifest_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return prices, coverage_frame, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public reproducible B3 adjusted-close total-return research input from brapi.")
    parser.add_argument("--fundamentals", required=True, help="Fundamental panel; unique tickers define the requested universe.")
    parser.add_argument("--start", default="2011-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--output", default="data/prices_brapi_adjusted_total_return_2011_2025.csv")
    parser.add_argument("--manifest", default="data/brapi_adjusted_total_return_2011_2025_manifest.json")
    parser.add_argument("--coverage-report", default="artifacts/brapi_adjusted_total_return_coverage.csv")
    parser.add_argument("--raw-dir", default="work/brapi_total_return")
    parser.add_argument("--max-tickers", type=int, help="Limit for a connection test; omitted requests every panel ticker.")
    parser.add_argument("--pause-seconds", type=float, default=0.05)
    args = parser.parse_args()
    fundamentals = pd.read_csv(args.fundamentals, dtype={"ticker": str})
    if "ticker" not in fundamentals:
        raise ValueError("Fundamental panel requires ticker column")
    tickers = sorted(fundamentals.ticker.dropna().unique())
    if args.max_tickers:
        tickers = tickers[:args.max_tickers]
    public_trial = {"PETR4.SA", "VALE3.SA", "ITUB4.SA", "MGLU3.SA"}
    if not brapi_token() and not set(tickers).issubset(public_trial):
        raise RuntimeError(
            "BRAPI_TOKEN is required for full B3 coverage. The brapi public trial permits only PETR4, VALE3, ITUB4 and MGLU3. "
            "Set BRAPI_TOKEN in .env.local or your shell; never commit it."
        )
    _, coverage, manifest = build_brapi_total_return(
        tickers, args.start, args.end, args.output, args.manifest, args.coverage_report,
        args.raw_dir, args.pause_seconds,
    )
    print(json.dumps({"accepted_tickers": int(coverage.status.eq("accepted").sum()), **manifest}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
