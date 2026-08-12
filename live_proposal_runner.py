"""Generate a real-data Benevente proposal; it never sends broker orders."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import json
import pandas as pd

from config import SystemConfig
from cvm_itr import CvmItrClient
from horizon import estimation_window_days
from market_snapshot import load_market_snapshots
from order_builder import build_initial_orders
from portfolio_recommendation import ValuePortfolioPlanner
from production_policy import load_policy
from price_history import load_price_history
from quality_metrics import apply_quality_metric_overrides, load_quality_metric_overrides
from shadow_portfolio import write_proposed_orders


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a human-review-only Benevente live proposal from CVM ITR/DFP TTM data.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--itr-year", type=int, required=True, help="ITR calendar year with filings available by the decision date.")
    parser.add_argument("--market-snapshot", required=True, help="Dated CSV from B3, broker, or licensed market-data vendor.")
    parser.add_argument("--price-history", required=True, help="Archived dated price-history CSV from B3, broker, or licensed vendor.")
    parser.add_argument("--price-history-source", required=True, help="Source and export reference for the archived price history.")
    parser.add_argument("--quality-metrics", help="Optional dated, attributable debt/interest metrics for non-financial issuers.")
    parser.add_argument("--decision-date", default=str(pd.Timestamp.now().date()))
    parser.add_argument("--output", default="artifacts/live_proposals")
    args = parser.parse_args()
    policy = load_policy(args.policy)
    decision_date = pd.Timestamp(args.decision_date)
    market_data = load_market_snapshots(args.market_snapshot, decision_date, policy.max_fundamental_age_days)
    snapshots = CvmItrClient().live_snapshots(args.itr_year, decision_date, market_data)
    if args.quality_metrics:
        snapshots = apply_quality_metric_overrides(
            snapshots, load_quality_metric_overrides(args.quality_metrics, decision_date, policy.max_fundamental_age_days)
        )
    excluded = set(policy.excluded_tickers)
    snapshots = [item for item in snapshots if item.ticker not in excluded]
    market_data = {ticker: item for ticker, item in market_data.items() if ticker not in excluded}
    if not snapshots:
        raise RuntimeError("All issuers were excluded by policy.")
    oldest = min(item.available_date for item in snapshots)
    if (decision_date - pd.Timestamp(oldest)).days > policy.max_fundamental_age_days:
        raise RuntimeError("At least one ITR is older than the policy freshness limit.")
    # Include only assets with current, verified fundamental snapshots. ETFs/BDRs
    # enter only after their separate look-through data module is implemented.
    tickers = sorted(item.ticker for item in snapshots) + ["TITULO_CDI"]
    lookback_days = estimation_window_days(policy.horizon_years)
    config = replace(SystemConfig(), tickers=tickers, initial_portfolio_value_brl=policy.portfolio_value_brl,
                     max_asset_weight=policy.maximum_asset_weight, rolling_window_days=lookback_days)
    prices = load_price_history(args.price_history, decision_date, tickers, lookback_days)
    proposal = ValuePortfolioPlanner(config).propose(
        prices.pct_change().dropna().tail(config.rolling_window_days), snapshots, decision_date,
        horizon_years=policy.horizon_years, maximum_equity_weight=policy.maximum_equity_weight,
    )
    destination = Path(args.output) / decision_date.strftime("%Y-%m-%d")
    destination.mkdir(parents=True, exist_ok=True)
    pd.read_csv(args.market_snapshot).to_csv(destination / "market_snapshot.csv", index=False)
    pd.DataFrame([item.model_dump() for item in snapshots]).to_csv(destination / "fundamentals_cvm_live.csv", index=False)
    proposal.screen.to_csv(destination / "fundamental_screen.csv", index=False)
    proposal.weights.rename("target_weight").to_csv(destination / "proposed_weights.csv")
    orders, order_summary = build_initial_orders(
        proposal.weights, market_data, decision_date, policy.portfolio_value_brl,
        config.max_position_adv_participation, policy.policy_id,
    )
    actual_cost_limit_passed = order_summary["estimated_cost_brl"] <= policy.maximum_rebalance_cost_brl
    metadata = {
        "status": "PROPOSAL_ONLY_REQUIRES_HUMAN_APPROVAL",
        "policy_id": policy.policy_id,
        "decision_date": str(decision_date.date()),
        "itr_year": args.itr_year,
        "ttm_base_dfp_year": args.itr_year - 1,
        "risk_profile": policy.risk_profile,
        "horizon_years": policy.horizon_years,
        "review_interval_months": policy.review_interval_months,
        "estimation_window_trading_days": lookback_days,
        "excluded_tickers": sorted(excluded),
        "fundamental_freshness_days": (decision_date - pd.Timestamp(oldest)).days,
        "estimated_rebalance_cost_brl": proposal.estimated_rebalance_cost_brl,
        "estimated_initial_order_cost_brl": order_summary["estimated_cost_brl"],
        "maximum_rebalance_cost_brl": policy.maximum_rebalance_cost_brl,
        "cost_limit_passed": actual_cost_limit_passed,
        "price_history_source": args.price_history_source,
        "execution": "No broker API or order submission is performed by this runner.",
    }
    if not metadata["cost_limit_passed"]:
        raise RuntimeError("Estimated initial order cost exceeds the policy limit; no proposal package was issued.")
    write_proposed_orders(destination / "proposed_orders.csv", orders)
    pd.DataFrame([order_summary]).to_csv(destination / "order_summary.csv", index=False)
    pd.read_csv(args.price_history).to_csv(destination / "price_history.csv", index=False)
    if args.quality_metrics:
        pd.read_csv(args.quality_metrics).to_csv(destination / "quality_metrics.csv", index=False)
    (destination / "proposal_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    report = "\n".join([
        "# Benevente Wealth System — proposal for human review", "",
        f"- Policy: `{policy.policy_id}`", f"- Decision date: `{decision_date.date()}`",
        f"- Horizon: {policy.horizon_years} years; estimation window: {lookback_days} trading days.",
        f"- Proposed B3 buy instructions: {len(orders)}; residual cash: R$ {order_summary['cash_after_orders_brl']:,.2f}.",
        "- Status: proposal only. A reviewer must approve each row before manual entry at the broker.",
        "- After execution, reconcile broker-note prices and fees against `proposed_orders.csv`; no automatic trading is enabled.", "",
    ])
    (destination / "proposal_report.md").write_text(report, encoding="utf-8")
    print(f"Proposal saved at {destination}. Review and manually approve every order before broker entry.")


if __name__ == "__main__":
    main()
