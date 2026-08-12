"""Current, point-in-time fundamental snapshots from CVM ITR plus DFP TTM."""
from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile
import pandas as pd

from cvm_fundamentals import BRAZIL_ISSUERS, CvmDfpClient, Issuer, _read_csv_from_zip
from fundamentals import FundamentalSnapshot
from market_snapshot import MarketSnapshot


CVM_ITR_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"


def _statement(frame: pd.DataFrame, cnpj: str, reference_date: pd.Timestamp,
               version: int, order: str = "ÚLTIMO") -> pd.DataFrame:
    copy = frame.copy()
    copy["DT_REFER"] = pd.to_datetime(copy["DT_REFER"])
    return copy[(copy.CNPJ_CIA == cnpj) & (copy.DT_REFER == reference_date)
                & (copy.VERSAO == version) & (copy.ORDEM_EXERC == order)]


def _value(frame: pd.DataFrame, cnpj: str, reference_date: pd.Timestamp,
           version: int, account: str, order: str = "ÚLTIMO") -> float | None:
    statement = _statement(frame, cnpj, reference_date, version, order)
    values = statement.loc[statement.CD_CONTA == account, "VL_CONTA"]
    return None if values.empty else float(values.iloc[0]) * 1_000


def _any_value(frame: pd.DataFrame, cnpj: str, reference_date: pd.Timestamp,
               version: int, accounts: tuple[str, ...], order: str = "ÚLTIMO") -> float | None:
    for account in accounts:
        value = _value(frame, cnpj, reference_date, version, account, order)
        if value is not None:
            return value
    return None


def _annual_value(frame: pd.DataFrame, cnpj: str, account: str) -> float | None:
    copy = frame[(frame.CNPJ_CIA == cnpj) & (frame.ORDEM_EXERC == "ÚLTIMO")].copy()
    copy["DT_REFER"] = pd.to_datetime(copy["DT_REFER"])
    if copy.empty:
        return None
    current = copy[copy.DT_REFER == copy.DT_REFER.max()]
    values = current.loc[current.CD_CONTA == account, "VL_CONTA"]
    return None if values.empty else float(values.iloc[0]) * 1_000


def _annual_any(frame: pd.DataFrame, cnpj: str, accounts: tuple[str, ...]) -> float | None:
    for account in accounts:
        value = _annual_value(frame, cnpj, account)
        if value is not None:
            return value
    return None


def _ttm(annual: float | None, current: float | None, comparative: float | None,
         label: str, ticker: str) -> float:
    if annual is None or current is None or comparative is None:
        raise RuntimeError(f"Missing annual/current/comparative CVM value for {label} of {ticker}")
    return annual + current - comparative


