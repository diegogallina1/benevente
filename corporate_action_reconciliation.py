"""Rebuild auditable B3 total-return indices from primary corporate events.

The historical COTAHIST close is a price series, not a total-return series.  A
cash distribution changes investor wealth without appearing in that close and
a split changes the number of shares without creating an economic return.  The
functions in this module apply only explicitly recorded events and refuse to
grant the institutional source tier unless every ticker has a complete primary
coverage declaration for the requested interval.

Expected event columns
----------------------
event_id, ticker, event_type, ex_date, cash_per_old_share, share_factor,
source_url, published_at, status

``share_factor`` is new shares per old share (2.0 for a two-for-one split,
0.1 for a one-for-ten reverse split).  Cash is expressed per old share.  Event
types that require a negotiated choice or a security conversion are recorded
but deliberately not guessed; they block verification until a manual
resolution is supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
import argparse
import hashlib
import json

import numpy as np
import pandas as pd


CASH_EVENT_TYPES = {
    "dividend", "jcp", "capital_restitution", "amortization", "income"
}
SHARE_EVENT_TYPES = {"split", "reverse_split", "bonus"}
MANUAL_EVENT_TYPES = {
    "subscription", "merger", "spin_off", "ticker_change", "delisting"
}
SUPPORTED_EVENT_TYPES = CASH_EVENT_TYPES | SHARE_EVENT_TYPES | MANUAL_EVENT_TYPES
PRIMARY_HOST_SUFFIXES = ("b3.com.br", "cvm.gov.br")
REQUIRED_EVENT_COLUMNS = {
    "event_id", "ticker", "event_type", "ex_date", "cash_per_old_share",
    "share_factor", "source_url", "published_at", "status",
}
REQUIRED_COVERAGE_COLUMNS = {
    "ticker", "coverage_start", "coverage_end", "status", "source_url",
    "extracted_at",
}


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_ticker(value: object) -> str:
    return str(value).strip().upper().removesuffix(".SA")


def _is_primary_url(value: object) -> bool:
    try:
        host = (urlparse(str(value)).hostname or "").lower()
    except ValueError:
        return False
    return any(host == suffix or host.endswith("." + suffix) for suffix in PRIMARY_HOST_SUFFIXES)


@dataclass(frozen=True)
class ReconciliationAudit:
    status: str
    price_ticker_count: int
    verified_ticker_count: int
    coverage_rate: float
    applied_events: int
    unresolved_events: int
    duplicate_events: int
    invalid_events: int
    primary_sources_official: bool
    limitations: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "price_ticker_count": self.price_ticker_count,
            "verified_ticker_count": self.verified_ticker_count,
            "coverage_rate": self.coverage_rate,
            "applied_events": self.applied_events,
            "unresolved_events": self.unresolved_events,
            "duplicate_events": self.duplicate_events,
            "invalid_events": self.invalid_events,
            "primary_sources_official": self.primary_sources_official,
            "limitations": list(self.limitations),
        }


def validate_primary_records(
    events: pd.DataFrame,
    coverage: pd.DataFrame,
    price_tickers: list[str],
    coverage_start: pd.Timestamp,
    coverage_end: pd.Timestamp,
    ticker_ranges: dict[str, tuple[pd.Timestamp, pd.Timestamp]] | None = None,
) -> tuple[pd.DataFrame, ReconciliationAudit]:
    """Validate event records and the explicit no-event/complete ledger.

    An empty event file is valid only when the coverage ledger independently
    states that every ticker was checked.  This avoids the classic ambiguity
    in which no rows can mean either "no events" or "the download failed".
    """
    if missing := REQUIRED_EVENT_COLUMNS - set(events.columns):
        raise ValueError(f"Corporate-event file missing columns: {sorted(missing)}")
    if missing := REQUIRED_COVERAGE_COLUMNS - set(coverage.columns):
        raise ValueError(f"Corporate-event coverage file missing columns: {sorted(missing)}")

    checked = events.copy()
    checked["ticker"] = checked["ticker"].map(_canonical_ticker)
    checked["event_type"] = checked["event_type"].astype(str).str.strip().str.lower()
    checked["status"] = checked["status"].astype(str).str.strip().str.lower()
    checked["ex_date"] = pd.to_datetime(checked["ex_date"], errors="coerce")
    checked["published_at"] = pd.to_datetime(checked["published_at"], errors="coerce", utc=True, format="mixed")
    checked["cash_per_old_share"] = pd.to_numeric(checked["cash_per_old_share"], errors="coerce")
    checked["share_factor"] = pd.to_numeric(checked["share_factor"], errors="coerce")

    duplicates = int(checked["event_id"].duplicated(keep=False).sum())
    unsupported = ~checked["event_type"].isin(SUPPORTED_EVENT_TYPES)
    bad_common = (
        checked["event_id"].astype(str).str.strip().eq("")
        | checked["ticker"].eq("")
        | checked["ex_date"].isna()
        | checked["published_at"].isna()
        | ~checked["source_url"].map(_is_primary_url)
        | ~checked["status"].isin({"confirmed", "cancelled"})
        | unsupported
    )
    cash = checked["event_type"].isin(CASH_EVENT_TYPES)
    shares = checked["event_type"].isin(SHARE_EVENT_TYPES)
    bad_cash = cash & (checked["cash_per_old_share"].isna() | checked["cash_per_old_share"].le(0))
    bad_shares = shares & (checked["share_factor"].isna() | checked["share_factor"].le(0))
    invalid_mask = bad_common | bad_cash | bad_shares | checked["event_id"].duplicated(keep=False)

    confirmed = checked[checked["status"].eq("confirmed") & ~invalid_mask].copy()
    confirmed["resolution"] = (
        checked.loc[confirmed.index, "resolution"].fillna("").astype(str).str.strip()
        if "resolution" in checked else ""
    )
    unresolved_mask = confirmed["event_type"].isin(MANUAL_EVENT_TYPES) & confirmed["resolution"].eq("")
    unresolved = int(unresolved_mask.sum())
    applicable = confirmed[~unresolved_mask].copy()

    ledger = coverage.copy()
    ledger["ticker"] = ledger["ticker"].map(_canonical_ticker)
    ledger["coverage_start"] = pd.to_datetime(ledger["coverage_start"], errors="coerce")
    ledger["coverage_end"] = pd.to_datetime(ledger["coverage_end"], errors="coerce")
    ledger["extracted_at"] = pd.to_datetime(ledger["extracted_at"], errors="coerce", utc=True, format="mixed")
    ledger["status"] = ledger["status"].astype(str).str.strip().str.lower()
    ledger["official"] = ledger["source_url"].map(_is_primary_url)
    requested = {_canonical_ticker(item) for item in price_tickers}
    expected = {
        ticker: ticker_ranges.get(ticker, (coverage_start, coverage_end)) if ticker_ranges else (coverage_start, coverage_end)
        for ticker in requested
    }
    ledger["expected_start"] = ledger["ticker"].map(lambda ticker: expected.get(ticker, (pd.NaT, pd.NaT))[0])
    ledger["expected_end"] = ledger["ticker"].map(lambda ticker: expected.get(ticker, (pd.NaT, pd.NaT))[1])
    ledger["complete"] = (
        ledger["status"].eq("complete")
        & ledger["coverage_start"].le(ledger["expected_start"])
        & ledger["coverage_end"].ge(ledger["expected_end"])
        & ledger["extracted_at"].notna()
        & ledger["official"]
    )
    ledger = ledger.sort_values(["ticker", "coverage_end"]).drop_duplicates("ticker", keep="last")
    verified = set(ledger.loc[ledger["complete"], "ticker"]) & requested
    coverage_rate = len(verified) / len(requested) if requested else 0.0
    events_official = bool(checked.empty or checked["source_url"].map(_is_primary_url).all())
    ledger_official = bool(not ledger.empty and ledger["official"].all())
    official = events_official and ledger_official
    limitations: list[str] = []
    if coverage_rate < 1:
        limitations.append("primary_coverage_incomplete")
    if duplicates:
        limitations.append("duplicate_event_ids")
    if int(invalid_mask.sum()):
        limitations.append("invalid_event_records")
    if unresolved:
        limitations.append("manual_events_unresolved")
    if not official:
        limitations.append("non_primary_source_present")
    status = "passed" if not limitations else "blocked"
    audit = ReconciliationAudit(
        status=status,
        price_ticker_count=len(requested),
        verified_ticker_count=len(verified),
        coverage_rate=float(coverage_rate),
        applied_events=int(len(applicable)),
        unresolved_events=unresolved,
        duplicate_events=duplicates,
        invalid_events=int(invalid_mask.sum()),
        primary_sources_official=official,
        limitations=tuple(limitations),
    )
    return applicable, audit


def reconstruct_total_return(
    raw_prices: pd.DataFrame,
    events: pd.DataFrame,
    coverage: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, ReconciliationAudit]:
    """Convert a wide raw-close panel into total-return indices.

    ``raw_prices`` must contain ``date`` and may contain ``TITULO_CDI``.  The
    cash sleeve is already an accumulated index and is copied unchanged.
    Event application is strict: a confirmed event whose ex-date has no raw
    closing price is reported as unresolved rather than shifted to a guessed
    session.
    """
    if "date" not in raw_prices:
        raise ValueError("Raw-price input requires a date column")
    prices = raw_prices.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    if prices["date"].isna().any() or prices["date"].duplicated().any():
        raise ValueError("Raw-price input has invalid or duplicate dates")
    prices = prices.sort_values("date").set_index("date")
    prices.columns = [_canonical_ticker(column) if column != "TITULO_CDI" else column for column in prices.columns]
    if prices.columns.duplicated().any():
        raise ValueError("Canonical ticker conversion created duplicate price columns")
    numeric = prices.apply(pd.to_numeric, errors="coerce")
    assets = [column for column in numeric.columns if column != "TITULO_CDI"]
    if not assets:
        raise ValueError("Raw-price input has no B3 assets")
    if (numeric[assets].dropna(how="all") <= 0).any().any():
        raise ValueError("Raw closes must be positive where supplied")

    ticker_ranges = {
        ticker: (numeric[ticker].dropna().index.min(), numeric[ticker].dropna().index.max())
        for ticker in assets if not numeric[ticker].dropna().empty
    }
    applicable, audit = validate_primary_records(
        events, coverage, assets, numeric.index.min(), numeric.index.max(), ticker_ranges=ticker_ranges
    )
    output = pd.DataFrame(index=numeric.index)
    applied_rows: list[dict] = []
    missing_session_events = 0
    for ticker in assets:
        close = numeric[ticker]
        valid = close.dropna()
        level = pd.Series(np.nan, index=numeric.index, dtype=float)
        if valid.empty:
            output[ticker] = level
            continue
        ticker_events = applicable[applicable["ticker"].eq(ticker)].copy()
        event_map: dict[pd.Timestamp, tuple[float, float, list[str]]] = {}
        for ex_date, group in ticker_events.groupby("ex_date"):
            ex_date = pd.Timestamp(ex_date)
            if ex_date not in close.index or pd.isna(close.loc[ex_date]):
                missing_session_events += len(group)
                continue
            cash = float(group.loc[group["event_type"].isin(CASH_EVENT_TYPES), "cash_per_old_share"].fillna(0).sum())
            factors = group.loc[group["event_type"].isin(SHARE_EVENT_TYPES), "share_factor"].dropna()
            share_factor = float(factors.prod()) if len(factors) else 1.0
            event_map[ex_date] = (cash, share_factor, group["event_id"].astype(str).tolist())
            for item in group.itertuples(index=False):
                applied_rows.append({
                    "event_id": item.event_id,
                    "ticker": ticker,
                    "event_type": item.event_type,
                    "ex_date": ex_date.date().isoformat(),
                    "cash_per_old_share": item.cash_per_old_share,
                    "share_factor": item.share_factor,
                    "source_url": item.source_url,
                    "application_status": "applied",
                })
        first = valid.index[0]
        level.loc[first] = 100.0
        prior_date = first
        for current_date in valid.index[1:]:
            prior_close = float(close.loc[prior_date])
            current_close = float(close.loc[current_date])
            cash, share_factor, _ = event_map.get(pd.Timestamp(current_date), (0.0, 1.0, []))
            gross_factor = (current_close * share_factor + cash) / prior_close
            if not np.isfinite(gross_factor) or gross_factor <= 0:
                raise ValueError(f"Invalid total-return factor for {ticker} on {current_date.date()}")
            level.loc[current_date] = float(level.loc[prior_date]) * gross_factor
            prior_date = current_date
        output[ticker] = level
    if "TITULO_CDI" in numeric:
        output["TITULO_CDI"] = numeric["TITULO_CDI"]

    if missing_session_events:
        limitations = tuple([*audit.limitations, "event_ex_date_without_price"])
        audit = ReconciliationAudit(
            **{**audit.as_dict(), "status": "blocked", "unresolved_events": audit.unresolved_events + missing_session_events,
               "limitations": limitations}
        )
    return output.reset_index(), pd.DataFrame(applied_rows), audit


def write_reconciled_export(
    raw_prices_path: str | Path,
    events_path: str | Path,
    coverage_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path,
    applied_events_path: str | Path,
    provider: str = "B3 primary corporate-event records",
) -> dict:
    raw = pd.read_csv(raw_prices_path)
    events = pd.read_csv(events_path)
    coverage = pd.read_csv(coverage_path)
    rebuilt, applied, audit = reconstruct_total_return(raw, events, coverage)
    output = Path(output_path)
    manifest_target = Path(manifest_path)
    applied_target = Path(applied_events_path)
    for target in (output, manifest_target, applied_target):
        target.parent.mkdir(parents=True, exist_ok=True)
    rebuilt.to_csv(output, index=False)
    applied.to_csv(applied_target, index=False)
    dates = pd.to_datetime(rebuilt["date"])
    manifest = {
        "price_basis": "total_return",
        "provider": provider,
        "extraction_timestamp": str(pd.Timestamp.utcnow()),
        "coverage_start": dates.min().date().isoformat(),
        "coverage_end": dates.max().date().isoformat(),
        "corporate_actions": "explicit primary records; no price-ratio inference",
        "cdi_source": "preserved from raw input; verify its own manifest independently",
        "file_sha256": file_sha256(output),
        "source_tier": "reconciled_primary_records" if audit.status == "passed" else "partial_primary_reconciliation_research_only",
        "reconciliation": {
            **audit.as_dict(),
            "events_input_sha256": file_sha256(events_path),
            "coverage_input_sha256": file_sha256(coverage_path),
            "applied_events_sha256": file_sha256(applied_target),
        },
    }
    manifest_target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile raw B3 closes with explicit primary corporate events.")
    parser.add_argument("--raw-prices", required=True)
    parser.add_argument("--events", required=True)
    parser.add_argument("--coverage", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--applied-events", required=True)
    args = parser.parse_args()
    manifest = write_reconciled_export(
        args.raw_prices, args.events, args.coverage, args.output, args.manifest, args.applied_events
    )
    print(json.dumps(manifest["reconciliation"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
