"""Current, point-in-time fundamental snapshots from CVM ITR plus DFP TTM.

Two corrections matter for anyone reading historical panels built before
2026-08-15.  Flow accounts are now read from the accumulated year-to-date row
only: from the second quarter onwards the ITR also publishes the isolated
quarter, and mixing the two invalidates the trailing-twelve-month bridge.
Solvency metrics are now derived instead of being emitted as ``None``, which
previously made every non-financial issuer fail the value/quality screen for
lack of data rather than for lack of quality.
"""
from __future__ import annotations

from pathlib import Path
import re
from zipfile import ZipFile
import pandas as pd

from cvm_fundamentals import BRAZIL_ISSUERS, CvmDfpClient, Issuer, _read_csv_from_zip
from fundamentals import FundamentalSnapshot
from market_snapshot import MarketSnapshot


CVM_ITR_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_{year}.zip"

# Finite sentinels keep the exported panel numeric and CSV round-trippable
# while still failing (or passing) the solvency screen unambiguously.
DISTRESSED_LEVERAGE = 999.0
UNLEVERED_COVERAGE = 999.0


def _cnpj_key(value: object) -> str:
    """Compare CVM and B3 identifiers independently of display formatting."""
    return re.sub(r"\D", "", str(value or "")).zfill(14)


