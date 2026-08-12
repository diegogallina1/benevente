"""Point-in-time fundamental-data contract for value and quality research."""
from __future__ import annotations

from pathlib import Path
from typing import Literal
from datetime import datetime
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, model_validator


class FundamentalSnapshot(BaseModel):
    ticker: str
    as_of_date: datetime
    available_date: datetime
    sector: str
    is_financial: bool = False
    market_cap_brl: float = Field(gt=0)
    price_to_earnings: float | None = Field(default=None, gt=0)
    price_to_book: float | None = Field(default=None, gt=0)
    ev_to_ebit: float | None = Field(default=None, gt=0)
    free_cash_flow_yield: float | None = None
    roe: float | None = None
    roic: float | None = None
    debt_to_ebitda: float | None = None
    interest_coverage: float | None = None
    operating_margin: float | None = None
    revenue_growth_3y: float | None = None
    average_daily_value_brl: float = Field(gt=0)
    source: str

    @model_validator(mode="after")
    def no_future_availability(self) -> "FundamentalSnapshot":
        if self.available_date < self.as_of_date:
            raise ValueError("available_date cannot precede as_of_date")
        return self


REQUIRED_COLUMNS = set(FundamentalSnapshot.model_fields)


def load_snapshots(path: str | Path) -> list[FundamentalSnapshot]:
    """Load dated fundamentals; missing columns or invalid records fail closed."""
    frame = pd.read_csv(path, parse_dates=["as_of_date", "available_date"])
    missing = REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Fundamental file missing required columns: {sorted(missing)}")
    records = frame.replace({np.nan: None}).to_dict(orient="records")
    return [FundamentalSnapshot.model_validate(row) for row in records]


def snapshots_available_on(snapshots: list[FundamentalSnapshot], decision_date: pd.Timestamp) -> dict[str, FundamentalSnapshot]:
    """Return only the newest record published on or before the decision date."""
    eligible = [item for item in snapshots if item.available_date <= decision_date]
    latest: dict[str, FundamentalSnapshot] = {}
    for item in sorted(eligible, key=lambda value: (value.ticker, value.available_date)):
        latest[item.ticker] = item
    return latest
