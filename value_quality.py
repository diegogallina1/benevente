"""Deterministic value/quality selection layer.

Hard filters keep distressed or illiquid securities out. Ranking happens only
among eligible assets and is independent of the LLM narrative layer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from config import SystemConfig
from fundamentals import FundamentalSnapshot, snapshots_available_on


class ValueQualitySelector:
    def __init__(self, config: SystemConfig) -> None:
        self.config = config

    def screen(self, snapshots: list[FundamentalSnapshot], decision_date: pd.Timestamp) -> pd.DataFrame:
        current = snapshots_available_on(snapshots, decision_date)
        rows = []
        for ticker, item in current.items():
            reasons: list[str] = []
            if item.market_cap_brl < self.config.min_market_cap_brl:
                reasons.append("market_cap")
            if item.average_daily_value_brl <= 0:
                reasons.append("liquidity")
            if item.is_financial:
                if item.roe is None or item.roe < self.config.min_roe:
                    reasons.append("roe")
                if item.price_to_book is None or item.price_to_book <= 0:
                    reasons.append("price_to_book")
            else:
                if item.free_cash_flow_yield is None or item.free_cash_flow_yield < self.config.min_free_cash_flow_yield:
                    reasons.append("free_cash_flow_yield")
                if item.roic is None or item.roic < self.config.min_roic:
                    reasons.append("roic")
                if item.debt_to_ebitda is None or item.debt_to_ebitda > self.config.max_debt_to_ebitda:
                    reasons.append("debt_to_ebitda")
                if item.interest_coverage is None or item.interest_coverage < self.config.min_interest_coverage:
                    reasons.append("interest_coverage")
            rows.append({**item.model_dump(), "eligible": not reasons, "rejection_reasons": ",".join(reasons)})
        columns = [*FundamentalSnapshot.model_fields, "eligible", "rejection_reasons"]
        return pd.DataFrame(rows, columns=columns)

    def score(self, snapshots: list[FundamentalSnapshot], decision_date: pd.Timestamp) -> pd.DataFrame:
        frame = self.screen(snapshots, decision_date)
        if frame.empty:
            return frame
        eligible = frame[frame.eligible].copy()
        if eligible.empty:
            frame["value_quality_score"] = 0.0
            return frame
        # Percentile scores avoid arbitrary cross-sectional scaling.
        eligible["earnings_yield"] = 1 / eligible.price_to_earnings.fillna(np.inf)
        eligible["book_yield"] = 1 / eligible.price_to_book.fillna(np.inf)
        for column, ascending in (("free_cash_flow_yield", True), ("earnings_yield", True), ("book_yield", True),
                                  ("roe", True), ("roic", True), ("operating_margin", True),
                                  ("debt_to_ebitda", False)):
            eligible[f"rank_{column}"] = eligible[column].fillna(eligible[column].median()).rank(pct=True, ascending=ascending)
        rank_columns = [column for column in eligible if column.startswith("rank_")]
        eligible["value_quality_score"] = eligible[rank_columns].mean(axis=1)
        frame = frame.merge(eligible[["ticker", "value_quality_score"]], on="ticker", how="left")
        frame["value_quality_score"] = frame.value_quality_score.fillna(0.0)
        return frame.sort_values(["eligible", "value_quality_score"], ascending=[False, False])
