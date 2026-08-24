import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_strategy_decision_ledger", ROOT / "tools" / "build_strategy_decision_ledger.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_ledger_contains_every_annual_and_risk_decision() -> None:
    result = MODULE.build_ledger(
        ROOT / "web" / "annual_research.json",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_annual_comparison.csv",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_daily_comparison.csv",
    )
    assert len(result["annual_decisions"]) == 11
    assert [row["year"] for row in result["annual_decisions"]] == list(range(2015, 2026))
    assert len(result["risk_transitions"]) == 38
    for row in result["annual_decisions"]:
        assert sum(item["weight"] for item in row["allocation"]) == pytest.approx(1.0, abs=1e-8)
        assert len(row["decision_evidence_sha256"]) == 64
    for transition in result["risk_transitions"]:
        assert sum(item["weight"] for item in transition["target_allocation"]) == pytest.approx(1.0, abs=1e-8)


def test_published_ledger_matches_the_builder() -> None:
    expected = MODULE.build_ledger(
        ROOT / "web" / "annual_research.json",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_annual_comparison.csv",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_daily_comparison.csv",
    )
    published = json.loads((ROOT / "web" / "strategy_decisions.json").read_text(encoding="utf-8"))
    assert published == expected
