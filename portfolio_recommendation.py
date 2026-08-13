"""Build an auditable long-horizon value/quality proposal, not an order."""
from __future__ import annotations

from dataclasses import dataclass, replace
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
                maximum_equity_weight: float = 0.80, maximum_asset_weight: float | None = None,
                scores_override: dict[str, float] | None = None) -> PortfolioProposal:
        if horizon_years not in {1, 2, 5, 10, 15}:
            raise ValueError("Benevente supports 1-, 2-, 5-, 10-, and 15-year investor horizons.")
        screen = ValueQualitySelector(self.config).score(snapshots, decision_date)
        if screen.empty or not screen.eligible.any():
            raise ValueError("No eligible assets. Provide complete point-in-time fundamental snapshots.")
        assets = list(historical_returns.columns)
        current_weights = current_weights.reindex(assets, fill_value=0.0) if current_weights is not None else pd.Series(0.0, index=assets)
        scores = {asset: 0.0 for asset in assets}
        for item in screen[screen.eligible].itertuples():
            scores[item.ticker] = float(2 * item.value_quality_score - 1)
        if scores_override is not None:
            # A factor experiment may change only the ranking of assets that
            # already passed the deterministic eligibility screen. It cannot
            # revive a blocked asset or alter policy constraints.
            scores.update({ticker: float(score) for ticker, score in scores_override.items() if ticker in scores})
        if "TITULO_CDI" in scores:
            scores["TITULO_CDI"] = 1.0
        optimizer_config = replace(
            self.config,
            max_asset_weight=maximum_asset_weight or self.config.max_asset_weight,
        )
        eligible_assets = set(screen.loc[screen.eligible, "ticker"])
        # Optimise only the assets that passed the dated eligibility screen
        # plus the CDI residual. Passing blocked names with a zero upper bound
        # needlessly creates a large, rank-deficient covariance matrix and
        # makes a valid constrained optimisation numerically fragile.
        optimizer_assets = [asset for asset in assets if asset == "TITULO_CDI" or asset in eligible_assets]
        optimized = MeanVarianceOptimizer(optimizer_config).optimize(
            historical_returns.loc[:, optimizer_assets],
            {asset: scores[asset] for asset in optimizer_assets},
            equity_cap=maximum_equity_weight, signal_influence=self.config.value_quality_influence,
            eligible_assets=eligible_assets,
        )
        weights = optimized.reindex(assets, fill_value=0.0)
        liquidity = screen.set_index("ticker").average_daily_value_brl.to_dict()
        portfolio_value = self.config.initial_portfolio_value_brl
        estimated_cost = sum(
            self.cost_model.estimate(portfolio_value * abs(weights[asset] - current_weights[asset]), liquidity[asset]).total_brl
            for asset in weights.index if asset != "TITULO_CDI" and asset in liquidity
        )
        return PortfolioProposal(decision_date, horizon_years, weights, screen, estimated_cost)
