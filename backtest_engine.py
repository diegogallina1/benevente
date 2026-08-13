from __future__ import annotations
import numpy as np
import pandas as pd
from config import SystemConfig
from execution_costs import ClearB3CostModel
from fundamentals import FundamentalSnapshot
from optimizer import MeanVarianceOptimizer
from signals import DeterministicSignalEngine
from value_quality import ValueQualitySelector


class BacktestEngine:
    def __init__(self, prices: pd.DataFrame, config: SystemConfig) -> None:
        self.prices, self.config = prices, config

    def run(self, macro_data: pd.DataFrame | None = None, use_signals: bool = True,
            equity_cap: float = 0.60, fundamental_snapshots: list[FundamentalSnapshot] | None = None,
            cost_model: ClearB3CostModel | None = None) -> pd.DataFrame:
        returns = self.prices.pct_change().dropna()
        signals, optimizer = DeterministicSignalEngine(self.config), MeanVarianceOptimizer(self.config)
        value_selector = ValueQualitySelector(self.config) if fundamental_snapshots else None
        previous = pd.Series(1 / len(returns.columns), index=returns.columns)
        wealth, rows = self.config.initial_wealth, []
        for end in range(self.config.rolling_window_days, len(returns) - self.config.rebalance_days, self.config.rebalance_days):
            history = returns.iloc[end - self.config.rolling_window_days:end]  # Through T-1 only.
            if macro_data is not None:
                observed = macro_data.loc[:returns.index[end - 1]].ffill().iloc[-1]
                macro = signals.macro_budget(float(observed.selic), float(observed.ipca) if pd.notna(observed.ipca) else 0.0)
            else:
                macro = signals.macro_budget(self.config.risk_free_rate_annual, 0.0)
            scores = signals.trailing_risk_adjusted_scores(history)
            eligible_assets = None
            liquidity: dict[str, float] = {}
            if value_selector is not None:
                fundamental_scores = value_selector.score(fundamental_snapshots, returns.index[end - 1])
                eligible_assets = set(fundamental_scores.loc[fundamental_scores["eligible"], "ticker"])
                liquidity = fundamental_scores.set_index("ticker")["average_daily_value_brl"].to_dict()
                # The fundamental signal is available only once its snapshot is published.
                for _, item in fundamental_scores.set_index("ticker").iterrows():
                    if item["eligible"]:
                        scores[item.name] = float(np.clip(2 * item.value_quality_score - 1, -1, 1))
            if not use_signals:
                scores = dict.fromkeys(scores, 0.0)
            target = optimizer.optimize(history, scores, macro.equity_allocation_cap if use_signals else equity_cap,
                                        signal_influence=self.config.signal_alpha_influence if use_signals else 0.0,
                                        eligible_assets=eligible_assets)
            turnover = float((target - previous).abs().sum())
            weights = target if turnover >= self.config.rebalance_threshold else previous
            period = returns.iloc[end:end + self.config.rebalance_days]
            gross = float((1 + period @ weights).prod() - 1)
            if weights.equals(target) and cost_model is not None:
                portfolio_value_brl = self.config.initial_portfolio_value_brl * wealth / self.config.initial_wealth
                friction_brl = sum(
                    cost_model.estimate(portfolio_value_brl * abs(target[asset] - previous[asset]), liquidity.get(asset, portfolio_value_brl)).total_brl
                    for asset in target.index if asset != "TITULO_CDI"
                )
                friction = friction_brl / portfolio_value_brl
            else:
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
