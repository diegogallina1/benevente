"""Add an official-CVM active-fund comparison curve to a shadow NAV CSV."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from fund_comparator import CvmFundDailyClient, fund_values_for_nav


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fill active_fund_value_brl from CVM fund quotes; this does not execute or recommend an investment."
    )
    parser.add_argument("--nav", required=True, help="Shadow NAV CSV without active_fund_value_brl")
    parser.add_argument("--fund-cnpj", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache-dir", default="work/cvm_fund_cache")
    args = parser.parse_args()
    nav = pd.read_csv(args.nav, parse_dates=["date"])
    required = {"date", "portfolio_value_brl"}
    if missing := required - set(nav.columns):
        raise ValueError(f"NAV file missing columns: {sorted(missing)}")
    if "active_fund_value_brl" in nav.columns and nav.active_fund_value_brl.notna().any():
        raise ValueError("NAV already has active_fund_value_brl; refuse to overwrite observed values")
    nav = nav.sort_values("date")
    fund = CvmFundDailyClient(args.cache_dir).quotes(args.fund_cnpj, nav.date.iloc[0], nav.date.iloc[-1])
    nav["active_fund_value_brl"] = fund_values_for_nav(fund, nav.date, float(nav.portfolio_value_brl.iloc[0])).to_numpy()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    nav.to_csv(output, index=False)
    print(f"CVM active-fund values written to {output}; source archives: {len(fund.source_urls)}")


if __name__ == "__main__":
    main()
