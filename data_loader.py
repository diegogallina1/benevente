"""Point-in-time market-data ingestion with an explicit deterministic fallback."""
from __future__ import annotations

import numpy as np
import pandas as pd
from config import SystemConfig


class PointInTimeDataLoader:
    def __init__(self, config: SystemConfig) -> None:
        self.config = config

    def fetch_prices(self, start_date: str, end_date: str, offline: bool = False) -> pd.DataFrame:
        equities = [ticker for ticker in self.config.tickers if ticker != "TITULO_CDI"]
        prices: pd.DataFrame
        if offline:
            prices = self._synthetic_prices(equities, start_date, end_date)
        else:
            try:
                import yfinance as yf
                raw = yf.download(equities, start=start_date, end=end_date, auto_adjust=True,
                                  progress=False, group_by="column")
                prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
                if isinstance(prices, pd.Series):
                    prices = prices.to_frame(equities[0])
                prices = prices.reindex(columns=equities).ffill().dropna(how="any")
                if prices.empty:
                    raise ValueError("yfinance returned no complete price rows")
            except Exception as exc:
                print(f"[WARN] Market download unavailable ({exc}); using deterministic synthetic data.")
                prices = self._synthetic_prices(equities, start_date, end_date)

        # No backward fill: a missing quote is never filled with future information.
        daily_cdi = (1 + self.config.risk_free_rate_annual) ** (1 / 252) - 1
        prices["TITULO_CDI"] = 100 * np.cumprod(np.full(len(prices), 1 + daily_cdi))
        return prices.sort_index()

    @staticmethod
    def _synthetic_prices(tickers: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        dates = pd.date_range(start_date, end_date, freq="B")
        rng = np.random.default_rng(2026)
        common = rng.normal(0.00035, 0.008, len(dates))[:, None]
        noise = rng.normal(0.00005, 0.012, (len(dates), len(tickers)))
        return pd.DataFrame(100 * np.cumprod(1 + common + noise, axis=0), index=dates, columns=tickers)

