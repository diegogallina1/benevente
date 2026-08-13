"""Track the prospective R$100k shadow portfolio without broker execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

from production_policy import ProductionPolicy
from shadow_portfolio import ShadowPortfolioManifest


REQUIRED_NAV_COLUMNS = {"date", "portfolio_value_brl", "cdi_value_brl", "ibovespa_value_brl", "notes"}
ACTIVE_FUND_NAV_COLUMN = "active_fund_value_brl"


def build_performance(policy: ProductionPolicy, nav: pd.DataFrame,
                      activation: ShadowPortfolioManifest | None = None) -> tuple[pd.DataFrame, dict]:
    missing = REQUIRED_NAV_COLUMNS - set(nav.columns)
    if missing:
        raise ValueError(f"NAV file missing columns: {sorted(missing)}")
    frame = nav.copy()
    # The template exposes an optional active-fund column. An entirely blank
    # column means ``no fund comparison`` rather than an invalid observation.
    if ACTIVE_FUND_NAV_COLUMN in frame.columns and frame[ACTIVE_FUND_NAV_COLUMN].isna().all():
        frame = frame.drop(columns=[ACTIVE_FUND_NAV_COLUMN])
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date")
    if frame.date.duplicated().any() or frame.empty:
        raise ValueError("NAV dates must be unique and non-empty")
    if frame.date.iloc[0].date() != policy.effective_date:
        raise ValueError("First NAV row must equal the policy effective date")
    if activation is not None:
        if activation.status != "SHADOW_PORTFOLIO_ACTIVE":
            raise ValueError("Shadow portfolio activation is not active")
        if activation.policy_id != policy.policy_id:
            raise ValueError("Shadow portfolio activation belongs to a different policy")
        if activation.effective_date != str(policy.effective_date):
            raise ValueError("Shadow portfolio activation has a different effective date")
        if abs(activation.initial_value_brl - policy.portfolio_value_brl) > 0.01:
            raise ValueError("Shadow portfolio activation has a different initial value")
        if activation.active_fund_cnpj and ACTIVE_FUND_NAV_COLUMN not in frame.columns:
            raise ValueError("The activated active-fund comparison requires active_fund_value_brl in the NAV file")
    for column in ("portfolio_value_brl", "cdi_value_brl", "ibovespa_value_brl"):
        frame[column] = pd.to_numeric(frame[column])
        if (frame[column] <= 0).any():
            raise ValueError(f"{column} must remain positive")
        frame[f"{column}_return"] = frame[column] / frame[column].iloc[0] - 1
    if ACTIVE_FUND_NAV_COLUMN in frame.columns:
        frame[ACTIVE_FUND_NAV_COLUMN] = pd.to_numeric(frame[ACTIVE_FUND_NAV_COLUMN])
        if (frame[ACTIVE_FUND_NAV_COLUMN] <= 0).any() or frame[ACTIVE_FUND_NAV_COLUMN].isna().any():
            raise ValueError(f"{ACTIVE_FUND_NAV_COLUMN} must remain positive and complete")
        frame[f"{ACTIVE_FUND_NAV_COLUMN}_return"] = (
            frame[ACTIVE_FUND_NAV_COLUMN] / frame[ACTIVE_FUND_NAV_COLUMN].iloc[0] - 1
        )
    running_peak = frame.portfolio_value_brl.cummax()
    frame["portfolio_drawdown"] = frame.portfolio_value_brl / running_peak - 1
    latest = frame.iloc[-1]
    summary = {
        "status": "SHADOW_PORTFOLIO_ACTIVE" if activation else "SHADOW_PORTFOLIO_DRAFT",
        "policy_id": policy.policy_id,
        "initial_value_brl": policy.portfolio_value_brl,
        "latest_date": str(latest["date"].date()),
        "latest_value_brl": float(latest["portfolio_value_brl"]),
        "portfolio_return": float(latest["portfolio_value_brl_return"]),
        "cdi_return": float(latest["cdi_value_brl_return"]),
        "ibovespa_return": float(latest["ibovespa_value_brl_return"]),
        "maximum_drawdown": float(frame.portfolio_drawdown.min()),
        "observation_count": int(len(frame)),
        "note": "Prospective tracking only; no return is guaranteed or inferred from this file.",
    }
    if ACTIVE_FUND_NAV_COLUMN in frame.columns:
        summary["active_fund_return"] = float(latest[f"{ACTIVE_FUND_NAV_COLUMN}_return"])
    if activation is not None:
        summary.update({
            "approved_by": activation.approved_by,
            "proposed_orders_sha256": activation.proposed_orders_sha256,
            "policy_sha256": activation.policy_sha256,
            "order_count": activation.order_count,
            "execution_mode": activation.execution_mode,
        })
        if activation.active_fund_cnpj:
            summary["active_fund_cnpj"] = activation.active_fund_cnpj
            summary["active_fund_name"] = activation.active_fund_name
    return frame, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Update a Benevente prospective shadow-portfolio report.")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--nav", required=True)
    parser.add_argument("--activation", help="shadow_portfolio_activation.json created after human approval")
    parser.add_argument("--output", default="artifacts/pilot_100k")
    args = parser.parse_args()
    policy = ProductionPolicy.model_validate_json(Path(args.policy).read_text(encoding="utf-8"))
    activation = (ShadowPortfolioManifest(**json.loads(Path(args.activation).read_text(encoding="utf-8")))
                  if args.activation else None)
    frame, summary = build_performance(policy, pd.read_csv(args.nav), activation)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "pilot_performance.csv", index=False)
    (output / "pilot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
