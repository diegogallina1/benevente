"""Investor policy with profile defaults and advanced explicit constraints."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator


RiskProfile = Literal["conservative", "moderate", "growth", "aggressive", "custom"]
HORIZONS = {1, 2, 5, 10, 15}
PROFILE_DEFAULTS = {
    "conservative": {"maximum_equity_weight": 0.35, "maximum_asset_weight": 0.10,
                     "maximum_drawdown_tolerance": 0.15, "review_interval_months": 3},
    "moderate": {"maximum_equity_weight": 0.55, "maximum_asset_weight": 0.12,
                 "maximum_drawdown_tolerance": 0.22, "review_interval_months": 3},
    "growth": {"maximum_equity_weight": 0.70, "maximum_asset_weight": 0.15,
               "maximum_drawdown_tolerance": 0.30, "review_interval_months": 6},
    "aggressive": {"maximum_equity_weight": 0.80, "maximum_asset_weight": 0.15,
                   "maximum_drawdown_tolerance": 0.40, "review_interval_months": 6},
}


class ProductionPolicy(BaseModel):
    policy_id: str = Field(min_length=3)
    owner: str = Field(min_length=2)
    effective_date: date
    portfolio_value_brl: float = Field(gt=0)
    risk_profile: RiskProfile = "moderate"
    horizon_years: int = Field(ge=1, le=15)
    maximum_equity_weight: float | None = Field(default=None, ge=0.10, le=0.80)
    maximum_asset_weight: float | None = Field(default=None, ge=0.05, le=0.15)
    maximum_rebalance_cost_brl: float = Field(gt=0)
    maximum_drawdown_tolerance: float | None = Field(default=None, ge=0.05, le=0.50)
    review_interval_months: int | None = Field(default=None, ge=1, le=12)
    max_fundamental_age_days: int = Field(default=120, ge=1, le=365)
    allow_global_b3_etfs: bool = False
    excluded_tickers: list[str] = Field(default_factory=list)
    require_human_approval: bool = True
    acknowledged_not_investment_advice: bool = False

    @model_validator(mode="after")
    def apply_profile_and_validate(self) -> "ProductionPolicy":
        if self.horizon_years not in HORIZONS:
            raise ValueError("Supported horizons are 1, 2, 5, 10, and 15 years")
        if self.risk_profile == "custom":
            if any(value is None for value in (self.maximum_equity_weight, self.maximum_asset_weight,
                                                self.maximum_drawdown_tolerance, self.review_interval_months)):
                raise ValueError("Custom policy requires all advanced risk constraints")
        else:
            defaults = PROFILE_DEFAULTS[self.risk_profile]
            for name, value in defaults.items():
                if getattr(self, name) is None:
                    setattr(self, name, value)
        if self.maximum_asset_weight > self.maximum_equity_weight:
            raise ValueError("maximum_asset_weight cannot exceed maximum_equity_weight")
        return self

    def validate_for_live_proposal(self) -> None:
        if not self.require_human_approval:
            raise ValueError("Live proposal workflow requires human approval")
        if not self.acknowledged_not_investment_advice:
            raise ValueError("Acknowledgement is required before a live proposal")


def load_policy(path: str | Path) -> ProductionPolicy:
    policy = ProductionPolicy.model_validate_json(Path(path).read_text(encoding="utf-8"))
    policy.validate_for_live_proposal()
    return policy
