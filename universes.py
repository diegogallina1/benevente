"""Explicit investable universes.

Tickers are configuration defaults, not historical index memberships. Historical
research must supply dated constituent files to eliminate survivorship bias.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class AssetMetadata:
    ticker: str
    asset_class: str
    region: str
    sector: str
    is_financial: bool = False


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

