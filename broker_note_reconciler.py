"""Reconcile a reviewed Benevente order file against a manually exported broker note."""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from shadow_portfolio import ExecutedOrder, ProposedOrder, reconcile


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile proposed Benevente orders and a broker-note export; no orders are sent.")
    parser.add_argument("--proposed-orders", required=True)
    parser.add_argument("--executions", required=True,
                        help="CSV: broker_note_id,execution_date,ticker,side,quantity,execution_price_brl,broker_fees_brl")
    parser.add_argument("--output", default="artifacts/reconciliation.csv")
    args = parser.parse_args()
    proposed = pd.read_csv(args.proposed_orders)
    executed = pd.read_csv(args.executions)
    proposal_columns = set(ProposedOrder.__annotations__)
    execution_columns = set(ExecutedOrder.__annotations__)
    if missing := proposal_columns - set(proposed.columns):
        raise ValueError(f"Proposed-order file missing columns: {sorted(missing)}")
    if missing := execution_columns - set(executed.columns):
        raise ValueError(f"Execution file missing columns: {sorted(missing)}")
    if proposed.empty or executed.empty:
        raise ValueError("Both proposed orders and executions must have at least one row")
    proposed_records = [ProposedOrder(**row) for row in proposed.where(pd.notna(proposed), None).to_dict("records")]
    execution_records = [ExecutedOrder(**row) for row in executed.to_dict("records")]
    if len(proposed_records) != len(execution_records):
        raise ValueError("Order and execution row counts differ; reconcile partial fills manually before importing")
    reports = [reconcile(order, fill) for order, fill in zip(proposed_records, execution_records, strict=True)]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(reports).to_csv(output, index=False)
    print(f"Reconciliation written to {output}")


if __name__ == "__main__":
    main()
