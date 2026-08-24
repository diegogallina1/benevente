"""Audit whether the current B3 event archive can reproduce published holdings.

The audit is intentionally strategy-scoped.  It compares every equity
holding-year in the published 2015--2025 path with a reconstruction from raw
COTAHIST closes plus the events returned by the current B3 corporate-action
page.  A successful endpoint response is not treated as proof of historical
completeness.  Large differences block reconciliation and remain visible.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from corporate_action_reconciliation import (
    CASH_EVENT_TYPES,
    MANUAL_EVENT_TYPES,
    SHARE_EVENT_TYPES,
)


RAW_PRICES = ROOT / "data/prices_b3_cotahist_price_return_only_2011_2025.csv"
EVENTS = ROOT / "data/b3_primary_corporate_events_2011_2025.csv"
COVERAGE = ROOT / "data/b3_primary_event_coverage_2011_2025.csv"
EVENT_MANIFEST = ROOT / "data/b3_primary_events_2011_2025_manifest.json"
HOLDINGS = ROOT / "artifacts/published_nested/annual_holdings.csv"
ANNUAL = ROOT / "artifacts/published_nested/annual_results.csv"
OUT_DIR = ROOT / "artifacts/primary_reconciliation"
DETAIL = OUT_DIR / "strategy_holding_year_audit.csv"
SUMMARY = OUT_DIR / "summary.json"
MATERIAL_DIFFERENCE = 0.05


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1_048_576), b""):
            digest.update(block)
    return digest.hexdigest()


def endpoint_return(
    close: pd.Series,
    events: pd.DataFrame,
) -> tuple[float, int, int]:
    """Rebuild one holding period from raw closes and archived B3 events."""
    valid = pd.to_numeric(close, errors="coerce").dropna()
    if len(valid) < 2:
        raise ValueError("holding period has fewer than two raw closes")
    event_map: dict[pd.Timestamp, tuple[float, float]] = {}
    missing_session_events = 0
    applied_events = 0
    for ex_date, group in events.groupby("ex_date"):
        date = pd.Timestamp(ex_date)
        if date not in valid.index:
            missing_session_events += len(group)
            continue
        cash = float(
            pd.to_numeric(
                group.loc[group.event_type.isin(CASH_EVENT_TYPES), "cash_per_old_share"],
                errors="coerce",
            ).fillna(0).sum()
        )
        factors = pd.to_numeric(
            group.loc[group.event_type.isin(SHARE_EVENT_TYPES), "share_factor"],
            errors="coerce",
        ).dropna()
        factor = float(factors.prod()) if len(factors) else 1.0
        event_map[date] = (cash, factor)
        applied_events += len(group)
    level = 1.0
    prior_date = valid.index[0]
    for date in valid.index[1:]:
        cash, factor = event_map.get(pd.Timestamp(date), (0.0, 1.0))
        gross = (float(valid.loc[date]) * factor + cash) / float(valid.loc[prior_date])
        if not np.isfinite(gross) or gross <= 0:
            raise ValueError(f"invalid reconstruction factor on {date:%Y-%m-%d}")
        level *= gross
        prior_date = date
    return level - 1.0, applied_events, missing_session_events


def build() -> dict:
    prices = pd.read_csv(RAW_PRICES)
    prices["date"] = pd.to_datetime(prices["date"], errors="raise")
    prices = prices.set_index("date")
    events = pd.read_csv(EVENTS)
    events["ticker"] = events.ticker.astype(str).str.upper().str.removesuffix(".SA")
    events["ex_date"] = pd.to_datetime(events.ex_date, errors="coerce")
    events["status"] = events.status.astype(str).str.lower()
    coverage = pd.read_csv(COVERAGE)
    coverage["ticker"] = coverage.ticker.astype(str).str.upper().str.removesuffix(".SA")
    coverage["status"] = coverage.status.astype(str).str.lower()
    coverage = coverage.sort_values(["ticker", "extracted_at"]).drop_duplicates("ticker", keep="last")
    endpoint_queried = set(
        coverage.loc[
            coverage.status.isin({"complete", "queried_current_endpoint"}), "ticker"
        ]
    )
    annual = pd.read_csv(ANNUAL).set_index("decision_year")
    holdings = pd.read_csv(HOLDINGS)
    holdings = holdings[(holdings.weight > 0) & holdings.ticker.ne("TITULO_CDI")].copy()
    holdings["ticker_symbol"] = holdings.ticker.str.replace(".SA", "", regex=False)

    rows: list[dict] = []
    for holding in holdings.itertuples(index=False):
        period = annual.loc[int(holding.decision_year)]
        start = pd.Timestamp(period.decision_date)
        end = pd.Timestamp(period.holding_end_exclusive)
        symbol = holding.ticker_symbol
        source_column = holding.ticker
        period_events = events[
            events.ticker.eq(symbol)
            & events.status.eq("confirmed")
            & events.ex_date.ge(start)
            & events.ex_date.lt(end)
        ].copy()
        manual = period_events[period_events.event_type.isin(MANUAL_EVENT_TYPES)]
        status = "compared_current_endpoint"
        reconstructed = np.nan
        applied = 0
        missing_sessions = 0
        note = ""
        if symbol not in endpoint_queried:
            status = "blocked_endpoint_not_queried"
            note = "The current B3 company-supplement endpoint did not return this issuer."
        elif not manual.empty:
            status = "blocked_manual_event_during_holding"
            note = "A subscription or security conversion overlaps the holding period."
        elif source_column not in prices:
            status = "blocked_raw_close_missing"
            note = "The raw COTAHIST panel does not contain the published ticker."
        else:
            close = prices.loc[(prices.index >= start) & (prices.index < end), source_column]
            applicable = period_events[
                period_events.event_type.isin(CASH_EVENT_TYPES | SHARE_EVENT_TYPES)
            ]
            reconstructed, applied, missing_sessions = endpoint_return(close, applicable)
            if missing_sessions:
                status = "blocked_event_without_raw_session"
                note = "At least one archived event could not be joined to a raw trading session."
        published = float(holding.realised_next_year_return)
        difference = reconstructed - published if np.isfinite(reconstructed) else np.nan
        material = bool(np.isfinite(difference) and abs(difference) > MATERIAL_DIFFERENCE)
        if material:
            status = "blocked_material_difference"
            note = (
                "The current endpoint archive does not reproduce the published adjusted return; "
                "this indicates an incomplete event history or a definition mismatch."
            )
        rows.append({
            "decision_year": int(holding.decision_year),
            "ticker": symbol,
            "portfolio_weight": float(holding.weight),
            "holding_start": start.date().isoformat(),
            "holding_end_exclusive": end.date().isoformat(),
            "endpoint_archive_status": status,
            "endpoint_reconstructed_return": reconstructed,
            "published_adjusted_return": published,
            "difference": difference,
            "absolute_difference": abs(difference) if np.isfinite(difference) else np.nan,
            "material_difference_over_5pp": material,
            "events_applied": applied,
            "manual_events_during_holding": int(len(manual)),
            "events_without_raw_session": int(missing_sessions),
            "note": note,
        })

    detail = pd.DataFrame(rows)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    detail.to_csv(DETAIL, index=False)
    compared = detail[detail.endpoint_reconstructed_return.notna()]
    blocked_endpoint = detail.endpoint_archive_status.eq("blocked_endpoint_not_queried")
    material = detail.material_difference_over_5pp
    total_equity_weight = float(detail.portfolio_weight.sum())
    event_manifest = json.loads(EVENT_MANIFEST.read_text(encoding="utf-8"))
    summary = {
        "status": "blocked_not_institutionally_reconciled",
        "scope": "published Benevente 1 equity holding-years, 2015-2025",
        "holding_year_records": int(len(detail)),
        "distinct_published_tickers": int(detail.ticker.nunique()),
        "current_endpoint_compared_records": int(len(compared)),
        "current_endpoint_unavailable_records": int(blocked_endpoint.sum()),
        "manual_events_overlapping_actual_holds": int(detail.manual_events_during_holding.sum()),
        "material_differences_over_5pp": int(material.sum()),
        "median_absolute_difference": float(compared.absolute_difference.median()),
        "weighted_mean_absolute_difference": float(
            np.average(compared.absolute_difference, weights=compared.portfolio_weight)
        ),
        "endpoint_unavailable_share_of_equity_weight_years": float(
            detail.loc[blocked_endpoint, "portfolio_weight"].sum() / total_equity_weight
        ),
        "material_difference_share_of_equity_weight_years": float(
            detail.loc[material, "portfolio_weight"].sum() / total_equity_weight
        ),
        "current_b3_endpoint_archive": {
            "records": int(event_manifest["event_count"]),
            "price_series_queried": int(
                event_manifest.get("ticker_count_endpoint_queried", 475)
            ),
            "price_series_requested": int(event_manifest["ticker_count_requested"]),
            "manual_events_unresolved": int(event_manifest["unresolved_manual_event_count"]),
        },
        "interpretation": (
            "The current B3 page is useful primary evidence but is not a complete historical "
            "corporate-action ledger. It cannot reproduce every published holding return, so the "
            "provider-adjusted performance panel remains research-grade and no institutional "
            "reconciliation seal is granted."
        ),
        "material_difference_threshold": MATERIAL_DIFFERENCE,
        "inputs": {
            str(path.relative_to(ROOT)).replace("\\", "/"): sha256(path)
            for path in (RAW_PRICES, EVENTS, COVERAGE, EVENT_MANIFEST, HOLDINGS, ANNUAL)
        },
    }
    summary["detail_sha256"] = sha256(DETAIL)
    SUMMARY.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, ensure_ascii=False))
