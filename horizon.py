"""Explicit mapping from investor horizon to estimation history."""
from __future__ import annotations

HORIZON_LOOKBACK_DAYS = {1: 252, 2: 504, 5: 756, 10: 1260, 15: 1260}


def estimation_window_days(horizon_years: int) -> int:
    try:
        return HORIZON_LOOKBACK_DAYS[horizon_years]
    except KeyError as exc:
        raise ValueError("Supported horizons are 1, 2, 5, 10, and 15 years") from exc
