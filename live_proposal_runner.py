"""Generate a real-data Benevente proposal; it never sends broker orders."""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import json
import pandas as pd

from config import SystemConfig
from cvm_fundamentals import CvmDfpClient
from data_loader import PointInTimeDataLoader
from portfolio_recommendation import ValuePortfolioPlanner
from production_policy import load_policy
from shadow_portfolio import write_order_template


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a human-review-only Benevente live proposal from official CVM filings.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--dfp-year", type=int, required=True, help="Latest annual DFP year that was public at the decision date.")
    parser.add_argument("--decision-date", default=str(pd.Timestamp.now().date()))
    parser.add_argument("--output", default="artifacts/live_proposals")
    args = parser.parse_args()
    policy = load_policy(args.policy)
    decision_date = pd.Timestamp(args.decision_date)
    snapshots = CvmDfpClient().live_snapshots(args.dfp_year)
    # Include only assets with current, verified fundamental snapshots. ETFs/BDRs
    # enter only after their separate look-through data module is implemented.
    tickers = sorted(item.ticker for item in snapshots) + ["TITULO_CDI"]
    config = replace(SystemConfig(), tickers=tickers, initial_portfolio_value_brl=policy.portfolio_value_brl,
                     max_asset_weight=policy.maximum_asset_weight)
    prices = PointInTimeDataLoader(config).fetch_prices(
        str((decision_date - pd.DateOffset(years=2)).date()), str((decision_date + pd.Timedelta(days=1)).date()),
    )
    proposal = ValuePortfolioPlanner(config).propose(
        prices.pct_change().dropna().tail(config.rolling_window_days), snapshots, decision_date,
        horizon_years=policy.horizon_years, maximum_equity_weight=policy.maximum_equity_weight,
    )
    destination = Path(args.output) / decision_date.strftime("%Y-%m-%d")
    destination.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([item.model_dump() for item in snapshots]).to_csv(destination / "fundamentals_cvm_live.csv", index=False)
    proposal.screen.to_csv(destination / "fundamental_screen.csv", index=False)
    proposal.weights.rename("target_weight").to_csv(destination / "proposed_weights.csv")
    metadata = {
        "status": "PROPOSAL_ONLY_REQUIRES_HUMAN_APPROVAL",
        "policy_id": policy.policy_id,
        "decision_date": str(decision_date.date()),
        "dfp_year": args.dfp_year,
        "estimated_rebalance_cost_brl": proposal.estimated_rebalance_cost_brl,
        "maximum_rebalance_cost_brl": policy.maximum_rebalance_cost_brl,
        "cost_limit_passed": proposal.estimated_rebalance_cost_brl <= policy.maximum_rebalance_cost_brl,
        "execution": "No broker API or order submission is performed by this runner.",
    }
    (destination / "proposal_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_order_template(destination / "proposed_orders.csv")
    if not metadata["cost_limit_passed"]:
        raise RuntimeError("Estimated rebalance cost exceeds the policy limit; review proposal without execution.")
    print(f"Proposal saved at {destination}. Review and manually approve every order before broker entry.")


if __name__ == "__main__":
    main()

