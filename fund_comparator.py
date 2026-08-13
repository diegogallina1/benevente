"""Compare Benevente research with active funds using official CVM daily reports.

Fund quotes are public, dated net-asset-value records. They support a historical
comparison, not a recommendation or an investability claim: every fund has its
own mandate, fees, taxes, eligibility and liquidity terms.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
import re

import numpy as np
import pandas as pd


CVM_INF_DIARIO_ROOT = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS"
IDENTIFIER_COLUMNS = (
    "CNPJ_FUNDO_CLASSE_COTA", "CNPJ_FUNDO_COTA", "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO",
)


def normalize_cnpj(value: str) -> str:
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 14:
        raise ValueError("CNPJ must contain exactly 14 digits")
    return digits


def format_cnpj(value: str) -> str:
    digits = normalize_cnpj(value)
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


@dataclass(frozen=True)
class FundQuoteSeries:
    cnpj: str
    quotes: pd.Series
    source_urls: tuple[str, ...]


class CvmFundDailyClient:
    """Download and cache only the requested fund rows from CVM archives."""
    def __init__(self, cache_dir: str | Path = "work/cvm_fund_cache") -> None:
        self.cache_dir = Path(cache_dir)

    @staticmethod
    def archive_urls(start: pd.Timestamp, end: pd.Timestamp) -> list[str]:
        months = pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")
        urls: list[str] = []
        for period in months:
            if period.year <= 2020:
                url = f"{CVM_INF_DIARIO_ROOT}/HIST/inf_diario_fi_{period.year}.zip"
                if url not in urls:
                    urls.append(url)
            else:
                urls.append(f"{CVM_INF_DIARIO_ROOT}/inf_diario_fi_{period.year}{period.month:02d}.zip")
        return urls

    def _archive(self, url: str) -> Path:
        import requests

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / url.rsplit("/", maxsplit=1)[-1]
        if not path.exists():
            response = requests.get(url, timeout=120)
            response.raise_for_status()
            path.write_bytes(response.content)
        return path

    @staticmethod
    def _rows_for_cnpj(path: Path, cnpj: str) -> pd.DataFrame:
        rows: list[pd.DataFrame] = []
        with ZipFile(path) as archive:
            members = [member for member in archive.namelist() if member.lower().endswith(".csv")]
            if not members:
                raise ValueError(f"No CSV found in CVM archive {path.name}")
            with archive.open(members[0]) as handle:
                for chunk in pd.read_csv(handle, sep=";", encoding="latin1", dtype=str, chunksize=100_000,
                                         low_memory=False):
                    identifier = next((column for column in IDENTIFIER_COLUMNS if column in chunk.columns), None)
                    if identifier is None or "DT_COMPTC" not in chunk.columns or "VL_QUOTA" not in chunk.columns:
                        raise ValueError(f"Unexpected CVM Informe Diário schema in {path.name}")
                    found = chunk[identifier].fillna("").str.replace(r"\D", "", regex=True).eq(cnpj)
                    if found.any():
                        rows.append(chunk.loc[found, ["DT_COMPTC", "VL_QUOTA"]])
        return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["DT_COMPTC", "VL_QUOTA"])

    def quotes(self, cnpj: str, start: str | pd.Timestamp, end: str | pd.Timestamp) -> FundQuoteSeries:
        normalized = normalize_cnpj(cnpj)
        start_date, end_date = pd.Timestamp(start), pd.Timestamp(end)
        if end_date < start_date:
            raise ValueError("end date cannot precede start date")
        urls = self.archive_urls(start_date, end_date)
        rows = [self._rows_for_cnpj(self._archive(url), normalized) for url in urls]
        frame = pd.concat(rows, ignore_index=True)
        if frame.empty:
            raise ValueError(
                f"No CVM daily quote found for CNPJ {format_cnpj(normalized)} in the selected period. "
                "Confirm the fund/class CNPJ in the CVM portal."
            )
        frame["date"] = pd.to_datetime(frame["DT_COMPTC"], errors="coerce")
        quota_text = frame["VL_QUOTA"].str.strip()
        quota_text = quota_text.where(~quota_text.str.contains(r"\.", regex=True) | ~quota_text.str.contains(",", regex=False),
                                      quota_text.str.replace(".", "", regex=False))
        frame["quota"] = pd.to_numeric(quota_text.str.replace(",", ".", regex=False), errors="coerce")
        frame = frame.dropna(subset=["date", "quota"]).query("quota > 0")
        frame = frame[(frame.date >= start_date) & (frame.date <= end_date)]
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        if frame.empty:
            raise ValueError("CVM quotes exist but none are valid in the selected date range")
        return FundQuoteSeries(normalized, frame.set_index("date")["quota"].rename("fund_quota"), tuple(urls))


def _wealth_metrics(wealth: pd.Series) -> dict[str, float]:
    wealth = wealth.dropna()
    returns = wealth.pct_change().dropna()
    elapsed_days = max((wealth.index[-1] - wealth.index[0]).days, 1)
    drawdown = wealth / wealth.cummax() - 1
    return {
        "cumulative_return": float(wealth.iloc[-1] / wealth.iloc[0] - 1),
        "cagr": float((wealth.iloc[-1] / wealth.iloc[0]) ** (365.25 / elapsed_days) - 1),
        "annual_volatility": float(returns.std(ddof=1) * np.sqrt(12)) if len(returns) > 1 else 0.0,
        "max_drawdown": float(drawdown.min()),
    }


def compare_common_window(strategies: dict[str, pd.DataFrame], fund: FundQuoteSeries,
                          fund_name: str) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Normalize all curves to base 100 over the common, publication-safe period."""
    reference = next(iter(strategies.values())).copy()
    dates = pd.DatetimeIndex(pd.to_datetime(reference["date"]))
    aligned_quota = fund.quotes.reindex(dates, method="ffill")
    valid_dates = dates[aligned_quota.notna()]
    if len(valid_dates) < 2:
        raise ValueError("Fund has fewer than two quotes aligned to strategy decision dates")
    curves = pd.DataFrame(index=valid_dates)
    for name, result in strategies.items():
        series = result.set_index(pd.to_datetime(result["date"]))["wealth"].reindex(valid_dates)
        curves[name] = series / series.iloc[0] * 100
    fund_wealth = aligned_quota.reindex(valid_dates)
    curves[fund_name] = fund_wealth / fund_wealth.iloc[0] * 100
    curves.index.name = "date"
    metrics = pd.DataFrame([{"strategy": name, **_wealth_metrics(curves[name])} for name in curves.columns])
    metadata = {
        "fund_cnpj": format_cnpj(fund.cnpj), "fund_name": fund_name,
        "comparison_start": str(valid_dates[0].date()), "comparison_end": str(valid_dates[-1].date()),
        "observations": str(len(valid_dates)),
        "alignment": "Latest CVM quote on or before each strategy decision date.",
    }
    return curves, metrics, metadata


def fund_values_for_nav(fund: FundQuoteSeries, nav_dates: pd.Series | pd.DatetimeIndex,
                        initial_value_brl: float) -> pd.Series:
    """Mark an active-fund reference to the shadow NAV dates from CVM quotas.

    Values are normalized only at the shadow portfolio's first date.  This is
    a comparison curve, not a cash flow or a claim that the fund was purchased.
    """
    dates = pd.DatetimeIndex(pd.to_datetime(nav_dates))
    if dates.empty or dates.has_duplicates:
        raise ValueError("NAV dates must be non-empty and unique")
    aligned = fund.quotes.reindex(dates, method="ffill")
    if aligned.isna().any():
        first_missing = str(aligned[aligned.isna()].index[0].date())
        raise ValueError(f"No CVM fund quote on or before NAV date {first_missing}")
    return (aligned / aligned.iloc[0] * initial_value_brl).rename("active_fund_value_brl")
