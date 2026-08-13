"""Create a full-universe, point-in-time CVM fundamental panel.

This is the third and final gate of the B3--CVM coverage build.  It starts
with every dated B3 equity, retains only mappings accepted by the auditable
identifier bridge, derives market capitalisation from that January's COTAHIST
price and a FRE share count available then, and finally uses only an ITR/DFP
filing received by the decision date.  A rejected row is recorded rather than
silently filled with current data.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from cvm_fundamentals import Issuer, _read_csv_from_zip
from cvm_itr import CvmItrClient
from market_snapshot import MarketSnapshot


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or "")).zfill(14)


def _financial_sector(value: object) -> bool:
    sector = str(value or "").upper()
    return any(term in sector for term in ("BANCO", "FINANCE", "SEGUR", "PREVID", "HOLDING FINANCE"))


def _share_kind(specification: object) -> tuple[str, str | None]:
    """Map the dated B3 descriptor to an unambiguous FRE share-count class."""
    spec = str(specification or "").upper().strip()
    if spec.startswith("ON"):
        return "ordinary", None
    # COTAHIST appends custody/status suffixes (e.g. ``PN EDJ N2``). They
    # are not a preferred *class* and must use the aggregate PN count.
    if re.match(r"^PN(?:\s|$)", spec):
        return "preferred", None
    match = re.match(r"^PN([A-Z])", spec.replace(" ", ""))
    if match:
        return "preferred_class", match.group(1)
    raise ValueError(f"unsupported_share_class:{specification}")


class FreShareResolver:
    """Resolve historical share counts from public FRE packages with caching."""
    def __init__(self, cache_dir: str | Path) -> None:
        self.cache_dir = Path(cache_dir)
        self._panels: dict[int, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] = {}

    def _panel(self, year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        cached = self._panels.get(year)
        if cached is not None:
            return cached
        path = self.cache_dir / f"fre_cia_aberta_{year}.zip"
        if not path.exists():
            raise FileNotFoundError(f"missing_cvm_fre_archive:{year}")
        with ZipFile(path) as archive:
            names = set(archive.namelist())
            index_name = f"fre_cia_aberta_{year}.csv"
            total_name = f"fre_cia_aberta_capital_social_{year}.csv"
            class_name = f"fre_cia_aberta_capital_social_classe_acao_{year}.csv"
            if not {index_name, total_name, class_name}.issubset(names):
                raise ValueError(f"incomplete_cvm_fre_schema:{year}")
            index = pd.read_csv(archive.open(index_name), sep=";", encoding="latin1", dtype=str, low_memory=False)
            total = pd.read_csv(archive.open(total_name), sep=";", encoding="latin1", dtype=str, low_memory=False)
            classes = pd.read_csv(archive.open(class_name), sep=";", encoding="latin1", dtype=str, low_memory=False)
        index["cnpj"] = index["CNPJ_CIA"].map(_digits)
        index["DT_RECEB"] = pd.to_datetime(index["DT_RECEB"], errors="coerce")
        total["cnpj"] = total["CNPJ_Companhia"].map(_digits)
        classes["cnpj"] = classes["CNPJ_Companhia"].map(_digits)
        self._panels[year] = (index, total, classes)
        return self._panels[year]

    @staticmethod
    def _one_number(values: pd.Series, reason: str) -> float:
        parsed = pd.to_numeric(values, errors="coerce").dropna()
        parsed = parsed[parsed > 0].drop_duplicates()
        if len(parsed) != 1:
            raise ValueError(reason)
        return float(parsed.iloc[0])

    def shares(self, cnpj: str, specification: object, decision: pd.Timestamp) -> tuple[float, str]:
        kind, preferred_class = _share_kind(specification)
        candidates: list[tuple[pd.Timestamp, int, float]] = []
        # FRE records can be amended.  Search a rolling three-package window
        # and select the last receipt that was public at the decision date.
        for year in range(decision.year - 2, decision.year + 1):
            index, total, classes = self._panel(year)
            filings = index[(index["cnpj"] == _digits(cnpj)) & (index["DT_RECEB"] <= decision)].copy()
            if filings.empty:
                continue
            filing = filings.sort_values(["DT_RECEB", "VERSAO", "ID_DOC"]).iloc[-1]
            doc_id = str(filing["ID_DOC"])
            total_rows = total[(total["cnpj"] == _digits(cnpj)) & (total["ID_Documento"].astype(str) == doc_id)].copy()
            total_rows = total_rows[total_rows["Tipo_Capital"].fillna("").str.contains("Integralizado", case=False)]
            # Some FRE amendments carry a new index document before the
            # capital-social section is refiled. In that case retain the
            # newest capital document that was public no later than the same
            # decision; never use a later filing to fill the gap.
            if total_rows.empty:
                company_total = total[total["cnpj"] == _digits(cnpj)].copy()
                company_total["ID_Documento_num"] = pd.to_numeric(company_total["ID_Documento"], errors="coerce")
                company_total = company_total[company_total["ID_Documento_num"] <= int(doc_id)]
                company_total = company_total[company_total["Tipo_Capital"].fillna("").str.contains("Integralizado", case=False)]
                if not company_total.empty:
                    last_capital_doc = company_total["ID_Documento_num"].max()
                    total_rows = company_total[company_total["ID_Documento_num"] == last_capital_doc]
            # A newer annual FRE ZIP can have a fresh index filing but omit
            # the historical capital table altogether. Skip that package and
            # let the previous package's still-public capital filing supply
            # the count; it remains point-in-time valid.
            if total_rows.empty:
                continue
            if kind == "ordinary":
                shares = self._one_number(total_rows["Quantidade_Acoes_Ordinarias"], "ambiguous_ordinary_share_count")
            elif kind == "preferred":
                shares = self._one_number(total_rows["Quantidade_Acoes_Preferenciais"], "ambiguous_preferred_share_count")
            else:
                class_rows = classes[(classes["cnpj"] == _digits(cnpj)) & (classes["ID_Documento"].astype(str) == doc_id)].copy()
                label = class_rows["Tipo_Classe_Acao_Preferencial"].fillna("").str.upper()
                class_rows = class_rows[label.str.contains(f"CLASSE {preferred_class}", regex=False)]
                shares = self._one_number(class_rows["Quantidade_Acoes"], "ambiguous_preferred_class_share_count")
            candidates.append((pd.Timestamp(filing["DT_RECEB"]), int(doc_id), shares))
        if not candidates:
            raise ValueError("no_fre_share_count")
        received, document, shares = max(candidates, key=lambda item: (item[0], item[1]))
        return shares, f"CVM FRE document {document}, received {received.date()}"


def build_full_panel(universe: pd.DataFrame, mapping: pd.DataFrame, start_year: int, end_year: int,
                     cache_dir: str | Path = "work/cvm_cache") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the generic B3/CVM panel and a row-level coverage report."""
    required_universe = {"universe_year", "ticker", "specification", "close_price_brl", "average_daily_value_brl", "observed_at"}
    required_mapping = {"universe_year", "ticker", "cnpj_cia", "cvm_sector", "mapping_status"}
    if missing := required_universe - set(universe.columns):
        raise ValueError(f"universe missing columns: {sorted(missing)}")
    if missing := required_mapping - set(mapping.columns):
        raise ValueError(f"mapping missing columns: {sorted(missing)}")
    selected = universe.merge(mapping[mapping.mapping_status.eq("accepted")], on=["universe_year", "ticker"], how="inner", suffixes=("", "_map"))
    selected = selected[selected.universe_year.between(start_year, end_year)].copy()
    resolver = FreShareResolver(cache_dir)
    itr = CvmItrClient(cache_dir)
    rows: list[dict] = []
    coverage: list[dict] = []
    for year, frame in selected.groupby("universe_year", sort=True):
        decision = pd.Timestamp(frame.decision_date.iloc[0])
        for item in frame.itertuples(index=False):
            try:
                shares, fre_source = resolver.shares(item.cnpj_cia, item.specification, decision)
                close = float(item.close_price_brl)
                if close <= 0 or float(item.average_daily_value_brl) <= 0:
                    raise ValueError("invalid_cotahist_market_observation")
                market = MarketSnapshot(
                    ticker=item.ticker, observed_at=pd.Timestamp(item.observed_at).to_pydatetime(),
                    market_cap_brl=close * shares, average_daily_value_brl=float(item.average_daily_value_brl),
                    close_price_brl=close, lot_size=1,
                    source=f"B3 COTAHIST {item.observed_at}; {fre_source}",
                )
                issuer = Issuer(item.ticker, item.cnpj_cia, str(item.cvm_sector), _financial_sector(item.cvm_sector))
                snapshots = itr.live_snapshots(int(year) - 1, decision, {item.ticker: market}, issuers=(issuer,))
                snapshot = snapshots[0].model_dump()
                snapshot["decision_date"] = decision.date().isoformat()
                snapshot["mapping_method"] = item.match_method
                snapshot["snapshot_vintage"] = "B3/CVM point-in-time full-universe gate"
                rows.append(snapshot)
                coverage.append({"decision_date": decision.date().isoformat(), "ticker": item.ticker,
                                 "status": "accepted", "reason": ""})
            except Exception as exc:
                coverage.append({"decision_date": decision.date().isoformat(), "ticker": item.ticker,
                                 "status": "blocked", "reason": str(exc)})
        itr.clear_cached_panels()
    return pd.DataFrame(rows), pd.DataFrame(coverage)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build full-universe point-in-time B3/CVM fundamentals.")
    parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True)
    parser.add_argument("--start-year", type=int, default=2013)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--cache-dir", default="work/cvm_cache")
    parser.add_argument("--output", default="data/fundamentals_b3_cvm_full.csv")
    parser.add_argument("--coverage-report", default="artifacts/fundamentals_b3_cvm_full_coverage.csv")
    args = parser.parse_args()
    panel, coverage = build_full_panel(
        pd.read_csv(args.universe, dtype={"ticker": str, "isin": str}),
        pd.read_csv(args.mapping, dtype={"ticker": str, "isin": str, "cnpj_cia": str}),
        args.start_year, args.end_year, args.cache_dir,
    )
    output, report = Path(args.output), Path(args.coverage_report)
    output.parent.mkdir(parents=True, exist_ok=True); report.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(output, index=False); coverage.to_csv(report, index=False)
    print(f"Accepted {len(panel)}/{len(coverage)} full-universe fundamental snapshots. Panel: {output}; coverage: {report}")


if __name__ == "__main__":
    main()
