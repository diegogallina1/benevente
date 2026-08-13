"""Freeze an approved Benevente proposal as a prospective shadow portfolio."""
from __future__ import annotations

import argparse
import json

from shadow_portfolio import activate_shadow_portfolio


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Activate a human-approved shadow portfolio; no broker or simulator order is sent."
    )
    parser.add_argument("--policy", required=True)
    parser.add_argument("--proposed-orders", required=True)
    parser.add_argument("--approved-by", required=True, help="Named human responsible for the approval")
    parser.add_argument("--active-fund-cnpj", help="Optional active fund/class CNPJ for prospective comparison")
    parser.add_argument("--active-fund-name", help="Required display name when a fund CNPJ is provided")
    parser.add_argument("--output", default="artifacts/pilot_100k/shadow_portfolio_activation.json")
    args = parser.parse_args()
    manifest = activate_shadow_portfolio(
        args.policy, args.proposed_orders, args.approved_by, args.output,
        args.active_fund_cnpj, args.active_fund_name,
    )
    print(json.dumps(manifest.__dict__, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
