"""Build an auditable long-horizon value/quality proposal, not an order."""
from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
from config import SystemConfig
from execution_costs import ClearB3CostModel
from fundamentals import FundamentalSnapshot
from optimizer import MeanVarianceOptimizer
from value_quality import ValueQualitySelector


@dataclass(frozen=True)
class PortfolioProposal:
    decision_date: pd.Timestamp
    horizon_years: int
    weights: pd.Series
    screen: pd.DataFrame
    estimated_rebalance_cost_brl: float
    required_human_approval: bool = True


class ValuePortfolioPlanner:
    def __init__(self, config: SystemConfig, cost_model: ClearB3CostModel | None = None) -> None:
        self.config = config
        self.cost_model = cost_model or ClearB3CostModel()

    def propose(self, historical_returns: pd.DataFrame, snapshots: list[FundamentalSnapshot], decision_date: pd.Timestamp,
                current_weights: pd.Series | None = None, horizon_years: int = 5,
                maximum_equity_weight: float = 0.80) -> PortfolioProposal:
        if horizon_years not in {2, 5}:
            raise ValueError("Benevente value proposals currently support 2- or 5-year horizons.")
        screen = ValueQualitySelector(self.config).score(snapshots, decision_date)
        if screen.empty or not screen.eligible.any():
            raise ValueError("No eligible assets. Provide complete point-in-time fundamental snapshots.")
        assets = list(historical_returns.columns)
        current_weights = current_weights.reindex(assets, fill_value=0.0) if current_weights is not None else pd.Series(0.0, index=assets)
        scores = {asset: 0.0 for asset in assets}
        for item in screen[screen.eligible].itertuples():
            scores[item.ticker] = float(2 * item.value_quality_score - 1)
        if "TITULO_CDI" in scores:
            scores["TITULO_CDI"] = 1.0
        weights = MeanVarianceOptimizer(self.config).optimize(
            historical_returns, scores, equity_cap=maximum_equity_weight, influence=self.config.value_quality_influence,
            eligible_assets=set(screen.loc[screen.eligible, "ticker"]),
        )
        liquidity = screen.set_index("ticker").average_daily_value_brl.to_dict()
        portfolio_value = self.config.initial_portfolio_value_brl
        estimated_cost = sum(
            self.cost_model.estimate(portfolio_value * abs(weights[asset] - current_weights[asset]), liquidity[asset]).total_brl
            for asset in weights.index if asset != "TITULO_CDI" and asset in liquidity
        )
        return PortfolioProposal(decision_date, horizon_years, weights, screen, estimated_cost)
