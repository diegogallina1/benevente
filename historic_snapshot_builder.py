"""Build a January-by-January CVM point-in-time fundamental panel.

The builder deliberately starts in January 2012 when using CVM's public ITR
archive: a January 2011 decision cannot know filings from 2011.  Each row of
the market and quality panels is dated and attributable, so the walk-forward
engine never replaces old market values with today's values.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from cvm_fundamentals import BRAZIL_ISSUERS, Issuer
from cvm_itr import CvmItrClient
from market_snapshot import MarketSnapshot
from quality_metrics import QualityMetricOverride, apply_quality_metric_overrides


MARKET_COLUMNS = {"decision_date", *MarketSnapshot.model_fields}
QUALITY_COLUMNS = {"decision_date", *QualityMetricOverride.model_fields}


def _latest_market_rows(panel: pd.DataFrame, decision: pd.Timestamp, max_age_days: int,
                        issuers: tuple[Issuer, ...] = BRAZIL_ISSUERS) -> dict[str, MarketSnapshot]:
    rows: dict[str, MarketSnapshot] = {}
    for ticker in (issuer.ticker for issuer in issuers):
        # A January backtest must use the market-cap snapshot made for that
        # same January decision.  Reusing the previous year's cap would make
        # liquidity/concentration inputs stale even though it is technically
        # in the past, so it is an explicit coverage failure instead.
        candidates = panel[(panel.ticker == ticker) & (panel.decision_date == decision)].sort_values("observed_at")
        if candidates.empty:
            raise ValueError(f"No market snapshot for {ticker} at {decision.date()}")
        record = MarketSnapshot.model_validate(candidates.iloc[-1].to_dict())
        if (decision - pd.Timestamp(record.observed_at)).days > max_age_days:
            raise ValueError(f"Market snapshot for {ticker} is older than {max_age_days} days at {decision.date()}")
        rows[ticker] = record
    return rows


def _latest_quality_rows(panel: pd.DataFrame | None, decision: pd.Timestamp,
                         max_age_days: int) -> dict[str, QualityMetricOverride]:
    if panel is None:
        return {}
    rows: dict[str, QualityMetricOverride] = {}
    for ticker in panel.ticker.unique():
        candidates = panel[(panel.ticker == ticker) & (panel.observed_at <= decision)].sort_values("observed_at")
        if candidates.empty:
            continue
        record = QualityMetricOverride.model_validate(candidates.iloc[-1].to_dict())
        if (decision - pd.Timestamp(record.observed_at)).days <= max_age_days:
            rows[ticker] = record
    return rows


def build_historical_snapshots(market_panel: pd.DataFrame, start_year: int, end_year: int,
                               quality_panel: pd.DataFrame | None = None,
                               max_age_days: int = 31,
                               client: CvmItrClient | None = None) -> pd.DataFrame:
    """Return one archived-CVM snapshot per issuer and January decision year.

    ``end_year`` is inclusive. The caller supplies historical market-cap and
    trading-value observations rather than calculating them from current data.
    """
    if start_year < 2012:
        raise ValueError("CVM-public ITR January walk-forward begins in 2012; January 2011 needs a separate pre-2011 vendor archive.")
    missing = MARKET_COLUMNS - set(market_panel.columns)
    if missing:
        raise ValueError(f"Market panel missing columns: {sorted(missing)}")
    market = market_panel.copy()
    market["decision_date"] = pd.to_datetime(market.decision_date)
    market["observed_at"] = pd.to_datetime(market.observed_at)
    quality = None
    if quality_panel is not None:
        missing_quality = QUALITY_COLUMNS - set(quality_panel.columns)
        if missing_quality:
            raise ValueError(f"Quality panel missing columns: {sorted(missing_quality)}")
        quality = quality_panel.copy(); quality["observed_at"] = pd.to_datetime(quality.observed_at)
    itr = client or CvmItrClient()
    output: list[dict] = []
    coverage: list[dict] = []
    for year in range(start_year, end_year + 1):
        decision = pd.Timestamp(year=year, month=1, day=1)
        # Use the filing calendar year immediately before the January decision.
        covered: list[Issuer] = []
        market_rows: dict[str, MarketSnapshot] = {}
        for issuer in BRAZIL_ISSUERS:
            try:
                market_rows.update(_latest_market_rows(market, decision, max_age_days, (issuer,)))
                covered.append(issuer)
            except Exception as exc:
                coverage.append({"decision_date": decision.date().isoformat(), "ticker": issuer.ticker,
                                 "status": "blocked", "reason": str(exc)})
        if not covered:
            continue
        quality_rows = _latest_quality_rows(quality, decision, max_age_days)
        for issuer in covered:
            try:
                # Build per issuer so one historical taxonomy gap cannot turn
                # into an all-or-nothing year. Every rejection is recorded.
                snapshots = itr.live_snapshots(year - 1, decision, {issuer.ticker: market_rows[issuer.ticker]}, issuers=(issuer,))
                snapshots = apply_quality_metric_overrides(snapshots, quality_rows)
                for snapshot in snapshots:
                    row = snapshot.model_dump()
                    row["decision_date"] = decision.date().isoformat()
                    row["snapshot_vintage"] = "CVM ITR/DFP available at January decision"
                    output.append(row)
                coverage.append({"decision_date": decision.date().isoformat(), "ticker": issuer.ticker,
                                 "status": "accepted", "reason": ""})
            except Exception as exc:
                coverage.append({"decision_date": decision.date().isoformat(), "ticker": issuer.ticker,
                                 "status": "blocked", "reason": str(exc)})
        if isinstance(itr, CvmItrClient):
            itr.clear_cached_panels()
    result = pd.DataFrame(output)
    result.attrs["coverage"] = pd.DataFrame(coverage)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dated January CVM fundamental snapshots for annual walk-forward.")
    parser.add_argument("--market-panel", required=True, help="CSV with decision_date plus MarketSnapshot fields.")
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--quality-panel", help="Optional CSV with decision_date plus QualityMetricOverride fields.")
    parser.add_argument("--max-age-days", type=int, default=31)
    parser.add_argument("--output", default="data/fundamentals_cvm_january_panel.csv")
    parser.add_argument("--coverage-report", default="artifacts/historic_fundamental_coverage.csv")
    args = parser.parse_args()
    quality = pd.read_csv(args.quality_panel) if args.quality_panel else None
    snapshots = build_historical_snapshots(pd.read_csv(args.market_panel), args.start_year, args.end_year,
                                           quality, args.max_age_days)
    destination, coverage_report = Path(args.output), Path(args.coverage_report)
    destination.parent.mkdir(parents=True, exist_ok=True); coverage_report.parent.mkdir(parents=True, exist_ok=True)
    snapshots.to_csv(destination, index=False)
    snapshots.attrs["coverage"].to_csv(coverage_report, index=False)
    print(f"Wrote {len(snapshots)} dated snapshots to {destination}; coverage: {coverage_report}")


if __name__ == "__main__":
    main()
