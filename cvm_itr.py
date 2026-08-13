"""Current, point-in-time fundamental snapshots from CVM ITR plus DFP TTM."""
from __future__ import annotations

from pathlib import Path
import re
from zipfile import ZipFile
import pandas as pd

from cvm_fundamentals import BRAZIL_ISSUERS, CvmDfpClient, Issuer, _read_csv_from_zip
from fundamentals import FundamentalSnapshot
from market_snapshot import MarketSnapshot


CVM_ITR_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"


def _cnpj_key(value: object) -> str:
    """Compare CVM and B3 identifiers independently of display formatting."""
    return re.sub(r"\D", "", str(value or "")).zfill(14)


def _statement(frame: pd.DataFrame, cnpj: str, reference_date: pd.Timestamp,
               version: int, order: str = "ÚLTIMO") -> pd.DataFrame:
    copy = frame.copy()
    copy["DT_REFER"] = pd.to_datetime(copy["DT_REFER"])
    return copy[(copy.CNPJ_CIA == _cnpj_key(cnpj)) & (copy.DT_REFER == reference_date)
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
    copy = frame[(frame.CNPJ_CIA == _cnpj_key(cnpj)) & (frame.ORDEM_EXERC == "ÚLTIMO")].copy()
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


def _statement_with_individual_fallback(archive: ZipFile, prefix: str, statement: str, year: int) -> pd.DataFrame:
    """Prefer consolidated statements, using individual statements only when needed.

    Some older financial institutions publish their standardized CVM accounts
    only in ``*_ind``.  Concatenating blindly would double-count issuers that
    have both versions, so rows from the individual file are retained solely
    for CNPJs absent from the consolidated counterpart.
    """
    consolidated = _read_csv_from_zip(archive, f"{prefix}{statement}_con_{year}.csv")
    individual_name = f"{prefix}{statement}_ind_{year}.csv"
    if individual_name not in archive.namelist():
        return consolidated
    individual = _read_csv_from_zip(archive, individual_name)
    individual = individual[~individual.CNPJ_CIA.isin(consolidated.CNPJ_CIA.unique())]
    return pd.concat([consolidated, individual], ignore_index=True)


class CvmItrClient:
    """Build TTM valuations from the newest ITR available by the decision date."""
    def __init__(self, cache_dir: str | Path = "work/cvm_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self._statement_panels: dict[int, dict[str, pd.DataFrame]] = {}

    def package(self, year: int) -> ZipFile:
        import requests
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"itr_cia_aberta_{year}.zip"
        if not path.exists():
            response = requests.get(CVM_ITR_URL.format(year=year), timeout=90)
            response.raise_for_status()
            path.write_bytes(response.content)
        return ZipFile(path)

    def clear_cached_panels(self) -> None:
        """Release parsed CVM statements after one January has been processed."""
        self._statement_panels.clear()

    def _statement_panel(self, itr_year: int) -> dict[str, pd.DataFrame]:
        """Read each annual ZIP once, then reuse it for every issuer."""
        cached = self._statement_panels.get(itr_year)
        if cached is not None:
            return cached
        with self.package(itr_year) as archive:
            prefix = "itr_cia_aberta_"
            panel = {
                "dre": _statement_with_individual_fallback(archive, prefix, "DRE", itr_year),
                "bpa": _statement_with_individual_fallback(archive, prefix, "BPA", itr_year),
                "bpp": _statement_with_individual_fallback(archive, prefix, "BPP", itr_year),
                "dfc": _statement_with_individual_fallback(archive, prefix, "DFC_MI", itr_year),
                "filings": _read_csv_from_zip(archive, f"{prefix}{itr_year}.csv"),
            }
        with CvmDfpClient(self.cache_dir).package(itr_year - 1) as annual_archive:
            prefix = "dfp_cia_aberta_"
            panel["annual_dre"] = _statement_with_individual_fallback(annual_archive, prefix, "DRE", itr_year - 1)
            panel["annual_dfc"] = _statement_with_individual_fallback(annual_archive, prefix, "DFC_MI", itr_year - 1)
        panel["filings"]["DT_RECEB"] = pd.to_datetime(panel["filings"].DT_RECEB)
        panel["filings"]["DT_REFER"] = pd.to_datetime(panel["filings"].DT_REFER)
        for frame in panel.values():
            if isinstance(frame, pd.DataFrame) and "CNPJ_CIA" in frame.columns:
                frame["CNPJ_CIA"] = frame["CNPJ_CIA"].map(_cnpj_key)
        self._statement_panels[itr_year] = panel
        return panel

    def live_snapshots(self, itr_year: int, decision_date: pd.Timestamp,
                       market_data: dict[str, MarketSnapshot],
                       issuers: tuple[Issuer, ...] = BRAZIL_ISSUERS) -> list[FundamentalSnapshot]:
        panel = self._statement_panel(itr_year)
        dre, bpa, bpp, dfc = panel["dre"], panel["bpa"], panel["bpp"], panel["dfc"]
        annual_dre, annual_dfc, filings = panel["annual_dre"], panel["annual_dfc"], panel["filings"]
        results: list[FundamentalSnapshot] = []
        for issuer in issuers:
            cnpj = _cnpj_key(issuer.cnpj)
            candidates = filings[(filings.CNPJ_CIA == cnpj) & (filings.DT_RECEB <= decision_date)].copy()
            if candidates.empty:
                raise RuntimeError(f"No ITR available by {decision_date.date()} for {issuer.ticker}")
            filing = candidates.sort_values(["DT_REFER", "VERSAO", "DT_RECEB"]).iloc[-1]
            reference, version = pd.Timestamp(filing.DT_REFER), int(filing.VERSAO)
            market = market_data.get(issuer.ticker)
            if market is None:
                raise RuntimeError(f"No auditable market snapshot for {issuer.ticker}")

            issuer_dre = dre[dre.CNPJ_CIA == cnpj]
            issuer_bpa = bpa[bpa.CNPJ_CIA == cnpj]
            issuer_bpp = bpp[bpp.CNPJ_CIA == cnpj]
            issuer_dfc = dfc[dfc.CNPJ_CIA == cnpj]
            issuer_annual_dre = annual_dre[annual_dre.CNPJ_CIA == cnpj]
            issuer_annual_dfc = annual_dfc[annual_dfc.CNPJ_CIA == cnpj]

            def ttm(accounts: tuple[str, ...]) -> float:
                return _ttm(
                    _annual_any(issuer_annual_dre, cnpj, accounts),
                    _any_value(issuer_dre, cnpj, reference, version, accounts, "ÚLTIMO"),
                    _any_value(issuer_dre, cnpj, reference, version, accounts, "PENÚLTIMO"),
                    accounts[0], issuer.ticker,
                )

            # Banks report a materially different DRE taxonomy.  Do not force
            # an industrial-company revenue/EBIT bridge on them: their
            # financial screen is deliberately P/E, P/B and ROE based.
            if issuer.is_financial:
                revenue = ebit = None
                net_income = ttm(("3.13", "3.11", "3.09"))
            else:
                revenue, ebit = ttm(("3.01",)), ttm(("3.05",))
                net_income = ttm(("3.11",))
            # Historical individual bank statements use the same equity total
            # account (2.03) as industrial statements, whereas newer bank
            # templates may expose 2.07/2.08.  The ordered fallback preserves
            # the most specific available presentation.
            equity = (_any_value(issuer_bpp, cnpj, reference, version, ("2.08", "2.07", "2.05", "2.03"))
                      if issuer.is_financial else _value(issuer_bpp, cnpj, reference, version, "2.03"))
            cash = _any_value(issuer_bpa, cnpj, reference, version, ("1.01.01", "1.01"))
            debt = (_value(issuer_bpp, cnpj, reference, version, "2.01.04") or 0.0) + (_value(issuer_bpp, cnpj, reference, version, "2.02.01") or 0.0)
            if issuer.is_financial:
                cfo = investing = None
            else:
                def ttm_cashflow(account: str) -> float:
                    return _ttm(_annual_value(issuer_annual_dfc, cnpj, account),
                                _value(issuer_dfc, cnpj, reference, version, account, "ÚLTIMO"),
                                _value(issuer_dfc, cnpj, reference, version, account, "PENÚLTIMO"),
                                account, issuer.ticker)
                cfo, investing = ttm_cashflow("6.01"), ttm_cashflow("6.02")
            required = (net_income, equity) if issuer.is_financial else (revenue, ebit, net_income, cash, equity, cfo, investing)
            if not all(value is not None for value in required):
                raise RuntimeError(f"Incomplete standardized ITR accounts for {issuer.ticker}; review filing manually.")
            owner_cash_proxy = None if issuer.is_financial else cfo + investing
            invested_capital = equity + debt - (cash or 0.0)
            results.append(FundamentalSnapshot(
                ticker=issuer.ticker, as_of_date=reference.to_pydatetime(), available_date=filing.DT_RECEB.to_pydatetime(),
                sector=issuer.sector, is_financial=issuer.is_financial, market_cap_brl=market.market_cap_brl,
                price_to_earnings=market.market_cap_brl / net_income if net_income > 0 else None,
                price_to_book=market.market_cap_brl / equity if equity > 0 else None,
                ev_to_ebit=(market.market_cap_brl + debt - (cash or 0.0)) / ebit if ebit is not None and ebit > 0 else None,
                free_cash_flow_yield=None if owner_cash_proxy is None else owner_cash_proxy / market.market_cap_brl,
                roe=net_income / equity if equity > 0 else None,
                roic=None if issuer.is_financial or invested_capital <= 0 else ebit / invested_capital,
                debt_to_ebitda=None, interest_coverage=None,
                operating_margin=ebit / revenue if revenue is not None and revenue > 0 else None, revenue_growth_3y=None,
                average_daily_value_brl=market.average_daily_value_brl,
                source=(f"CVM ITR {itr_year}, ref {reference.date()}, receipt {filing.DT_RECEB.date()}; "
                        f"CVM DFP {itr_year - 1} TTM bridge; market snapshot: {market.source}"),
            ))
        return results
