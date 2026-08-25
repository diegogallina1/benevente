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


def assert_same_ledger(published, expected, path: str = "") -> None:
    """Compare structure exactly and numbers within floating-point tolerance.

    The published ledger and a fresh build agree on every ticker, year and
    weight, but not always on the last bit: a weight that sums to 0.5 in one
    summation order lands on 0.5000000000000001 in another. Exact equality
    turned that into a permanently failing test, which is worse than no test,
    because a real staleness -- a changed weight, a dropped year, a different
    ticker -- stops being visible among the noise.
    """
    assert type(published) is type(expected), f"{path}: {type(published)} != {type(expected)}"
    if isinstance(expected, dict):
        assert set(published) == set(expected), f"{path}: chaves diferentes"
        for key in expected:
            assert_same_ledger(published[key], expected[key], f"{path}.{key}")
    elif isinstance(expected, list):
        assert len(published) == len(expected), f"{path}: {len(published)} itens vs {len(expected)}"
        for index, (left, right) in enumerate(zip(published, expected)):
            assert_same_ledger(left, right, f"{path}[{index}]")
    elif isinstance(expected, float):
        assert published == pytest.approx(expected, abs=1e-12), f"{path}: {published} != {expected}"
    else:
        assert published == expected, f"{path}: {published} != {expected}"


def test_published_ledger_matches_the_builder() -> None:
    expected = MODULE.build_ledger(
        ROOT / "web" / "annual_research.json",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_annual_comparison.csv",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_daily_comparison.csv",
    )
    published = json.loads((ROOT / "web" / "strategy_decisions.json").read_text(encoding="utf-8"))
    assert_same_ledger(published, expected)


def test_the_comparison_still_catches_a_stale_published_ledger() -> None:
    """A tolerance that hides a real change would be worse than the strict test."""
    expected = MODULE.build_ledger(
        ROOT / "web" / "annual_research.json",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_annual_comparison.csv",
        ROOT / "artifacts" / "benevente2_event_risk" / "candidate_daily_comparison.csv",
    )
    stale = json.loads(json.dumps(expected))
    stale["annual_decisions"][0]["allocation"][0]["weight"] += 1e-6
    with pytest.raises(AssertionError):
        assert_same_ledger(stale, expected)
    dropped = json.loads(json.dumps(expected))
    dropped["risk_transitions"].pop()
    with pytest.raises(AssertionError):
        assert_same_ledger(dropped, expected)
