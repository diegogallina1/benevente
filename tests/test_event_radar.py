import importlib.util
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_event_radar", ROOT / "tools" / "update_event_radar.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def event(identifier: str, title: str, source_tier: str = "fonte_secundaria_a_confirmar") -> dict:
    return {
        "id": identifier, "source": "Fonte", "source_type": "noticia_descoberta",
        "source_tier": source_tier, "title": title, "summary": title,
        "url": f"https://example.test/{identifier}", "published_at": "2026-08-23T09:00:00-03:00",
    }


def test_deterministic_classification_prioritises_portfolio_and_severe_terms() -> None:
    result = MODULE.deterministic_classification(
        event("a", "VIVA3 anuncia recuperação judicial e investigação por fraude"),
        ["VIVA3", "CURY3"],
    )
    assert result["materiality"] >= 85
    assert result["urgency"] == "critica"
    assert result["impact"] == "negativo"
    assert result["impacted_tickers"] == ["VIVA3"]
    assert result["needs_human_review"] is True


def test_build_radar_is_deduplicated_and_auditable() -> None:
    now = datetime(2026, 8, 23, 12, 10, tzinfo=MODULE.BRT)
    first = MODULE.build_radar({}, now, [event("a", "Copom eleva a Selic")], [{"source": "teste", "status": "ok", "items": 1}])
    second = MODULE.build_radar(first, now, [event("a", "Copom eleva a Selic")], [{"source": "teste", "status": "ok", "items": 1}])
    assert first["consolidations"][0]["new_items"] == 1
    assert second["consolidations"][0]["new_items"] == 0
    assert len(second["events"]) == 1
    assert len(second["record_sha256"]) == 64
    assert second["schedule"] == ["00:10", "12:10"]
    assert "api" not in json.dumps(second).lower()


def test_published_radar_respects_contract() -> None:
    published = json.loads((ROOT / "web" / "event_radar.json").read_text(encoding="utf-8"))
    assert published["window_hours"] == 12
    assert published["schedule"] == ["00:10", "12:10"]
    assert len(published["record_sha256"]) == 64
    assert published["policy"].startswith("O radar informa")


def test_configured_gemini_is_reported_when_there_is_nothing_to_classify() -> None:
    now = datetime(2026, 8, 23, 12, 10, tzinfo=MODULE.BRT)
    prior_event = event("a", "Evento já classificado")
    prior_event["classification"] = {
        **MODULE.deterministic_classification(prior_event, []),
        "classifier": "gemini:gemini-3.5-flash",
    }
    prior_event["state"] = "normal"
    result = MODULE.build_radar(
        {"events": [prior_event]}, now, [prior_event],
        [{"source": "teste", "status": "ok", "items": 1}], api_key="configurada",
    )
    assert result["consolidations"][0]["classifier_status"] == "gemini_disponivel_sem_itens_novos"
