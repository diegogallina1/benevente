"""Verified supplementary solvency metrics for non-financial issuers."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import pandas as pd
from pydantic import BaseModel, Field

from fundamentals import FundamentalSnapshot


class QualityMetricOverride(BaseModel):
    ticker: str
    observed_at: datetime
    debt_to_ebitda: float = Field(ge=0)
    interest_coverage: float = Field(ge=0)
    source: str = Field(min_length=8)


def load_quality_metric_overrides(path: str | Path, decision_date: pd.Timestamp,
                                  max_age_days: int) -> dict[str, QualityMetricOverride]:
    frame = pd.read_csv(path, parse_dates=["observed_at"])
    required = set(QualityMetricOverride.model_fields)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Quality-metrics file missing columns: {sorted(missing)}")
    result: dict[str, QualityMetricOverride] = {}
    for record in frame.to_dict(orient="records"):
        item = QualityMetricOverride.model_validate(record)
        observed_at = pd.Timestamp(item.observed_at)
        if observed_at > decision_date:
            raise ValueError(f"Quality metrics for {item.ticker} are after the decision date")
        if (decision_date - observed_at).days > max_age_days:
            raise ValueError(f"Quality metrics for {item.ticker} are older than {max_age_days} days")
        if item.ticker in result:
            raise ValueError(f"Duplicate quality metrics for {item.ticker}")
        result[item.ticker] = item
    return result


def apply_quality_metric_overrides(snapshots: list[FundamentalSnapshot],
                                   overrides: dict[str, QualityMetricOverride]) -> list[FundamentalSnapshot]:
    """Attach attributable metrics; missing data remains missing and fails closed."""
    updated: list[FundamentalSnapshot] = []
    for snapshot in snapshots:
        override = overrides.get(snapshot.ticker)
        if override is None or snapshot.is_financial:
            updated.append(snapshot)
            continue
        updated.append(snapshot.model_copy(update={
            "debt_to_ebitda": override.debt_to_ebitda,
            "interest_coverage": override.interest_coverage,
            "source": f"{snapshot.source}; solvency metrics: {override.source}",
        }))
    return updated
