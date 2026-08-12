"""Official-CVM fundamental ingestion for live Benevente research proposals.

The source files are filed financial statements, not vendor ratios. A snapshot
uses the CVM receipt date as `available_date`, so it can be stored and reused
without placing an unpublished filing in the past.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile
import pandas as pd
import yfinance as yf

from fundamentals import FundamentalSnapshot


CVM_DFP_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{year}.zip"


@dataclass(frozen=True)
class Issuer:
    ticker: str
    cnpj: str
    sector: str
    is_financial: bool = False


BRAZIL_ISSUERS = (
    Issuer("PETR4.SA", "33.000.167/0001-01", "Energy"),
    Issuer("VALE3.SA", "33.592.510/0001-54", "Materials"),
    Issuer("ITUB4.SA", "60.872.504/0001-23", "Financials", True),
    Issuer("BBDC4.SA", "60.746.948/0001-12", "Financials", True),
    Issuer("BBAS3.SA", "00.000.000/0001-91", "Financials", True),
    Issuer("ABEV3.SA", "07.526.557/0001-00", "Consumer Staples"),
    Issuer("WEGE3.SA", "84.429.695/0001-11", "Industrials"),
    Issuer("RENT3.SA", "16.670.085/0001-55", "Industrials"),
)


def _read_csv_from_zip(archive: ZipFile, filename: str) -> pd.DataFrame:
    with archive.open(filename) as source:
        return pd.read_csv(source, sep=";", encoding="latin1", decimal=",", low_memory=False)


def _latest_statement(frame: pd.DataFrame, cnpj: str) -> pd.DataFrame:
    company = frame[(frame.CNPJ_CIA == cnpj) & (frame.ORDEM_EXERC == "ÚLTIMO")].copy()
    company["DT_REFER"] = pd.to_datetime(company.DT_REFER)
    return company[company.DT_REFER == company.DT_REFER.max()]


def _account_value(frame: pd.DataFrame, cnpj: str, account: str) -> float | None:
    row = _latest_statement(frame, cnpj)
    values = row.loc[row.CD_CONTA == account, "VL_CONTA"]
    return None if values.empty else float(values.iloc[0]) * 1_000  # CVM DFP is normally in thousands of BRL.


def _account_value_any(frame: pd.DataFrame, cnpj: str, accounts: tuple[str, ...]) -> float | None:
    """Return the first available value from a documented taxonomy fallback."""
    for account in accounts:
        value = _account_value(frame, cnpj, account)
        if value is not None:
            return value
    return None


class CvmDfpClient:
    """Fetch and cache the annual DFP package from CVM's open-data portal."""
    def __init__(self, cache_dir: str | Path = "work/cvm_cache") -> None:
        self.cache_dir = Path(cache_dir)

    def package(self, year: int) -> ZipFile:
        import requests
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"dfp_cia_aberta_{year}.zip"
        if not path.exists():
            response = requests.get(CVM_DFP_URL.format(year=year), timeout=90)
            response.raise_for_status()
            path.write_bytes(response.content)
        return ZipFile(path)

    def live_snapshots(self, year: int, issuers: tuple[Issuer, ...] = BRAZIL_ISSUERS) -> list[FundamentalSnapshot]:
        """Create current, annual snapshots; output must be reviewed before use.

        Revenue and profitability are annual DFP values; market capitalization
        and average traded value are retrieved at run time from yfinance and
        stamped with the proposal's generation date in the output provenance.
        """
        with self.package(year) as archive:
            prefix = f"dfp_cia_aberta_"
            dre = _read_csv_from_zip(archive, f"{prefix}DRE_con_{year}.csv")
            bpa = _read_csv_from_zip(archive, f"{prefix}BPA_con_{year}.csv")
            bpp = _read_csv_from_zip(archive, f"{prefix}BPP_con_{year}.csv")
            dfc = _read_csv_from_zip(archive, f"{prefix}DFC_MI_con_{year}.csv")
            filings = _read_csv_from_zip(archive, f"{prefix}{year}.csv")
        results = []
        for issuer in issuers:
            filing = filings[filings.CNPJ_CIA == issuer.cnpj].copy()
            if filing.empty:
                raise RuntimeError(f"No DFP filing found for {issuer.ticker}/{issuer.cnpj}; update the issuer map.")
            filing["DT_RECEB"] = pd.to_datetime(filing.DT_RECEB)
            filing = filing.sort_values("DT_RECEB").iloc[-1]
            available = filing.DT_RECEB.to_pydatetime()
            # The economic observation date belongs to the statement, not to
            # the date on which it was received by the regulator.  Keeping
            # both dates is what makes the snapshot safe for future PIT uses.
            statement = _latest_statement(dre, issuer.cnpj)
            if statement.empty:
                raise RuntimeError(f"No consolidated DRE found for {issuer.ticker}; review filing manually.")
            as_of = pd.Timestamp(statement.DT_REFER.max()).to_pydatetime()
            market = yf.Ticker(issuer.ticker)
            history = market.history(period="3mo", auto_adjust=True)
            if history.empty:
                raise RuntimeError(f"No live market data returned for {issuer.ticker}")
            try:
                market_cap = float(market.fast_info["market_cap"])
            except Exception as exc:
                raise RuntimeError(
                    f"Verified live market capitalization is unavailable for {issuer.ticker}; "
                    "do not issue a proposal until the market-data source is available."
                ) from exc
            daily_value = float((history.Close * history.Volume).tail(60).mean())
            revenue = _account_value(dre, issuer.cnpj, "3.01")
            ebit = _account_value(dre, issuer.cnpj, "3.05")
            # Financial statements have two CVM taxonomies in the observed
            # universe: net income is 3.09 or 3.11; consolidated equity is
            # 2.07 or 2.08. Non-financial issuers use 3.11/2.03.
            net_income = _account_value_any(dre, issuer.cnpj, ("3.09", "3.11")) if issuer.is_financial else _account_value(dre, issuer.cnpj, "3.11")
            cash = _account_value(bpa, issuer.cnpj, "1.01.01")
            equity = _account_value_any(bpp, issuer.cnpj, ("2.08", "2.07")) if issuer.is_financial else _account_value(bpp, issuer.cnpj, "2.03")
            current_debt = _account_value(bpp, issuer.cnpj, "2.01.04") or 0.0
            noncurrent_debt = _account_value(bpp, issuer.cnpj, "2.02.01") or 0.0
            debt = current_debt + noncurrent_debt
            cfo = _account_value(dfc, issuer.cnpj, "6.01")
            investing_cashflow = _account_value(dfc, issuer.cnpj, "6.02")
            required = (revenue, net_income, equity) if issuer.is_financial else (revenue, ebit, net_income, cash, equity, cfo, investing_cashflow)
            if not all(value is not None for value in required):
                raise RuntimeError(f"Incomplete standardized CVM accounts for {issuer.ticker}; review filing manually.")
            owner_cash_proxy = None if issuer.is_financial else cfo + investing_cashflow
            invested_capital = equity + debt - (cash or 0.0)
            results.append(FundamentalSnapshot(
                ticker=issuer.ticker, as_of_date=as_of, available_date=available, sector=issuer.sector,
                is_financial=issuer.is_financial, market_cap_brl=market_cap,
                price_to_earnings=market_cap / net_income if net_income > 0 else None,
                price_to_book=market_cap / equity if equity > 0 else None,
                ev_to_ebit=(market_cap + debt - (cash or 0.0)) / ebit if ebit is not None and ebit > 0 else None,
                free_cash_flow_yield=None if owner_cash_proxy is None else owner_cash_proxy / market_cap,
                roe=net_income / equity if equity > 0 else None,
                roic=None if issuer.is_financial or invested_capital <= 0 else ebit / invested_capital,
                debt_to_ebitda=None,  # Requires a validated EBITDA mapping; fail closed for non-financial firms.
                interest_coverage=None,
                operating_margin=ebit / revenue if ebit is not None and revenue > 0 else None,
                revenue_growth_3y=None,
                average_daily_value_brl=daily_value,
                source=f"CVM DFP {year} (receipt {available.date()}) + yfinance live market data",
            ))
        return results
