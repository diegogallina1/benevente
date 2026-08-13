"""Validate a dated B3--CVM issuer map for a current ITR refresh."""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path

import pandas as pd

from cvm_fundamentals import Issuer


REQUIRED_COLUMNS = {"ticker", "cnpj_cia", "cvm_sector", "mapping_status", "observed_at", "source"}


def _ticker_key(value: object) -> str:
    return str(value or "").upper().strip().removesuffix(".SA")


def _cnpj_key(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 14:
        raise ValueError("CNPJ must contain exactly 14 digits")
    return digits


def _is_financial(sector: object) -> bool:
    name = str(sector or "").upper()
    return any(word in name for word in ("BANCO", "FINANCE", "SEGUR", "PREVID", "HOLDING FINANCE"))


@dataclass(frozen=True)
class LiveIssuerMap:
    issuers: tuple[Issuer, ...]
    coverage: pd.DataFrame


def load_live_issuer_map(path: str | Path, market_tickers: set[str], decision_date: pd.Timestamp,
                         max_age_days: int = 120) -> LiveIssuerMap:
    """Return only current, accepted equity mappings with dated evidence.

    The caller's market snapshot defines what is tradeable.  A mapping cannot
    silently add an absent ticker, and an old mapping cannot be carried into a
    live decision without an explicit refresh.
    """
    frame = pd.read_csv(path, dtype=str)
    if missing := REQUIRED_COLUMNS - set(frame.columns):
        raise ValueError(f"Issuer map missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["ticker_key"] = frame.ticker.map(_ticker_key)
    frame["observed_at"] = pd.to_datetime(frame.observed_at, errors="coerce")
    market_by_key = {_ticker_key(ticker): ticker for ticker in market_tickers}
    if frame.ticker_key.duplicated().any():
        duplicated = sorted(frame.loc[frame.ticker_key.duplicated(keep=False), "ticker_key"].unique())
        raise ValueError(f"Issuer map has duplicate ticker mappings: {duplicated}")
    issuers: list[Issuer] = []
    coverage: list[dict[str, str]] = []
    for key, ticker in sorted(market_by_key.items()):
        mapped = frame[frame.ticker_key.eq(key)]
        if mapped.empty:
            coverage.append({"ticker": ticker, "status": "blocked", "reason": "missing_b3_cvm_mapping"})
            continue
        record = mapped.iloc[0]
        if record.mapping_status != "accepted":
            coverage.append({"ticker": ticker, "status": "blocked", "reason": "mapping_not_accepted"})
            continue
        observed = record.observed_at
        if pd.isna(observed) or observed > decision_date:
            coverage.append({"ticker": ticker, "status": "blocked", "reason": "mapping_after_decision_date"})
            continue
        if (decision_date - observed).days > max_age_days:
            coverage.append({"ticker": ticker, "status": "blocked", "reason": "mapping_too_old"})
            continue
        if not str(record.source or "").strip():
            coverage.append({"ticker": ticker, "status": "blocked", "reason": "mapping_source_missing"})
            continue
        try:
            cnpj = _cnpj_key(record.cnpj_cia)
        except ValueError:
            coverage.append({"ticker": ticker, "status": "blocked", "reason": "invalid_cnpj"})
            continue
        issuers.append(Issuer(ticker, cnpj, str(record.cvm_sector), _is_financial(record.cvm_sector)))
        coverage.append({"ticker": ticker, "status": "accepted", "reason": ""})
    return LiveIssuerMap(tuple(issuers), pd.DataFrame(coverage))
