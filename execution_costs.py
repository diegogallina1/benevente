"""Transparent cost model for Clear/B3 regular equity and ETF trades.

Rates are versioned defaults from Clear's published swing-trade schedule and
B3's regular-trade table, as retrieved on 2026-08-12. Reconcile every live
order against the broker note; never assume a historic schedule was unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeCost:
    notional_brl: float
    clear_brokerage_brl: float
    b3_fees_brl: float
    estimated_slippage_brl: float

    @property
    def total_brl(self) -> float:
        return self.clear_brokerage_brl + self.b3_fees_brl + self.estimated_slippage_brl


@dataclass(frozen=True)
class ClearB3CostModel:
    """Regular B3 trade: Clear brokerage zero, B3 fees 0.0300% in base tier."""
    b3_regular_fee_rate: float = 0.000300
    clear_brokerage_rate: float = 0.0
    slippage_bps_floor: float = 5.0
    participation_impact_bps: float = 10.0
    effective_from: str = "2026-08-12"
    source_clear: str = "https://corretora.clear.com.br/custos/"
    source_b3: str = "https://www.b3.com.br/main.jsp?lumA=1&lumII=8A80CB81633FBF0B01634039ECCF714B&lumPageId=8A68812D556EB213015572DE4B3A77DC"

    def estimate(self, notional_brl: float, average_daily_value_brl: float) -> TradeCost:
        if notional_brl < 0 or average_daily_value_brl <= 0:
            raise ValueError("notional_brl must be non-negative and average_daily_value_brl must be positive")
        participation = notional_brl / average_daily_value_brl
        slippage_rate = (self.slippage_bps_floor + self.participation_impact_bps * participation ** 0.5) / 10_000
        return TradeCost(notional_brl, notional_brl * self.clear_brokerage_rate,
                         notional_brl * self.b3_regular_fee_rate, notional_brl * slippage_rate)

