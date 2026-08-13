"""Explicit, dated investable-universe contracts.

The small lists below are UI defaults only.  A claim that a backtest covers
"all B3 assets" requires a dated, attributable constituent file -- B3 market
data and over-the-counter fixed-income inventories are not safely inferred from
today's tickers.  ``load_universe_snapshot`` is the import gate for that file.
"""
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class AssetMetadata:
    ticker: str
    asset_class: str
    region: str
    sector: str
    is_financial: bool = False


UNIVERSE_REQUIRED_COLUMNS = {"ticker", "asset_class", "observed_at", "source", "active"}
SUPPORTED_ASSET_CLASSES = {"equity", "etf", "bdr", "fii", "fixed_income", "cash_equivalent"}


def load_universe_snapshot(path: str | Path | pd.DataFrame, decision_date: pd.Timestamp) -> pd.DataFrame:
    """Load a point-in-time B3/broker/vendor universe without inventing coverage.

    A row must identify its source and observation time.  Inactive instruments,
    observations after the decision date and unsupported asset classes are
    rejected.  Fixed income may be represented by an ISIN instead of a ticker.
    Pricing, liquidity and suitability remain separate gates.
    """
    frame = path.copy() if isinstance(path, pd.DataFrame) else pd.read_csv(path)
    missing = UNIVERSE_REQUIRED_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Universe snapshot missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["observed_at"] = pd.to_datetime(frame["observed_at"], errors="coerce")
    if frame[["ticker", "asset_class", "observed_at", "source"]].isna().any().any():
        raise ValueError("Universe snapshot has missing ticker, class, observation time or source")
    if (frame["observed_at"] > pd.Timestamp(decision_date)).any():
        raise ValueError("Universe snapshot contains information after the decision date")
    frame["asset_class"] = frame["asset_class"].astype(str).str.lower().str.strip()
    unsupported = sorted(set(frame["asset_class"]) - SUPPORTED_ASSET_CLASSES)
    if unsupported:
        raise ValueError(f"Unsupported asset classes: {unsupported}")
    frame["active"] = frame["active"].astype(str).str.lower().isin({"1", "true", "yes", "sim"})
    frame["ticker"] = frame["ticker"].astype(str).str.upper().str.strip()
    active = frame.loc[frame["active"]].sort_values(["ticker", "observed_at"]).drop_duplicates("ticker", keep="last")
    if active.empty:
        raise ValueError("Universe snapshot contains no active instruments")
    return active.reset_index(drop=True)


BRAZIL_VALUE_UNIVERSE = [
    AssetMetadata("PETR4.SA", "equity", "Brazil", "Energy"),
    AssetMetadata("VALE3.SA", "equity", "Brazil", "Materials"),
    AssetMetadata("ITUB4.SA", "equity", "Brazil", "Financials", True),
    AssetMetadata("BBDC4.SA", "equity", "Brazil", "Financials", True),
    AssetMetadata("BBAS3.SA", "equity", "Brazil", "Financials", True),
    AssetMetadata("ABEV3.SA", "equity", "Brazil", "Consumer Staples"),
    AssetMetadata("WEGE3.SA", "equity", "Brazil", "Industrials"),
    AssetMetadata("RENT3.SA", "equity", "Brazil", "Industrials"),
]

# Global exposure traded locally. Validate listings/liquidity for every live run.
B3_GLOBAL_ETF_UNIVERSE = [
    AssetMetadata("IVVB11.SA", "etf", "United States", "Broad market"),
    AssetMetadata("NASD11.SA", "etf", "United States", "Technology"),
    AssetMetadata("ACWI11.SA", "etf", "Global", "Broad market"),
    AssetMetadata("EURP11.SA", "etf", "Europe", "Broad market"),
]
