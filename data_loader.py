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
                raise RuntimeError(
                    "Real B3 data download failed. Use --offline only for deterministic tests; "
                    "do not silently substitute synthetic data in empirical research."
                ) from exc

        if offline:
            daily_cdi = (1 + self.config.risk_free_rate_annual) ** (1 / 252) - 1
            cdi_returns = pd.Series(daily_cdi, index=prices.index)
        else:
            cdi_returns = self.fetch_cdi_returns(start_date, end_date).reindex(prices.index).ffill()
            if cdi_returns.isna().any():
                raise ValueError("CDI series has missing values on B3 trading dates.")
        prices["TITULO_CDI"] = 100 * (1 + cdi_returns).cumprod()
        return prices.sort_index()

    def fetch_ibovespa(self, start_date: str, end_date: str) -> pd.Series:
        import yfinance as yf
        raw = yf.download("^BVSP", start=start_date, end=end_date, auto_adjust=True, progress=False)
        close = raw["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        if close.empty:
            raise ValueError("No Ibovespa prices returned by yfinance.")
        return close.rename("IBOVESPA")

    def fetch_cdi_returns(self, start_date: str, end_date: str) -> pd.Series:
        """Return the BCB SGS 12 CDI daily rate as a decimal daily return."""
        from bcb import sgs
        cdi = sgs.get({"cdi": self.config.cdi_bcb_series}, start=start_date, end=end_date)["cdi"]
        return (cdi / 100).rename("CDI_RETURN")

    def fetch_macro_data(self, start_date: str, end_date: str) -> pd.DataFrame:
        """BCB macro series; callers must use observations dated no later than T-1."""
        from bcb import sgs
        macro = sgs.get({"selic": self.config.selic_bcb_series, "ipca": self.config.ipca_bcb_series},
                        start=start_date, end=end_date)
        macro["selic"] = macro["selic"] / 100
        macro["ipca"] = macro["ipca"] / 100
        return macro

    @staticmethod
    def _synthetic_prices(tickers: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        dates = pd.date_range(start_date, end_date, freq="B")
        rng = np.random.default_rng(2026)
        common = rng.normal(0.00035, 0.008, len(dates))[:, None]
        noise = rng.normal(0.00005, 0.012, (len(dates), len(tickers)))
        return pd.DataFrame(100 * np.cumprod(1 + common + noise, axis=0), index=dates, columns=tickers)
