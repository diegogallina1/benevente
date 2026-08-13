"""Audit trail and broker-note reconciliation for a human-approved shadow portfolio."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from datetime import date
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd


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


@dataclass(frozen=True)
class ShadowPortfolioManifest:
    """Immutable identity of a human-approved prospective observation.

    A shadow portfolio is an observation protocol, not a broker integration.
    The hashes make it possible to prove later which policy and which proposed
    orders were in force when performance tracking began.
    """
    status: str
    policy_id: str
    effective_date: str
    initial_value_brl: float
    approved_by: str
    proposed_orders_sha256: str
    policy_sha256: str
    order_count: int
    execution_mode: str = "MANUAL_OR_SIMULATOR_ONLY"
    active_fund_cnpj: str | None = None
    active_fund_name: str | None = None


def file_sha256(path: str | Path) -> str:
    """Return a content hash without interpreting or changing an input file."""
    return sha256(Path(path).read_bytes()).hexdigest()


def activate_shadow_portfolio(policy_path: str | Path, proposed_orders_path: str | Path,
                              approved_by: str, output_path: str | Path,
                              active_fund_cnpj: str | None = None,
                              active_fund_name: str | None = None) -> ShadowPortfolioManifest:
    """Freeze a reviewed proposal before any prospective performance is recorded."""
    if not approved_by or not approved_by.strip():
        raise ValueError("A named human approver is required to activate a shadow portfolio")
    if bool(active_fund_cnpj) != bool(active_fund_name):
        raise ValueError("Active-fund CNPJ and display name must be supplied together")
    if active_fund_cnpj:
        from fund_comparator import normalize_cnpj
        active_fund_cnpj = normalize_cnpj(active_fund_cnpj)
    from production_policy import load_policy

    policy = load_policy(policy_path)
    orders = pd.read_csv(proposed_orders_path)
    required = set(ProposedOrder.__annotations__)
    if missing := required - set(orders.columns):
        raise ValueError(f"Proposed-order file missing columns: {sorted(missing)}")
    if orders.empty:
        raise ValueError("A shadow portfolio requires at least one reviewed proposed order")
    decision_dates = set(orders["decision_date"].astype(str))
    if decision_dates != {str(policy.effective_date)}:
        raise ValueError("Every proposed order must use the policy effective date")
    manifest = ShadowPortfolioManifest(
        status="SHADOW_PORTFOLIO_ACTIVE",
        policy_id=policy.policy_id,
        effective_date=str(policy.effective_date),
        initial_value_brl=policy.portfolio_value_brl,
        approved_by=approved_by.strip(),
        proposed_orders_sha256=file_sha256(proposed_orders_path),
        policy_sha256=file_sha256(policy_path),
        order_count=len(orders),
        active_fund_cnpj=active_fund_cnpj,
        active_fund_name=active_fund_name.strip() if active_fund_name else None,
    )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(manifest), indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def write_order_template(path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ProposedOrder.__annotations__))
        writer.writeheader()


def write_proposed_orders(path: str | Path, orders: list[ProposedOrder]) -> None:
    """Persist proposed orders in the exact contract used for reconciliation."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ProposedOrder.__annotations__))
        writer.writeheader()
        writer.writerows(asdict(order) for order in orders)


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
