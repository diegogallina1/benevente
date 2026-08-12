"""Turn approved target weights into review-only B3 order instructions."""
from __future__ import annotations

import math
import pandas as pd

from execution_costs import ClearB3CostModel
from market_snapshot import MarketSnapshot
from shadow_portfolio import ProposedOrder


def b3_symbol(ticker: str) -> str:
    return ticker.removesuffix(".SA")


def build_initial_orders(weights: pd.Series, market_data: dict[str, MarketSnapshot],
                         decision_date: pd.Timestamp, portfolio_value_brl: float,
                         max_adv_participation: float, thesis_prefix: str,
                         cost_model: ClearB3CostModel | None = None) -> tuple[list[ProposedOrder], dict[str, float]]:
    """Create buy instructions for an initial all-cash portfolio.

    This function does not place orders.  It rounds down to the declared lot,
    refuses orders over the policy's participation cap, and reports the cash
    left after estimated one-way costs.  Rebalancing an existing portfolio is
    intentionally a separate reviewed workflow rather than an implicit sell.
    """
    model = cost_model or ClearB3CostModel()
    orders: list[ProposedOrder] = []
    invested_notional = estimated_cost = 0.0
    for ticker, weight in weights.items():
        if ticker == "TITULO_CDI" or weight <= 0:
            continue
        market = market_data.get(ticker)
        if market is None:
            raise ValueError(f"No execution market snapshot for {ticker}")
        target_notional = float(weight) * portfolio_value_brl
        quantity = math.floor(target_notional / market.close_price_brl / market.lot_size) * market.lot_size
        if quantity <= 0:
            continue
        notional = quantity * market.close_price_brl
        participation = notional / market.average_daily_value_brl
        if participation > max_adv_participation:
            raise ValueError(
                f"{ticker} would use {participation:.4%} of average daily value; "
                f"policy maximum is {max_adv_participation:.4%}"
            )
        cost = model.estimate(notional, market.average_daily_value_brl).total_brl
        orders.append(ProposedOrder(
            decision_date=str(decision_date.date()), ticker=b3_symbol(ticker), side="BUY", quantity=quantity,
            limit_price_brl=market.close_price_brl, estimated_cost_brl=cost,
            thesis_id=f"{thesis_prefix}:{ticker}",
        ))
        invested_notional += notional
        estimated_cost += cost
    cash_after_orders = portfolio_value_brl - invested_notional - estimated_cost
    if cash_after_orders < -0.01:
        raise RuntimeError("Rounded orders plus estimated costs exceed portfolio value")
    return orders, {
        "portfolio_value_brl": portfolio_value_brl,
        "equity_notional_brl": invested_notional,
        "estimated_cost_brl": estimated_cost,
        "cash_after_orders_brl": max(cash_after_orders, 0.0),
        "cash_weight_after_orders": max(cash_after_orders, 0.0) / portfolio_value_brl,
    }
