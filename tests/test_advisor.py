import pandas as pd
import pytest

from advisor import build_proposal, candidate_memo, demo_snapshots, returns_from_price_frame
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from production_policy import ProductionPolicy


def policy(profile: str = "moderate") -> ProductionPolicy:
    kwargs = {}
    if profile == "custom":
        kwargs = {"maximum_equity_weight": .60, "maximum_asset_weight": .12,
                  "maximum_drawdown_tolerance": .30, "review_interval_months": 6}
    return ProductionPolicy(policy_id="advisor-test", owner="Reviewer", effective_date="2026-08-12",
                            portfolio_value_brl=100_000, risk_profile=profile, horizon_years=5,
                            maximum_rebalance_cost_brl=500, acknowledged_not_investment_advice=True, **kwargs)


def test_advisor_demo_generates_constrained_human_review_proposal():
    date = pd.Timestamp("2026-08-12")
    prices = PointInTimeDataLoader(SystemConfig()).fetch_prices("2020-08-01", "2026-08-13", offline=True)
    proposal, metrics = build_proposal(policy(), date, prices, demo_snapshots(date))
    assert proposal.required_human_approval
    assert proposal.weights.sum() == pytest.approx(1.0)
    assert proposal.weights.drop("TITULO_CDI").sum() <= .55 + 1e-8
    assert not proposal.screen.loc[proposal.screen.ticker.eq("RENT3.SA"), "eligible"].iloc[0]
    assert set(metrics) >= {"model_historical_sharpe", "cdi_historical_annual_return", "equity_weight"}
    memo = candidate_memo(proposal)
    assert set(memo) >= {"ticker", "status", "target_weight", "why", "how", "next_review"}
    assert memo.loc[memo.ticker.eq("RENT3.SA"), "status"].item() == "Bloqueado"
    assert memo.loc[memo.ticker.eq("TITULO_CDI"), "why"].item().startswith("Reserva residual")


def test_advisor_requires_cdi_and_enough_history():
    prices = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=20), "PETR4.SA": range(20)})
    with pytest.raises(ValueError, match="TITULO_CDI"):
        returns_from_price_frame(prices, pd.Timestamp("2026-08-12"), 1)


def test_custom_policy_supports_explicit_constraints():
    assert policy("custom").maximum_equity_weight == pytest.approx(.60)
