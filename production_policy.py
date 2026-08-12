"""Investor-specific constraints required before a Benevente live proposal."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
from pydantic import BaseModel, Field, field_validator


class ProductionPolicy(BaseModel):
    policy_id: str = Field(min_length=3)
    owner: str = Field(min_length=2)
    effective_date: date
    portfolio_value_brl: float = Field(gt=0)
    horizon_years: int = Field(ge=2, le=5)
    maximum_equity_weight: float = Field(ge=0.10, le=0.80)
    maximum_asset_weight: float = Field(ge=0.05, le=0.15)
    maximum_rebalance_cost_brl: float = Field(gt=0)
    maximum_drawdown_tolerance: float = Field(ge=0.05, le=0.50)
    allow_global_b3_etfs: bool = False
    require_human_approval: bool = True
    acknowledged_not_investment_advice: bool = False

    @field_validator("horizon_years")
    @classmethod
    def accepted_horizons(cls, value: int) -> int:
        if value not in {2, 5}:
            raise ValueError("Only 2- and 5-year policies are supported")
        return value

    def validate_for_live_proposal(self) -> None:
        if not self.require_human_approval:
            raise ValueError("Live proposal workflow requires human approval")
        if not self.acknowledged_not_investment_advice:
            raise ValueError("Acknowledgement is required before a live proposal")


def load_policy(path: str | Path) -> ProductionPolicy:
    policy = ProductionPolicy.model_validate_json(Path(path).read_text(encoding="utf-8"))
    policy.validate_for_live_proposal()
    return policy

