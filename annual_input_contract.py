"""Validate annual walk-forward inputs before any performance calculation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import pandas as pd


@dataclass(frozen=True)
class AnnualInputManifest:
    price_basis: str
    performance_permitted: bool
    status: str
    reasons: tuple[str, ...]
    first_price_date: str | None
    last_price_date: str | None
    price_tickers: int
    fundamental_snapshots: int

    def as_dict(self) -> dict:
        return {
            "price_basis": self.price_basis,
            "performance_permitted": self.performance_permitted,
            "status": self.status,
            "reasons": list(self.reasons),
            "first_price_date": self.first_price_date,
            "last_price_date": self.last_price_date,
            "price_tickers": self.price_tickers,
            "fundamental_snapshots": self.fundamental_snapshots,
        }


def validate_annual_inputs(prices: pd.DataFrame, fundamentals: pd.DataFrame, price_basis: str) -> AnnualInputManifest:
    """Return an explicit go/no-go for calculating historical performance."""
    if price_basis not in {"total_return", "price_return_only"}:
        raise ValueError("price_basis must be total_return or price_return_only")
    reasons: list[str] = []
    if "date" not in prices.columns:
        reasons.append("missing_price_date")
        dates = pd.Series(dtype="datetime64[ns]")
    else:
        dates = pd.to_datetime(prices.date, errors="coerce")
        if dates.isna().any() or dates.duplicated().any():
            reasons.append("invalid_or_duplicate_price_dates")
    if "TITULO_CDI" not in prices.columns:
        reasons.append("missing_cdi_total_return_index")
    if price_basis == "price_return_only":
        reasons.append("price_return_only_excludes_dividends_jcp_and_corporate_actions")
    if fundamentals.empty:
        reasons.append("missing_fundamental_snapshots")
    permitted = not reasons
    return AnnualInputManifest(
        price_basis=price_basis, performance_permitted=permitted,
        status="ready_for_performance" if permitted else "blocked_before_performance",
        reasons=tuple(reasons),
        first_price_date=None if dates.empty else str(dates.min().date()),
        last_price_date=None if dates.empty else str(dates.max().date()),
        price_tickers=max(len(prices.columns) - (1 if "date" in prices.columns else 0), 0),
        fundamental_snapshots=int(len(fundamentals)),
    )


def write_manifest(path: str | Path, manifest: AnnualInputManifest) -> None:
    Path(path).write_text(json.dumps(manifest.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
