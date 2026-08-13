"""Deterministic research signals used by the allocation engine.

These rules deliberately live outside the LLM boundary.  They are a testable
numeric specification: macro inputs set a risk budget and trailing returns
produce a bounded score.  A language model may later explain these facts but
cannot supply, change, or amplify a score.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from config import SystemConfig


@dataclass(frozen=True)
class MacroRiskBudget:
    equity_allocation_cap: float
    risk_level: str
    summary: str


class DeterministicSignalEngine:
    def __init__(self, config: SystemConfig) -> None:
        self.config = config

    def macro_budget(self, selic_rate: float, ipca_rate: float) -> MacroRiskBudget:
        if selic_rate > 0.12:
            cap, risk = 0.40, "HIGH"
        elif selic_rate < 0.09:
            cap, risk = 0.80, "LOW"
        else:
            cap, risk = 0.60, "MEDIUM"
        return MacroRiskBudget(cap, risk, f"Deterministic rule: Selic {selic_rate:.1%}; IPCA {ipca_rate:.1%}.")

    def trailing_risk_adjusted_scores(self, historical_returns: pd.DataFrame) -> dict[str, float]:
        scores: dict[str, float] = {}
        for ticker in historical_returns.columns:
            if ticker == "TITULO_CDI":
                scores[ticker] = 1.0
                continue
            annual_return = (1 + historical_returns[ticker]).prod() ** (252 / len(historical_returns)) - 1
            annual_volatility = historical_returns[ticker].std(ddof=1) * np.sqrt(252)
            scores[ticker] = float(np.clip((annual_return - self.config.risk_free_rate_annual) /
                                            (2 * annual_volatility + 1e-9), -1, 1))
        return scores
