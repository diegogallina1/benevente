from __future__ import annotations
import cvxpy as cp
import numpy as np
import pandas as pd
from config import SystemConfig


class MeanVarianceOptimizer:
    def __init__(self, config: SystemConfig) -> None:
        self.config = config

    def optimize(self, historical_returns: pd.DataFrame, scores: dict[str, float], equity_cap: float,
                 signal_influence: float | None = None, eligible_assets: set[str] | None = None,
                 previous_weights: pd.Series | None = None, turnover_penalty: float = 0.0,
                 minimum_selected_weight: float = 0.0) -> pd.Series:
        assets = list(historical_returns.columns)
        n = len(assets)
        mu = historical_returns.mean().to_numpy() * 252
        confidence = np.array([scores[a] for a in assets])
        influence = self.config.signal_alpha_influence if signal_influence is None else signal_influence
        mu = mu * (1 + influence * confidence)
        covariance = historical_returns.cov().to_numpy() * 252 + np.eye(n) * 1e-7
        w = cp.Variable(n)
        equity_indices = [i for i, asset in enumerate(assets) if asset != "TITULO_CDI"]
        # CDI is the residual/cash sleeve. Applying the 15% issuer cap to it
        # makes the stated 60% equity cap infeasible (at most 75% invested).
        upper_bounds = np.array([
            1.0 if asset == "TITULO_CDI" else self.config.max_asset_weight if eligible_assets is None or asset in eligible_assets else 0.0
            for asset in assets
        ])
        lower_bounds = np.array([
            0.0 if asset == "TITULO_CDI" or eligible_assets is None or asset not in eligible_assets else minimum_selected_weight
            for asset in assets
        ])
        if np.any(lower_bounds > upper_bounds):
            raise ValueError("Minimum selected weight exceeds an asset upper bound.")
        constraints = [cp.sum(w) == 1, w >= lower_bounds, w <= upper_bounds,
                       cp.sum(w[equity_indices]) <= equity_cap]
        previous = (previous_weights.reindex(assets, fill_value=0.0).to_numpy()
                    if previous_weights is not None else np.zeros(n))
        objective = cp.Maximize(
            mu @ w - (self.config.risk_aversion_gamma / 2) * cp.quad_form(w, covariance)
            - max(0.0, turnover_penalty) * cp.norm1(w - previous)
        )
        problem = cp.Problem(objective, constraints)
        problem.solve(solver=cp.CLARABEL)
        if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or w.value is None:
            raise RuntimeError(f"Optimization failed: {problem.status}")
        return pd.Series(np.maximum(w.value, 0), index=assets).div(np.maximum(w.value, 0).sum())
