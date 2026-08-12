"""Immutable price-history input contract for a live Benevente proposal."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


def load_price_history(path: str | Path, decision_date: pd.Timestamp,
                       required_tickers: list[str], minimum_rows: int) -> pd.DataFrame:
    """Load a dated wide CSV and fail closed on incomplete or future data.

    Live proposals deliberately use an archived B3/broker/vendor export instead
    of downloading mutable market data at decision time.  ``TITULO_CDI`` must
    be present as a total-return index (or a daily-marked CDI sleeve) in the
    same export so the optimizer has a reproducible cash benchmark.
    """
    frame = pd.read_csv(path, parse_dates=["date"])
    required = {"date", *required_tickers}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Price history missing columns: {sorted(missing)}")
    frame = frame.loc[:, ["date", *required_tickers]].copy()
    if frame.date.isna().any() or frame.date.duplicated().any():
        raise ValueError("Price history dates must be valid and unique")
    if (frame.date > decision_date).any():
        raise ValueError("Price history contains dates after the decision date")
    frame = frame.sort_values("date").set_index("date")
    for ticker in required_tickers:
        frame[ticker] = pd.to_numeric(frame[ticker], errors="coerce")
    if frame.isna().any().any() or (frame <= 0).any().any():
        raise ValueError("Price history must contain positive, non-null prices for every required ticker")
    if len(frame) < minimum_rows + 1:
        raise ValueError(f"Price history needs at least {minimum_rows + 1} rows; received {len(frame)}")
    return frame
