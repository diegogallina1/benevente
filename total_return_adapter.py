"""Build a validated total-return input from an attributable provider export.

The project does not invent total return from unadjusted COTAHIST closes.
Instead, an official or licensed export must already contain a daily total
return index per ticker. This adapter checks that contract, joins a documented
CDI index, and preserves source metadata for annual audit artifacts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd


REQUIRED_MANIFEST = {"price_basis", "provider", "extraction_timestamp", "coverage_start", "coverage_end", "corporate_actions", "cdi_source", "file_sha256"}


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_total_return_export(prices_path: str | Path, manifest_path: str | Path) -> tuple[pd.DataFrame, dict]:
    """Validate a provider export before it becomes a performance input."""
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if missing := REQUIRED_MANIFEST - set(manifest):
        raise ValueError(f"Total-return source manifest missing fields: {sorted(missing)}")
    if manifest["price_basis"] != "total_return":
        raise ValueError("Total-return source manifest must declare price_basis=total_return")
    actual_hash = file_sha256(prices_path)
    if actual_hash != manifest["file_sha256"]:
        raise ValueError("Total-return export hash does not match its source manifest")
    prices = pd.read_csv(prices_path, parse_dates=["date"])
    if "date" not in prices or "TITULO_CDI" not in prices:
        raise ValueError("Total-return export requires date and TITULO_CDI columns")
    if prices.date.duplicated().any() or prices.date.isna().any():
        raise ValueError("Total-return export has invalid or duplicate dates")
    numeric = prices.drop(columns="date").apply(pd.to_numeric, errors="coerce")
    # A historical universe is intrinsically sparse: an IPO cannot have a
    # price before listing.  The annual engine separately requires a complete
    # pre-decision lookback for every eligible ticker.  CDI, in contrast, is
    # mandatory on every trade-date to keep the defensive allocation honest.
    if numeric.empty or numeric.drop(columns="TITULO_CDI", errors="ignore").dropna(how="all").empty:
        raise ValueError("Total-return export must contain at least one asset index")
    if numeric["TITULO_CDI"].isna().any() or (numeric["TITULO_CDI"] <= 0).any():
        raise ValueError("Total-return export must contain a complete positive TITULO_CDI index")
    assets = numeric.drop(columns="TITULO_CDI")
    if (assets.dropna(how="all") <= 0).any().any():
        raise ValueError("Total-return asset index levels must be positive where supplied")
    prices.loc[:, numeric.columns] = numeric
    return prices.sort_values("date").reset_index(drop=True), manifest
