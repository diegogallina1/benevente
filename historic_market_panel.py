"""Build dated January B3 market snapshots from public CVM FRE and prices.

This is intentionally a *coverage builder*, not a gap-filler.  It downloads
only public FRE files, chooses a filing received no later than each January
decision, obtains the last 60 prior trading days and creates an explicit
coverage report. Ambiguous share classes or unavailable price observations are
reported and omitted rather than substituted with current market capitalisation.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import yfinance as yf

from cvm_fundamentals import BRAZIL_ISSUERS, Issuer


FRE_URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/FRE/DADOS/fre_cia_aberta_{year}.zip"


@dataclass(frozen=True)
class ShareClassRule:
    ticker: str
    preferred: bool


SHARE_CLASS_RULES = {
    issuer.ticker: ShareClassRule(issuer.ticker, issuer.ticker[4] == "4")
    for issuer in BRAZIL_ISSUERS
}


def _read(archive: ZipFile, name: str) -> pd.DataFrame:
    return pd.read_csv(archive.open(name), sep=";", encoding="latin1", low_memory=False)


def _package(year: int, cache: Path) -> ZipFile:
    import requests
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"fre_cia_aberta_{year}.zip"
    if not path.exists():
        response = requests.get(FRE_URL.format(year=year), timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
    return ZipFile(path)


def _shares_for_decision(issuer: Issuer, decision: pd.Timestamp, cache: Path) -> tuple[float, str]:
    """Return an unambiguous share count from a FRE received before decision."""
    # The previous package may contain only filings received after the January
    # decision. Search one additional historical archive and retain the newest
    # receipt strictly no later than the decision date.
    candidates: list[tuple[pd.Timestamp, int, pd.DataFrame]] = []
    for year in (decision.year - 2, decision.year - 1, decision.year):
        with _package(year, cache) as archive:
            names = set(archive.namelist())
            index_name = f"fre_cia_aberta_{year}.csv"
            capital_name = f"fre_cia_aberta_capital_social_classe_acao_{year}.csv"
            total_capital_name = f"fre_cia_aberta_capital_social_{year}.csv"
            if index_name not in names or capital_name not in names or total_capital_name not in names:
                continue
            index = _read(archive, index_name)
            index["DT_RECEB"] = pd.to_datetime(index.DT_RECEB, errors="coerce")
            filings = index[(index.CNPJ_CIA == issuer.cnpj) & (index.DT_RECEB <= decision)].copy()
            if filings.empty:
                continue
            filing = filings.sort_values(["DT_RECEB", "VERSAO", "ID_DOC"]).iloc[-1]
            capital = _read(archive, capital_name)
            capital = capital[capital.ID_Documento == filing.ID_DOC].copy()
            if capital.empty:
                total = _read(archive, total_capital_name)
                total = total[(total.ID_Documento == filing.ID_DOC) & (total.Tipo_Capital == "Capital Integralizado")].copy()
                if total.empty:
                    continue
                rule = SHARE_CLASS_RULES[issuer.ticker]
                column = "Quantidade_Acoes_Preferenciais" if rule.preferred else "Quantidade_Acoes_Ordinarias"
                quantities = pd.to_numeric(total[column], errors="coerce").dropna()
                quantities = quantities[quantities > 0].drop_duplicates()
                if len(quantities) != 1:
                    raise ValueError(f"ambiguous_or_missing_share_class:{issuer.ticker}:{filing.ID_DOC}")
                candidates.append((pd.Timestamp(filing.DT_RECEB), int(filing.ID_DOC), total.assign(_shares=float(quantities.iloc[0]))))
                continue
            kind = capital["Tipo_Classe_Acao_Preferencial"].fillna("").astype(str).str.lower()
            is_preferred = kind.str.contains("preferencial")
            rule = SHARE_CLASS_RULES[issuer.ticker]
            class_rows = capital[is_preferred] if rule.preferred else capital[~is_preferred]
            quantities = pd.to_numeric(class_rows.Quantidade_Acoes, errors="coerce").dropna()
            quantities = quantities[quantities > 0].drop_duplicates()
            if len(quantities) != 1:
                # Older FRE files sometimes have capital rows but no class
                # detail. The total-capital table remains a first-party
                # fallback because it exposes ON and PN quantities directly.
                total = _read(archive, total_capital_name)
                total = total[(total.ID_Documento == filing.ID_DOC) & (total.Tipo_Capital == "Capital Integralizado")].copy()
                column = "Quantidade_Acoes_Preferenciais" if rule.preferred else "Quantidade_Acoes_Ordinarias"
                quantities = pd.to_numeric(total[column], errors="coerce").dropna()
                quantities = quantities[quantities > 0].drop_duplicates()
            if len(quantities) != 1:
                raise ValueError(f"ambiguous_or_missing_share_class:{issuer.ticker}:{filing.ID_DOC}")
            candidates.append((pd.Timestamp(filing.DT_RECEB), int(filing.ID_DOC), capital.assign(_shares=float(quantities.iloc[0]))))
    if not candidates:
        raise ValueError(f"no_fre_share_count:{issuer.ticker}")
    received, doc_id, frame = max(candidates, key=lambda item: (item[0], item[1]))
    return float(frame._shares.iloc[0]), f"CVM FRE document {doc_id}, received {received.date()}"


def _market_observation(issuer: Issuer, decision: pd.Timestamp, shares: float, source: str) -> dict:
    history = yf.Ticker(issuer.ticker).history(
        start=(decision - pd.Timedelta(days=100)).strftime("%Y-%m-%d"),
        end=decision.strftime("%Y-%m-%d"), auto_adjust=False,
    )
    history = history.loc[history.index.tz_localize(None) < decision].copy()
    if len(history) < 20:
        raise ValueError(f"insufficient_prior_price_volume_history:{issuer.ticker}")
    last = history.iloc[-1]
    average_value = float((history["Close"] * history["Volume"]).tail(60).mean())
    close = float(last.Close)
    if close <= 0 or average_value <= 0:
        raise ValueError(f"invalid_price_or_volume:{issuer.ticker}")
    observed = pd.Timestamp(history.index[-1]).tz_localize(None)
    return {
        "decision_date": decision.date().isoformat(), "ticker": issuer.ticker,
        "observed_at": observed.isoformat(), "market_cap_brl": close * shares,
        "average_daily_value_brl": average_value, "close_price_brl": close,
        "lot_size": 1, "source": f"{source}; Yahoo Finance historical OHLCV through {observed.date()}",
    }


def build_market_panel(start_year: int, end_year: int, cache_dir: str | Path = "work/cvm_cache") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return accepted dated rows and a full accepted/blocked coverage report."""
    cache = Path(cache_dir)
    accepted: list[dict] = []
    report: list[dict] = []
    for year in range(start_year, end_year + 1):
        decision = pd.Timestamp(year=year, month=1, day=1)
        for issuer in BRAZIL_ISSUERS:
            try:
                shares, fre_source = _shares_for_decision(issuer, decision, cache)
                accepted.append(_market_observation(issuer, decision, shares, fre_source))
                report.append({"decision_date": decision.date().isoformat(), "ticker": issuer.ticker,
                               "status": "accepted", "reason": ""})
            except Exception as exc:
                report.append({"decision_date": decision.date().isoformat(), "ticker": issuer.ticker,
                               "status": "blocked", "reason": str(exc)})
    return pd.DataFrame(accepted), pd.DataFrame(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build public-source dated market panel for January walk-forward.")
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=pd.Timestamp.now().year)
    parser.add_argument("--output", default="data/market_snapshot_panel.csv")
    parser.add_argument("--coverage-report", default="artifacts/historic_market_coverage.csv")
    parser.add_argument("--cache-dir", default="work/cvm_cache")
    args = parser.parse_args()
    panel, coverage = build_market_panel(args.start_year, args.end_year, args.cache_dir)
    output, report = Path(args.output), Path(args.coverage_report)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False); coverage.to_csv(report, index=False)
    print(f"Accepted {len(panel)} dated observations; blocked {(coverage.status == 'blocked').sum()}. Panel: {output}; coverage: {report}")


if __name__ == "__main__":
    main()
