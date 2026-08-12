"""Create a research-only proposal from a supplied fundamental snapshot file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

from config import SystemConfig
from data_loader import PointInTimeDataLoader
from horizon import estimation_window_days
from fundamentals import load_snapshots
from portfolio_recommendation import ValuePortfolioPlanner
from shadow_portfolio import write_order_template


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an auditable Benevente value/quality portfolio proposal.")
    parser.add_argument("--fundamentals", required=True, help="Point-in-time CSV with source and available_date columns.")
    parser.add_argument("--decision-date", required=True, help="Decision date in YYYY-MM-DD; only prior available data is used.")
    parser.add_argument("--horizon", type=int, choices=(1, 2, 5, 10, 15), default=5)
    parser.add_argument("--output", default="artifacts/proposals")
    args = parser.parse_args()

    config = SystemConfig()
    snapshots = load_snapshots(args.fundamentals)
    tickers = sorted({item.ticker for item in snapshots}) + ["TITULO_CDI"]
    lookback_days = estimation_window_days(args.horizon)
    config = SystemConfig(tickers=tickers, rolling_window_days=lookback_days)
    end = str((pd.Timestamp(args.decision_date) + pd.Timedelta(days=1)).date())
    start = str((pd.Timestamp(args.decision_date) - pd.DateOffset(days=lookback_days * 1.6)).date())
    prices = PointInTimeDataLoader(config).fetch_prices(start, end)
    history = prices.pct_change().dropna().tail(lookback_days)
    proposal = ValuePortfolioPlanner(config).propose(history, snapshots, pd.Timestamp(args.decision_date),
                                                     horizon_years=args.horizon)
    destination = Path(args.output) / args.decision_date
    destination.mkdir(parents=True, exist_ok=True)
    proposal.weights.rename("weight").to_csv(destination / "proposed_weights.csv")
    proposal.screen.to_csv(destination / "fundamental_screen.csv", index=False)
    (destination / "proposal_metadata.json").write_text(json.dumps({
        "decision_date": args.decision_date, "horizon_years": args.horizon, "estimation_window_trading_days": lookback_days,
        "estimated_rebalance_cost_brl": proposal.estimated_rebalance_cost_brl,
        "requires_human_approval": proposal.required_human_approval,
        "fundamental_source_file": str(Path(args.fundamentals).resolve()),
    }, indent=2), encoding="utf-8")
    write_order_template(destination / "proposed_orders.csv")
    print(f"Proposal saved to {destination}; human approval and broker-note reconciliation are required.")


if __name__ == "__main__":
    main()
