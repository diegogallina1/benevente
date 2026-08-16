"""Evidence gate for annual B3/CVM walk-forward decisions.

A fundamental observation alone is not sufficient to enter an annual test: the
share must have existed in that year's B3 universe and have an accepted,
auditable CVM identifier link.  This module freezes that eligibility before
the performance period begins.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DecisionEvidence:
    """Accepted B3/CVM tickers at every annual decision date."""
    allowed_by_date: dict[pd.Timestamp, frozenset[str]]
    issuer_by_date: dict[pd.Timestamp, dict[str, str]]

    def allows(self, decision_date: pd.Timestamp, ticker: str) -> bool:
        return ticker in self.allowed_by_date.get(pd.Timestamp(decision_date).normalize(), frozenset())

    def allowed(self, decision_date: pd.Timestamp) -> frozenset[str]:
        return self.allowed_by_date.get(pd.Timestamp(decision_date).normalize(), frozenset())

    def issuer_ids(self, decision_date: pd.Timestamp) -> dict[str, str]:
        """Return the economic issuer for each permitted share class.

        Tickers without a reliable company identifier deliberately fall back to
        themselves.  They therefore never create a false link with another
        listed company, while PETR3/PETR4-style classes share one exposure.
        """
        return self.issuer_by_date.get(pd.Timestamp(decision_date).normalize(), {})


def build_decision_evidence(universe: pd.DataFrame, mapping: pd.DataFrame) -> tuple[DecisionEvidence, pd.DataFrame]:
    """Build a dated eligibility gate and an annual coverage manifest.

    The join is deliberately keyed by both decision year and ticker.  A
    company that lists later is not retroactively added to an older January;
    an accepted CNPJ mapping for a different year is also insufficient.
    """
    universe_required = {"decision_date", "universe_year", "ticker", "asset_class"}
    mapping_required = {"universe_year", "ticker", "mapping_status"}
    if missing := universe_required - set(universe.columns):
        raise ValueError(f"B3 universe missing columns: {sorted(missing)}")
    if missing := mapping_required - set(mapping.columns):
        raise ValueError(f"CVM mapping missing columns: {sorted(missing)}")
    b3 = universe[universe.asset_class.eq("equity")].copy()
    b3["decision_date"] = pd.to_datetime(b3.decision_date).dt.normalize()
    mapping_for_join = mapping.copy()
    if "cnpj_cia" not in mapping_for_join:
        mapping_for_join["cnpj_cia"] = None
    accepted = mapping_for_join[mapping_for_join.mapping_status.eq("accepted")][["universe_year", "ticker", "cnpj_cia"]].drop_duplicates()
    joined = b3.merge(accepted, on=["universe_year", "ticker"], how="inner")
    allowed = {
        decision: frozenset(group.ticker)
        for decision, group in joined.groupby("decision_date", sort=True)
    }
    issuer_by_date = {
        decision: {
            row.ticker: str(row.cnpj_cia) if pd.notna(row.cnpj_cia) and str(row.cnpj_cia).strip() else row.ticker
            for row in group.itertuples(index=False)
        }
        for decision, group in joined.groupby("decision_date", sort=True)
    }
    manifest = (b3.groupby(["universe_year", "decision_date"]).size().rename("b3_equities").reset_index()
                .merge(joined.groupby(["universe_year", "decision_date"]).size().rename("accepted_identifier_equities").reset_index(),
                       on=["universe_year", "decision_date"], how="left"))
    manifest["accepted_identifier_equities"] = manifest.accepted_identifier_equities.fillna(0).astype(int)
    manifest["accepted_identifier_share"] = manifest.accepted_identifier_equities / manifest.b3_equities
    manifest["decision_date"] = pd.to_datetime(manifest["decision_date"]).dt.date.astype(str)
    return DecisionEvidence(allowed, issuer_by_date), manifest.sort_values("decision_date").reset_index(drop=True)


def load_decision_evidence(universe_path: str | Path, mapping_path: str | Path) -> tuple[DecisionEvidence, pd.DataFrame]:
    """Read dated source files; no current-universe substitution is allowed."""
    universe = pd.read_csv(universe_path, dtype={"ticker": str})
    mapping = pd.read_csv(mapping_path, dtype={"ticker": str, "cnpj_cia": str})
    return build_decision_evidence(universe, mapping)
