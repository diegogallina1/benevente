"""Audit trail and broker-note reconciliation for a human-approved shadow portfolio."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from datetime import date
from pathlib import Path


@dataclass(frozen=True)
class ProposedOrder:
    decision_date: str
    ticker: str
    side: str
    quantity: int
    limit_price_brl: float
    estimated_cost_brl: float
    thesis_id: str
    approved_by: str | None = None


@dataclass(frozen=True)
class ExecutedOrder:
    broker_note_id: str
    execution_date: str
    ticker: str
    side: str
    quantity: int
    execution_price_brl: float
    broker_fees_brl: float


def write_order_template(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ProposedOrder.__annotations__))
        writer.writeheader()


def reconcile(proposal: ProposedOrder, execution: ExecutedOrder) -> dict[str, float | str]:
    if proposal.ticker != execution.ticker or proposal.side != execution.side:
        raise ValueError("Broker-note execution does not match proposed order")
    estimated_notional = proposal.quantity * proposal.limit_price_brl
    actual_notional = execution.quantity * execution.execution_price_brl
    return {
        "ticker": proposal.ticker,
        "broker_note_id": execution.broker_note_id,
        "estimated_notional_brl": estimated_notional,
        "actual_notional_brl": actual_notional,
        "execution_slippage_brl": actual_notional - estimated_notional if proposal.side == "BUY" else estimated_notional - actual_notional,
        "estimated_cost_brl": proposal.estimated_cost_brl,
        "actual_broker_fees_brl": execution.broker_fees_brl,
        "cost_estimation_error_brl": execution.broker_fees_brl - proposal.estimated_cost_brl,
    }

