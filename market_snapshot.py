"""Audited market-data snapshot contract for a live Benevente proposal."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd
from pydantic import BaseModel, Field


class MarketSnapshot(BaseModel):
    ticker: str
    observed_at: datetime
    market_cap_brl: float = Field(gt=0)
    average_daily_value_brl: float = Field(gt=0)
    source: str = Field(min_length=8)


def load_market_snapshots(path: str | Path, decision_date: pd.Timestamp,
                          max_age_days: int) -> dict[str, MarketSnapshot]:
    """Load one dated, attributable market snapshot per ticker.

    A production proposal intentionally does not ask a web API for an
    undocumented current value. The source (B3/vendor/broker export) is
    preserved alongside the generated proposal instead.
    """
    frame = pd.read_csv(path, parse_dates=["observed_at"])
    required = set(MarketSnapshot.model_fields)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Market snapshot missing columns: {sorted(missing)}")
    records = [MarketSnapshot.model_validate(row) for row in frame.to_dict(orient="records")]
    result: dict[str, MarketSnapshot] = {}
    for item in records:
        observed = pd.Timestamp(item.observed_at)
        if observed > decision_date:
            raise ValueError(f"Market snapshot for {item.ticker} is after the decision date")
        if (decision_date - observed).days > max_age_days:
            raise ValueError(f"Market snapshot for {item.ticker} is older than {max_age_days} days")
        if item.ticker in result:
            raise ValueError(f"Duplicate market snapshot for {item.ticker}")
        result[item.ticker] = item
    return result
