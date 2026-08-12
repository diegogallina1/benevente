from __future__ import annotations
import numpy as np
import pandas as pd
from config import SystemConfig
from llm_agents import MockLLMAgents
from optimizer import MeanVarianceOptimizer


class BacktestEngine:
    def __init__(self, prices: pd.DataFrame, config: SystemConfig) -> None:
        self.prices, self.config = prices, config

    def run(self, macro_data: pd.DataFrame | None = None, use_signals: bool = True,
            equity_cap: float = 0.60) -> pd.DataFrame:
        returns = self.prices.pct_change().dropna()
        agents, optimizer = MockLLMAgents(self.config), MeanVarianceOptimizer(self.config)
        previous = pd.Series(1 / len(returns.columns), index=returns.columns)
        wealth, rows = self.config.initial_wealth, []
        for end in range(self.config.rolling_window_days, len(returns) - self.config.rebalance_days, self.config.rebalance_days):
            history = returns.iloc[end - self.config.rolling_window_days:end]  # Through T-1 only.
            if macro_data is not None:
                observed = macro_data.loc[:returns.index[end - 1]].ffill().iloc[-1]
                macro = agents.macro(float(observed.selic), float(observed.ipca) if pd.notna(observed.ipca) else 0.0)
            else:
                macro = agents.macro(self.config.risk_free_rate_annual, 0.0)
            selection = agents.select(history)
            scores = {x.ticker: x.confidence_score for x in selection.scores}
            if not use_signals:
                scores = dict.fromkeys(scores, 0.0)
            target = optimizer.optimize(history, scores, macro.equity_allocation_cap if use_signals else equity_cap,
                                        influence=self.config.llm_alpha_influence if use_signals else 0.0)
            turnover = float((target - previous).abs().sum())
            weights = target if turnover >= self.config.rebalance_threshold else previous
            period = returns.iloc[end:end + self.config.rebalance_days]
            gross = float((1 + period @ weights).prod() - 1)
            friction = (self.config.transaction_cost + self.config.slippage) * (turnover if weights.equals(target) else 0.0)
            net = gross - friction
            wealth *= 1 + net
            rows.append({"date": returns.index[end], "wealth": wealth, "gross_return": gross, "net_return": net,
                         "turnover": turnover if weights.equals(target) else 0.0, "friction_cost": friction,
                         "equity_cap": macro.equity_allocation_cap if use_signals else equity_cap})
            # Drift weights to their post-period values before the next decision.
            growth = (1 + period).prod()
            previous = (weights * growth) / float((weights * growth).sum())
        return pd.DataFrame(rows)

    @staticmethod
    def metrics(results: pd.DataFrame, risk_free_annual: float) -> dict[str, float]:
        if results.empty:
            raise ValueError("No backtest periods; extend the data range.")
        monthly = results.net_return
        years = len(monthly) / 12
        cagr = (results.wealth.iloc[-1] / 100) ** (1 / years) - 1
        vol = float(monthly.std(ddof=1) * np.sqrt(12))
        drawdown = results.wealth / results.wealth.cummax() - 1
        return {"cumulative_return": float(results.wealth.iloc[-1] / 100 - 1), "cagr": float(cagr),
                "annual_volatility": vol, "sharpe": float((cagr - risk_free_annual) / (vol + 1e-9)),
                "max_drawdown": float(drawdown.min()), "average_turnover": float(results.turnover.mean())}