class CvmItrClient:
    """Build TTM valuations from the newest ITR available by the decision date."""
    def __init__(self, cache_dir: str | Path = "work/cvm_cache") -> None:
        self.cache_dir = Path(cache_dir)

    def package(self, year: int) -> ZipFile:
        import requests
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"itr_cia_aberta_{year}.zip"
        if not path.exists():
            response = requests.get(CVM_ITR_URL.format(year=year), timeout=90)
            response.raise_for_status()
            path.write_bytes(response.content)
        return ZipFile(path)

    def live_snapshots(self, itr_year: int, decision_date: pd.Timestamp,
                       market_data: dict[str, MarketSnapshot],
                       issuers: tuple[Issuer, ...] = BRAZIL_ISSUERS) -> list[FundamentalSnapshot]:
        with self.package(itr_year) as archive:
            prefix = "itr_cia_aberta_"
            dre = _read_csv_from_zip(archive, f"{prefix}DRE_con_{itr_year}.csv")
            bpa = _read_csv_from_zip(archive, f"{prefix}BPA_con_{itr_year}.csv")
            bpp = _read_csv_from_zip(archive, f"{prefix}BPP_con_{itr_year}.csv")
            dfc = _read_csv_from_zip(archive, f"{prefix}DFC_MI_con_{itr_year}.csv")
            filings = _read_csv_from_zip(archive, f"{prefix}{itr_year}.csv")
        with CvmDfpClient(self.cache_dir).package(itr_year - 1) as annual_archive:
            prefix = "dfp_cia_aberta_"
            annual_dre = _read_csv_from_zip(annual_archive, f"{prefix}DRE_con_{itr_year - 1}.csv")
            annual_dfc = _read_csv_from_zip(annual_archive, f"{prefix}DFC_MI_con_{itr_year - 1}.csv")

        filings["DT_RECEB"] = pd.to_datetime(filings["DT_RECEB"])
        filings["DT_REFER"] = pd.to_datetime(filings["DT_REFER"])
        results: list[FundamentalSnapshot] = []
        for issuer in issuers:
            candidates = filings[(filings.CNPJ_CIA == issuer.cnpj) & (filings.DT_RECEB <= decision_date)].copy()
            if candidates.empty:
                raise RuntimeError(f"No ITR available by {decision_date.date()} for {issuer.ticker}")
            filing = candidates.sort_values(["DT_REFER", "VERSAO", "DT_RECEB"]).iloc[-1]
            reference, version = pd.Timestamp(filing.DT_REFER), int(filing.VERSAO)
            market = market_data.get(issuer.ticker)
            if market is None:
                raise RuntimeError(f"No auditable market snapshot for {issuer.ticker}")

            def ttm(accounts: tuple[str, ...]) -> float:
                return _ttm(
                    _annual_any(annual_dre, issuer.cnpj, accounts),
                    _any_value(dre, issuer.cnpj, reference, version, accounts, "ÚLTIMO"),
                    _any_value(dre, issuer.cnpj, reference, version, accounts, "PENÚLTIMO"),
                    accounts[0], issuer.ticker,
                )

            revenue, ebit = ttm(("3.01",)), ttm(("3.05",))
            net_income = ttm(("3.09", "3.11")) if issuer.is_financial else ttm(("3.11",))
            equity = _any_value(bpp, issuer.cnpj, reference, version, ("2.08", "2.07")) if issuer.is_financial else _value(bpp, issuer.cnpj, reference, version, "2.03")
            cash = _any_value(bpa, issuer.cnpj, reference, version, ("1.01.01", "1.01"))
            debt = (_value(bpp, issuer.cnpj, reference, version, "2.01.04") or 0.0) + (_value(bpp, issuer.cnpj, reference, version, "2.02.01") or 0.0)
            if issuer.is_financial:
                cfo = investing = None
            else:
                def ttm_cashflow(account: str) -> float:
                    return _ttm(_annual_value(annual_dfc, issuer.cnpj, account),
                                _value(dfc, issuer.cnpj, reference, version, account, "ÚLTIMO"),
                                _value(dfc, issuer.cnpj, reference, version, account, "PENÚLTIMO"),
                                account, issuer.ticker)
                cfo, investing = ttm_cashflow("6.01"), ttm_cashflow("6.02")
            required = (revenue, net_income, equity) if issuer.is_financial else (revenue, ebit, net_income, cash, equity, cfo, investing)
            if not all(value is not None for value in required):
                raise RuntimeError(f"Incomplete standardized ITR accounts for {issuer.ticker}; review filing manually.")
            owner_cash_proxy = None if issuer.is_financial else cfo + investing
            invested_capital = equity + debt - (cash or 0.0)
            results.append(FundamentalSnapshot(
                ticker=issuer.ticker, as_of_date=reference.to_pydatetime(), available_date=filing.DT_RECEB.to_pydatetime(),
                sector=issuer.sector, is_financial=issuer.is_financial, market_cap_brl=market.market_cap_brl,
                price_to_earnings=market.market_cap_brl / net_income if net_income > 0 else None,
                price_to_book=market.market_cap_brl / equity if equity > 0 else None,
                ev_to_ebit=(market.market_cap_brl + debt - (cash or 0.0)) / ebit if ebit > 0 else None,
                free_cash_flow_yield=None if owner_cash_proxy is None else owner_cash_proxy / market.market_cap_brl,
                roe=net_income / equity if equity > 0 else None,
                roic=None if issuer.is_financial or invested_capital <= 0 else ebit / invested_capital,
                debt_to_ebitda=None, interest_coverage=None,
                operating_margin=ebit / revenue if revenue > 0 else None, revenue_growth_3y=None,
                average_daily_value_brl=market.average_daily_value_brl,
                source=(f"CVM ITR {itr_year}, ref {reference.date()}, receipt {filing.DT_RECEB.date()}; "
                        f"CVM DFP {itr_year - 1} TTM bridge; market snapshot: {market.source}"),
            ))
        return results
