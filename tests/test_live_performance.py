import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "update_live_performance", ROOT / "tools" / "update_live_performance.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def fixture_inputs():
    decision = {
        "decision_date": "2026-01-02",
        "holdings": [
            {"ticker": "AAA3", "weight": 0.30},
            {"ticker": "BBB3", "weight": 0.25},
        ],
        "cdi_weight": 0.45,
    }
    series = {
        "AAA3": {"2026-01-02": 10.0, "2026-01-05": 11.0, "2026-01-06": 12.0},
        "BBB3": {"2026-01-02": 20.0, "2026-01-05": 18.0, "2026-01-06": 20.0},
        "BOVA11": {"2026-01-02": 100.0, "2026-01-05": 105.0, "2026-01-06": 110.0},
        "IBOVESPA": {"2026-01-02": 100_000.0, "2026-01-05": 102_000.0, "2026-01-06": 103_000.0},
    }
    cdi = {"2026-01-02": 0.001, "2026-01-05": 0.001, "2026-01-06": 0.001}
    return decision, series, cdi


def test_builds_buy_and_hold_without_rebalancing() -> None:
    decision, series, cdi = fixture_inputs()
    result = MODULE.build_live_document(
        decision,
        series,
        cdi,
        {"fixture": "0" * 64},
        generated_at=datetime(2026, 1, 7, tzinfo=timezone.utc),
    )
    expected = 0.30 * 1.20 + 0.25 * 1.00 + 0.45 * (1.001**2)
    assert result["summary"]["portfolio_return"] == pytest.approx(expected - 1.0)
    assert result["summary"]["equity_sleeve_return"] == pytest.approx(
        (0.30 * 1.20 + 0.25) / 0.55 - 1.0
    )
    assert result["summary"]["bova11_return"] == pytest.approx(0.10)
    assert result["summary"]["ibovespa_price_return"] == pytest.approx(0.03)
    assert result["series"][0]["portfolio"] == 100.0
    assert result["series"][0]["benevente2"] == 100.0
    assert result["benevente2_overlay"]["current_risk_state"] == "normal"
    assert result["strategy"] == "Benevente 2"
    assert result["status"] == "carteira_sombra_acompanhamento_corrente"


def test_same_content_is_idempotent() -> None:
    decision, series, cdi = fixture_inputs()
    first = MODULE.build_live_document(
        decision,
        series,
        cdi,
        {"fixture": "0" * 64},
        generated_at=datetime(2026, 1, 7, tzinfo=timezone.utc),
    )
    second = MODULE.build_live_document(
        decision,
        series,
        cdi,
        {"fixture": "0" * 64},
        previous=first,
        generated_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
    )
    assert second == first


def test_changed_content_chains_the_previous_record() -> None:
    decision, series, cdi = fixture_inputs()
    first = MODULE.build_live_document(decision, series, cdi, {"fixture": "0" * 64})
    for ticker, value in (("AAA3", 13.0), ("BBB3", 21.0), ("BOVA11", 111.0), ("IBOVESPA", 104_000.0)):
        series[ticker]["2026-01-07"] = value
    cdi["2026-01-07"] = 0.001
    second = MODULE.build_live_document(decision, series, cdi, {"fixture": "1" * 64}, first)
    assert second["previous_record_sha256"] == first["record_sha256"]
    assert second["record_sha256"] != first["record_sha256"]


def test_same_market_date_ignores_provider_float_noise() -> None:
    decision, series, cdi = fixture_inputs()
    first = MODULE.build_live_document(decision, series, cdi, {"fixture": "0" * 64})
    series["AAA3"]["2026-01-06"] += 0.000001
    second = MODULE.build_live_document(decision, series, cdi, {"fixture": "1" * 64}, first)
    assert second == first


def test_rejects_incomplete_weights() -> None:
    decision, series, cdi = fixture_inputs()
    decision["cdi_weight"] = 0.40
    with pytest.raises(MODULE.LiveDataError, match="não somam 100%"):
        MODULE.build_live_document(decision, series, cdi, {})


def test_workflow_is_daily_local_time_and_does_not_use_an_llm() -> None:
    workflow = (ROOT / ".github" / "workflows" / "update-live-performance.yml").read_text(
        encoding="utf-8"
    )
    assert 'cron: "10 23 * * 1-5"' in workflow
    assert 'timezone: "America/Sao_Paulo"' in workflow
    assert "contents: write" in workflow
    assert "diegogallina1" in workflow
    assert "update_live_performance.py" in workflow
    assert "OPENAI" not in workflow.upper()


def test_published_document_has_a_verifiable_contract() -> None:
    document = json.loads((ROOT / "web" / "live_performance.json").read_text(encoding="utf-8"))
    assert document["status"] == "carteira_sombra_acompanhamento_corrente"
    assert document["protocol_registered_at"] == "2026-08-23"
    assert document["protocol_sha256"] == __import__("hashlib").sha256(
        (ROOT / "docs" / "live_monitoring_protocol.md").read_bytes()
    ).hexdigest()
    assert document["benevente2_protocol_sha256"] == __import__("hashlib").sha256(
        (ROOT / "docs" / "benevente_1_vs_2_protocol.md").read_bytes()
    ).hexdigest()
    assert len(document["record_sha256"]) == 64
    declared_hash = document.pop("record_sha256")
    canonical = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    assert declared_hash == __import__("hashlib").sha256(canonical).hexdigest()
    assert document["summary"]["portfolio_value_brl"] > 0
    assert "benevente2_reconstructed_return" in document["summary"]
    assert len(document["series"]) >= 2
    assert document["data_quality"]["provisional"] is True


def test_strategy_pages_share_the_same_live_structure() -> None:
    first = (ROOT / "web" / "benevente-1.html").read_text(encoding="utf-8")
    second = (ROOT / "web" / "benevente-2.html").read_text(encoding="utf-8")
    for source, mode in ((first, "b1"), (second, "b2")):
        assert 'class="strategy-tab"' in source
        assert f'data-live-strategy="{mode}"' in source
        assert "CARTEIRA-SOMBRA 2026" in source
        assert "paper.js?v=20260823" in source
