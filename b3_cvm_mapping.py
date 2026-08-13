"""Auditable mapping between a dated B3 universe and CVM reporting companies.

The B3 COTAHIST file identifies a traded issuer in a short display field; CVM
financial statements identify the reporting company by CNPJ.  They cannot be
joined safely by a loose name match.  This module produces a reviewable map:
only deterministic exact/prefix matches are accepted automatically and every
other candidate is retained as ``review_required``.  A reviewed override is
the only way to promote an ambiguous match for a research run.
"""
from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path
import re
import unicodedata

import pandas as pd


MAP_COLUMNS = [
    "ticker", "issuer_name", "asset_class", "cnpj_cia", "cvm_name",
    "cvm_sector", "match_method", "confidence", "mapping_status", "source",
]


def normalise_name(value: str) -> str:
    """Return an accent/punctuation-free company-name key for matching."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char)).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def load_cvm_company_master(path: str | Path) -> pd.DataFrame:
    """Load the official CVM open-company register with verified identifiers."""
    master = pd.read_csv(path, sep=";", encoding="latin1", dtype={"CNPJ_CIA": str}, low_memory=False)
    required = {"CNPJ_CIA", "DENOM_SOCIAL", "DENOM_COMERC", "SETOR_ATIV"}
    missing = required - set(master.columns)
    if missing:
        raise ValueError(f"CVM company master missing columns: {sorted(missing)}")
    master = master.copy()
    master["CNPJ_CIA"] = master.CNPJ_CIA.str.strip()
    master["social_key"] = master.DENOM_SOCIAL.map(normalise_name)
    master["commercial_key"] = master.DENOM_COMERC.map(normalise_name)
    return master.drop_duplicates("CNPJ_CIA").reset_index(drop=True)


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
    candidates = master.copy()
    candidates["similarity"] = candidates.apply(
        lambda item: max(SequenceMatcher(None, key, item.social_key).ratio(),
                         SequenceMatcher(None, key, item.commercial_key).ratio()), axis=1)
    best = candidates.sort_values("similarity", ascending=False).iloc[0]
    return best, "fuzzy_candidate_requires_review", float(best.similarity), "review_required"


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
                    overrides_path: str | Path | None = None) -> pd.DataFrame:
    """Map each dated equity ticker to a CVM company without silent guessing."""
    required = {"ticker", "issuer_name", "asset_class", "source"}
    missing = required - set(universe.columns)
    if missing:
        raise ValueError(f"B3 universe missing columns: {sorted(missing)}")
    equities = universe[universe.asset_class.eq("equity")].copy()
    overrides = _read_overrides(overrides_path).set_index("ticker")
    by_cnpj = cvm_master.set_index("CNPJ_CIA")
    rows: list[dict] = []
    for item in equities.sort_values("ticker").itertuples():
        ticker = str(item.ticker).upper()
        override = overrides.loc[ticker] if ticker in overrides.index else None
        if override is not None and override.cnpj_cia:
            if override.cnpj_cia not in by_cnpj.index:
                raise ValueError(f"Manual mapping for {ticker} references unknown CVM CNPJ {override.cnpj_cia}")
            candidate, method, confidence, status = by_cnpj.loc[override.cnpj_cia], "reviewed_manual_override", 1.0, "accepted"
        else:
            candidate, method, confidence, status = _best_candidate(item.issuer_name, cvm_master)
        rows.append({
            "ticker": ticker,
            "issuer_name": item.issuer_name,
            "asset_class": item.asset_class,
            "cnpj_cia": None if candidate is None else candidate.CNPJ_CIA,
            "cvm_name": None if candidate is None else candidate.DENOM_SOCIAL,
            "cvm_sector": None if candidate is None else candidate.SETOR_ATIV,
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
    if accepted.ticker.duplicated().any():
        raise ValueError("Accepted mapping has duplicated tickers; resolve the mapping before ingestion.")
    return accepted


def coverage_summary(mapping: pd.DataFrame) -> pd.DataFrame:
    """Summarise mapping readiness instead of claiming full fundamental coverage."""
    summary = mapping.groupby(["mapping_status", "match_method"], dropna=False).size().reset_index(name="tickers")
    summary["share_of_equities"] = summary.tickers / max(len(mapping), 1)
    return summary.sort_values(["mapping_status", "tickers"], ascending=[True, False]).reset_index(drop=True)