def _accumulated_only(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep the year-to-date row of a flow statement, dropping the quarter row.

    From the second quarter onwards a CVM ITR income or cash-flow statement
    publishes two rows per account and ``ORDEM_EXERC``: the accumulated period
    starting in January and the isolated quarter.  Only the accumulated figure
    is valid in the ``annual + current - comparative`` trailing-twelve-month
    bridge, so the shorter period is removed explicitly instead of relying on
    the file's row order.
    """
    if "DT_INI_EXERC" not in frame.columns or frame.empty:
        return frame
    copy = frame.copy()
    start = pd.to_datetime(copy["DT_INI_EXERC"], errors="coerce")
    if start.isna().all():
        return frame
    copy["_period_start"] = start
    keep = copy.groupby(["CD_CONTA", "ORDEM_EXERC"])["_period_start"].transform("min")
    return copy[copy["_period_start"].eq(keep) | copy["_period_start"].isna()].drop(columns="_period_start")


def _statement(frame: pd.DataFrame, cnpj: str, reference_date: pd.Timestamp,
               version: int, order: str = "ÚLTIMO") -> pd.DataFrame:
    # Called several times per issuer. Filter before copying so a dated
    # full-universe panel does not duplicate every CVM statement per lookup.
    copy = frame[frame.CNPJ_CIA == _cnpj_key(cnpj)].copy()
    copy["DT_REFER"] = pd.to_datetime(copy["DT_REFER"])
    selected = copy[(copy.DT_REFER == reference_date)
                    & (copy.VERSAO == version) & (copy.ORDEM_EXERC == order)]
    return _accumulated_only(selected)


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
    current = _accumulated_only(copy[copy.DT_REFER == copy.DT_REFER.max()])
    values = current.loc[current.CD_CONTA == account, "VL_CONTA"]
    return None if values.empty else float(values.iloc[0]) * 1_000


def _annual_any(frame: pd.DataFrame, cnpj: str, accounts: tuple[str, ...]) -> float | None:
    for account in accounts:
        value = _annual_value(frame, cnpj, account)
        if value is not None:
            return value
    return None


# Standardized CVM statements label depreciation under several sibling codes
# (6.01.01.02 through 6.01.01.06 are all observed), so the add-back is located
# by description inside the operating-adjustment group rather than by a single
# hardcoded account number.
DEPRECIATION_PATTERN = re.compile(r"deprecia|amortiza|exaust", re.IGNORECASE)
FINANCIAL_EXPENSE_PATTERN = re.compile(r"despesa.*financeir", re.IGNORECASE)


def _labelled_sum(frame: pd.DataFrame, reference: pd.Timestamp | None, version: int | None,
                  prefix: str, depth: int, pattern: re.Pattern[str], order: str = "ÚLTIMO") -> float | None:
    """Sum every leaf account under ``prefix`` whose description matches.

    Only accounts at exactly ``depth`` segments are summed so a parent line and
    its children are never double counted.  ``None`` means the concept is
    absent from the filing; it is not silently treated as zero.
    """
    if frame.empty or "CD_CONTA" not in frame.columns:
        return None
    copy = frame[frame.ORDEM_EXERC == order].copy()
    if reference is not None:
        copy["DT_REFER"] = pd.to_datetime(copy["DT_REFER"])
        copy = copy[(copy.DT_REFER == reference) & (copy.VERSAO == version)]
    elif not copy.empty:
        copy["DT_REFER"] = pd.to_datetime(copy["DT_REFER"])
        copy = copy[copy.DT_REFER == copy.DT_REFER.max()]
    if copy.empty:
        return None
    # Summing without this would add the quarter row on top of the accumulated
    # row and double count depreciation from the second quarter onwards.
    copy = _accumulated_only(copy)
    codes = copy.CD_CONTA.astype(str)
    selected = copy[codes.str.startswith(prefix)
                    & codes.str.count(r"\.").eq(depth - 1)
                    & copy.DS_CONTA.astype(str).str.contains(pattern)]
    if selected.empty:
        return None
    return float(pd.to_numeric(selected.VL_CONTA, errors="coerce").fillna(0).sum()) * 1_000


def _ttm_optional(annual: float | None, current: float | None, comparative: float | None) -> float | None:
    """Trailing-twelve-month bridge that reports absence instead of guessing."""
    if annual is None or current is None or comparative is None:
        return None
    return annual + current - comparative


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
        # The full-universe gate asks for one issuer at a time.  Index each
        # statement once instead of rescanning multi-million-row CVM panels
        # for every issuer and every account.
        panel["by_issuer"] = {
            name: {str(cnpj): group for cnpj, group in frame.groupby("CNPJ_CIA", sort=False)}
            for name, frame in panel.items()
            if isinstance(frame, pd.DataFrame) and name != "filings" and "CNPJ_CIA" in frame.columns
        }
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

            by_issuer = panel["by_issuer"]
            empty = pd.DataFrame()
            issuer_dre = by_issuer["dre"].get(cnpj, empty)
            issuer_bpa = by_issuer["bpa"].get(cnpj, empty)
            issuer_bpp = by_issuer["bpp"].get(cnpj, empty)
            issuer_dfc = by_issuer["dfc"].get(cnpj, empty)
            issuer_annual_dre = by_issuer["annual_dre"].get(cnpj, empty)
            issuer_annual_dfc = by_issuer["annual_dfc"].get(cnpj, empty)

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
            # Net debt uses cash equivalents plus short-term financial
            # investments, the standard Brazilian convention. Treating only
            # 1.01.01 as cash overstates leverage for issuers that park
            # liquidity in 1.01.02.
            equivalents = _value(issuer_bpa, cnpj, reference, version, "1.01.01")
            short_term_investments = _value(issuer_bpa, cnpj, reference, version, "1.01.02")
            cash = (None if equivalents is None and short_term_investments is None
                    else (equivalents or 0.0) + (short_term_investments or 0.0))
            if cash is None:
                cash = _value(issuer_bpa, cnpj, reference, version, "1.01")
            debt = (_value(issuer_bpp, cnpj, reference, version, "2.01.04") or 0.0) + (_value(issuer_bpp, cnpj, reference, version, "2.02.01") or 0.0)
            if issuer.is_financial:
                cfo = investing = None
                ebitda = financial_expense = None
            else:
                def ttm_cashflow(account: str) -> float:
                    return _ttm(_annual_value(issuer_annual_dfc, cnpj, account),
                                _value(issuer_dfc, cnpj, reference, version, account, "ÚLTIMO"),
                                _value(issuer_dfc, cnpj, reference, version, account, "PENÚLTIMO"),
                                account, issuer.ticker)
                cfo, investing = ttm_cashflow("6.01"), ttm_cashflow("6.02")
                # Solvency needs the depreciation add-back and the interest
                # burden.  Both come from the same dated filing as EBIT, so a
                # missing concept degrades the metric to ``None`` instead of
                # rejecting an otherwise complete issuer for the wrong reason.
                depreciation = _ttm_optional(
                    _labelled_sum(issuer_annual_dfc, None, None, "6.01", 4, DEPRECIATION_PATTERN),
                    _labelled_sum(issuer_dfc, reference, version, "6.01", 4, DEPRECIATION_PATTERN, "ÚLTIMO"),
                    _labelled_sum(issuer_dfc, reference, version, "6.01", 4, DEPRECIATION_PATTERN, "PENÚLTIMO"),
                )
                financial_expense = _ttm_optional(
                    _labelled_sum(issuer_annual_dre, None, None, "3.06", 3, FINANCIAL_EXPENSE_PATTERN),
                    _labelled_sum(issuer_dre, reference, version, "3.06", 3, FINANCIAL_EXPENSE_PATTERN, "ÚLTIMO"),
                    _labelled_sum(issuer_dre, reference, version, "3.06", 3, FINANCIAL_EXPENSE_PATTERN, "PENÚLTIMO"),
                )
                ebitda = None if ebit is None or depreciation is None else ebit + abs(depreciation)
            required = (net_income, equity) if issuer.is_financial else (revenue, ebit, net_income, cash, equity, cfo, investing)
            if not all(value is not None for value in required):
                raise RuntimeError(f"Incomplete standardized ITR accounts for {issuer.ticker}; review filing manually.")
            owner_cash_proxy = None if issuer.is_financial else cfo + investing
            invested_capital = equity + debt - (cash or 0.0)
            net_debt = debt - (cash or 0.0)
            if ebitda is None:
                leverage = None
            elif ebitda > 0:
                leverage = net_debt / ebitda
            else:
                # Negative trailing EBITDA is a distress signal, not a missing
                # value. Report it as leverage beyond any admissible limit so
                # the screen rejects it explicitly rather than by absence.
                leverage = DISTRESSED_LEVERAGE
            if financial_expense is None or ebit is None:
                coverage = None
            elif abs(financial_expense) > 0:
                coverage = ebit / abs(financial_expense)
            else:
                # No interest burden in the period: solvency is unconstrained
                # by coverage.  A finite sentinel keeps the CSV panel numeric.
                coverage = UNLEVERED_COVERAGE
            results.append(FundamentalSnapshot(
                ticker=issuer.ticker, as_of_date=reference.to_pydatetime(), available_date=filing.DT_RECEB.to_pydatetime(),
                sector=issuer.sector, is_financial=issuer.is_financial, market_cap_brl=market.market_cap_brl,
                price_to_earnings=market.market_cap_brl / net_income if net_income > 0 else None,
                price_to_book=market.market_cap_brl / equity if equity > 0 else None,
                ev_to_ebit=(market.market_cap_brl + debt - (cash or 0.0)) / ebit if ebit is not None and ebit > 0 else None,
                free_cash_flow_yield=None if owner_cash_proxy is None else owner_cash_proxy / market.market_cap_brl,
                roe=net_income / equity if equity > 0 else None,
                roic=None if issuer.is_financial or invested_capital <= 0 else ebit / invested_capital,
                debt_to_ebitda=leverage, interest_coverage=coverage,
                operating_margin=ebit / revenue if revenue is not None and revenue > 0 else None, revenue_growth_3y=None,
                average_daily_value_brl=market.average_daily_value_brl,
                source=(f"CVM ITR {itr_year}, ref {reference.date()}, receipt {filing.DT_RECEB.date()}; "
                        f"CVM DFP {itr_year - 1} TTM bridge on accumulated periods; "
                        "EBITDA = EBIT (3.05) + depreciation/amortisation add-back (6.01.01.x); "
                        "net debt = 2.01.04 + 2.02.01 - (1.01.01 + 1.01.02); "
                        "interest coverage = EBIT / CVM standardized financial expenses (3.06.02), "
                        "a broader concept than interest alone; "
                        f"market snapshot: {market.source}"),
            ))
        return results
