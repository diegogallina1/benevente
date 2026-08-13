"""Auditable mapping between a dated B3 universe and CVM reporting companies.

The B3 COTAHIST file identifies a traded issuer in a short display field; CVM
financial statements identify the reporting company by CNPJ.  They cannot be
joined safely by a loose name match.  This module produces a reviewable map:
only deterministic exact/prefix matches are accepted automatically and every
other candidate is retained as ``review_required``.  A reviewed override is
the only way to promote an ambiguous match for a research run.
"""
from __future__ import annotations

from pathlib import Path
import re
import unicodedata

import pandas as pd


MAP_COLUMNS = [
    "ticker", "isin", "issuer_name", "asset_class", "cnpj_cia", "cvm_name",
    "cvm_sector", "match_method", "confidence", "mapping_status", "source",
]


def normalise_name(value: str) -> str:
    """Return an accent/punctuation-free company-name key for matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char)).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def _format_cnpj(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 14:
        return None
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def load_cvm_company_master(path: str | Path) -> pd.DataFrame:
    """Load the official CVM open-company register with verified identifiers."""
    master = pd.read_csv(path, sep=";", encoding="latin1", dtype={"CNPJ_CIA": str}, low_memory=False)
    required = {"CNPJ_CIA", "DENOM_SOCIAL", "DENOM_COMERC", "SETOR_ATIV"}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"CVM company master missing columns: {sorted(missing)}")
    master = master.copy()
    master["CNPJ_CIA"] = master.CNPJ_CIA.str.replace(r"\D", "", regex=True).str.zfill(14)
    master["social_key"] = master.DENOM_SOCIAL.map(normalise_name)
    master["commercial_key"] = master.DENOM_COMERC.map(normalise_name)
    return master.drop_duplicates("CNPJ_CIA").reset_index(drop=True)


def load_b3_isin_database(directory: str | Path) -> pd.DataFrame:
    """Load the official B3 ISIN complete database as an ISIN/CNPJ bridge.

    The public download has two fixed-schema CSV-like files: ``EMISSOR.TXT``
    (B3 issuer code, legal name and CNPJ) and ``NUMERACA.TXT`` (ISIN and B3
    issuer code).  It is an identifier bridge, not a fundamental-data source.
    Keeping it external avoids committing a large, date-sensitive vendor file
    to the research repository.
    """
    directory = Path(directory)
    issuer_path = directory / "EMISSOR.TXT"
    issue_path = directory / "NUMERACA.TXT"
    if not issuer_path.exists() or not issue_path.exists():
        raise FileNotFoundError("Official B3 ISIN database must contain EMISSOR.TXT and NUMERACA.TXT")
    issuers = pd.read_csv(issuer_path, header=None, encoding="latin1", dtype=str)
    issues = pd.read_csv(issue_path, header=None, encoding="latin1", dtype=str)
    if issuers.shape[1] < 3 or issues.shape[1] < 4:
        raise ValueError("Unexpected official B3 ISIN database schema")
    issuers = issuers.iloc[:, [0, 2]].copy()
    issuers.columns = ["b3_issuer_code", "cnpj_cia"]
    issuers["b3_issuer_code"] = issuers.b3_issuer_code.str.zfill(4)
    issuers["cnpj_cia"] = issuers.cnpj_cia.str.replace(r"\D", "", regex=True).str.zfill(14)
    issues = issues.iloc[:, [2, 3]].copy()
    issues.columns = ["isin", "b3_issuer_code"]
    issues["isin"] = issues["isin"].str.upper().str.strip()
    issues["b3_issuer_code"] = issues["b3_issuer_code"].str.zfill(4)
    bridge = issues.merge(issuers, on="b3_issuer_code", how="inner")[["isin", "cnpj_cia"]]
    conflicts = bridge.groupby("isin").cnpj_cia.nunique()
    if (conflicts > 1).any():
        raise ValueError("Official B3 ISIN database has conflicting CNPJs for at least one ISIN")
    return bridge.drop_duplicates("isin").reset_index(drop=True)


def load_b3_issuer_database(directory: str | Path) -> pd.DataFrame:
    """Load official B3 issuer names and CNPJs for conservative fallback checks."""
    path = Path(directory) / "EMISSOR.TXT"
    if not path.exists():
        raise FileNotFoundError("Official B3 ISIN database must contain EMISSOR.TXT")
    issuers = pd.read_csv(path, header=None, encoding="latin1", dtype=str)
    if issuers.shape[1] < 3:
        raise ValueError("Unexpected official B3 issuer database schema")
    result = issuers.iloc[:, [1, 2]].copy()
    result.columns = ["issuer_name", "cnpj_cia"]
    result["cnpj_cia"] = result["cnpj_cia"].str.replace(r"\D", "", regex=True).str.zfill(14)
    result["issuer_key"] = result["issuer_name"].map(normalise_name)
    return result.drop_duplicates(["issuer_key", "cnpj_cia"]).reset_index(drop=True)


def _best_candidate(issuer_name: str, master: pd.DataFrame) -> tuple[pd.Series | None, str, float, str]:
    """Find a conservative candidate; uncertain short-name matches stay pending."""
    key = normalise_name(issuer_name)
    if not key:
        return None, "no_name", 0.0, "review_required"
    exact = master[(master.social_key == key) | (master.commercial_key == key)]
    if len(exact) == 1:
        return exact.iloc[0], "exact_normalised_name", 1.0, "accepted"
    # COTAHIST issuer field is truncated to 12 characters. A single CVM
    # company beginning with this key can be accepted only when the key is
    # long enough to be discriminative. Names like "BRASIL" must be reviewed.
    prefix = master[(master.social_key.str.startswith(key)) | (master.commercial_key.str.startswith(key))]
    if len(key) >= 7 and len(prefix) == 1:
        return prefix.iloc[0], "unique_cotahist_prefix", 0.97, "accepted"
    # Do not run a fuzzy auto-suggestion across the entire CVM register here.
    # It is both slow on a historical panel and, more importantly, too easy to
    # mistake an approximate name for accounting evidence. The reviewer can
    # resolve this issuer in the documented override file using official data.
    return None, "no_deterministic_cnpj_match", 0.0, "review_required"


def _read_overrides(path: str | Path | None) -> pd.DataFrame:
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=["ticker", "cnpj_cia", "reviewed_by", "reviewed_at", "note"])
    overrides = pd.read_csv(path, dtype=str).fillna("")
    required = {"ticker", "cnpj_cia"}
    missing = required - set(overrides.columns)
    if missing:
        raise ValueError(f"Manual mapping file missing columns: {sorted(missing)}")
    overrides["ticker"] = overrides.ticker.str.upper().str.strip()
    return overrides.drop_duplicates("ticker", keep="last")


def map_b3_equities(universe: pd.DataFrame, cvm_master: pd.DataFrame,
                    overrides_path: str | Path | None = None,
                    isin_cnpj: pd.DataFrame | None = None,
                    b3_issuers: pd.DataFrame | None = None) -> pd.DataFrame:
    """Map each dated equity ticker to a CVM company without silent guessing."""
    required = {"ticker", "issuer_name", "asset_class", "source"}
    missing = required - set(universe.columns)
    if missing:
        raise ValueError(f"B3 universe missing columns: {sorted(missing)}")
    equities = universe[universe.asset_class.eq("equity")].copy()
    cvm_master = cvm_master.copy()
    cvm_master["CNPJ_CIA"] = cvm_master["CNPJ_CIA"].astype(str).str.replace(r"\D", "", regex=True).str.zfill(14)
    if "social_key" not in cvm_master:
        cvm_master["social_key"] = cvm_master["DENOM_SOCIAL"].map(normalise_name)
    if "commercial_key" not in cvm_master:
        cvm_master["commercial_key"] = cvm_master["DENOM_COMERC"].map(normalise_name)
    overrides = _read_overrides(overrides_path).set_index("ticker")
    by_cnpj = cvm_master.set_index("CNPJ_CIA")
    isin_lookup: dict[str, str] = {}
    if isin_cnpj is not None:
        isin_required = {"isin", "cnpj_cia"}
        isin_missing = isin_required - set(isin_cnpj.columns)
        if isin_missing:
            raise ValueError(f"ISIN bridge missing columns: {sorted(isin_missing)}")
        isin_lookup = (isin_cnpj.dropna(subset=["isin", "cnpj_cia"])
                       .drop_duplicates("isin").set_index("isin").cnpj_cia.to_dict())
    issuer_prefix_lookup: dict[str, str] = {}
    if b3_issuers is not None:
        issuer_required = {"issuer_key", "cnpj_cia"}
        issuer_missing = issuer_required - set(b3_issuers.columns)
        if issuer_missing:
            raise ValueError(f"B3 issuer database missing columns: {sorted(issuer_missing)}")
        candidates = b3_issuers[b3_issuers["cnpj_cia"].isin(by_cnpj.index)].copy()
        candidates["prefix7"] = candidates["issuer_key"].str[:7]
        unique = candidates.groupby("prefix7")["cnpj_cia"].nunique()
        issuer_prefix_lookup = (candidates[candidates["prefix7"].isin(unique[unique.eq(1)].index)]
                                .drop_duplicates("prefix7").set_index("prefix7")["cnpj_cia"].to_dict())
    candidate_cache: dict[str, tuple[pd.Series | None, str, float, str]] = {}
    rows: list[dict] = []
    for item in equities.sort_values("ticker").itertuples():
        ticker = str(item.ticker).upper()
        override = overrides.loc[ticker] if ticker in overrides.index else None
        isin = str(getattr(item, "isin", "") or "").upper().strip()
        official_cnpj = isin_lookup.get(isin)
        if override is not None and override.cnpj_cia:
            if override.cnpj_cia not in by_cnpj.index:
                raise ValueError(f"Manual mapping for {ticker} references unknown CVM CNPJ {override.cnpj_cia}")
            candidate, method, confidence, status = by_cnpj.loc[override.cnpj_cia], "reviewed_manual_override", 1.0, "accepted"
        elif official_cnpj:
            if official_cnpj in by_cnpj.index:
                candidate, method, confidence, status = (
                    by_cnpj.loc[official_cnpj], "official_b3_isin_cnpj", 1.0, "accepted"
                )
            else:
                candidate, method, confidence, status = (
                    None, "b3_isin_cnpj_not_in_cvm_master", 1.0, "review_required"
                )
        else:
            issuer_key = normalise_name(item.issuer_name)
            fallback_cnpj = issuer_prefix_lookup.get(issuer_key[:7])
            if fallback_cnpj:
                candidate, method, confidence, status = (
                    by_cnpj.loc[fallback_cnpj], "official_b3_issuer_unique_prefix", 0.99, "accepted"
                )
            else:
                if issuer_key not in candidate_cache:
                    candidate_cache[issuer_key] = _best_candidate(item.issuer_name, cvm_master)
                candidate, method, confidence, status = candidate_cache[issuer_key]
        rows.append({
            "ticker": ticker,
            "isin": isin or None,
            "issuer_name": item.issuer_name,
            "asset_class": item.asset_class,
            "cnpj_cia": None if candidate is None else _format_cnpj(candidate.get("CNPJ_CIA", candidate.name)),
            "cvm_name": None if candidate is None else candidate["DENOM_SOCIAL"],
            "cvm_sector": None if candidate is None else candidate["SETOR_ATIV"],
            "match_method": method,
            "confidence": confidence,
            "mapping_status": status,
            "source": item.source,
        })
    return pd.DataFrame(rows, columns=MAP_COLUMNS)


def accepted_issuers(mapping: pd.DataFrame) -> pd.DataFrame:
    """Return only mappings that may be sent to the ITR/DFP ingestion gate."""
    accepted = mapping[mapping.mapping_status.eq("accepted")].copy()
    # Preferred and ordinary shares can legitimately map to the same reporting
    # company (e.g. ALPA3 and ALPA4).  The ingestion layer deduplicates CNPJ
    # filings while the portfolio layer retains the tradable share classes.
    if accepted["ticker"].duplicated().any():
        raise ValueError("Accepted mapping has duplicated tickers; resolve the mapping before ingestion.")
    return accepted


def coverage_summary(mapping: pd.DataFrame) -> pd.DataFrame:
    """Summarise mapping readiness instead of claiming full fundamental coverage."""
    summary = mapping.groupby(["mapping_status", "match_method"], dropna=False).size().reset_index(name="tickers")
    summary["share_of_equities"] = summary["tickers"] / max(len(mapping), 1)
    return summary.sort_values(["mapping_status", "tickers"], ascending=[True, False]).reset_index(drop=True)
