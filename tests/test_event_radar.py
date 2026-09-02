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


def test_portfolio_tickers_are_loaded_from_the_current_live_contract(tmp_path: Path) -> None:
    live = {
        "portfolio_definitions": {"benevente1": {"target_allocation": [
            {"ticker": "ABCD3", "weight": 0.4}, {"ticker": "EFGH4", "weight": 0.3},
            {"ticker": "CDI", "weight": 0.3},
        ]}}
    }
    (tmp_path / "live_performance.json").write_text(json.dumps(live), encoding="utf-8")
    assert MODULE.load_portfolio_tickers(tmp_path) == ("ABCD3", "EFGH4")


def test_each_run_has_a_hard_cost_cap() -> None:
    now = datetime(2026, 8, 23, 12, 10, tzinfo=MODULE.BRT)
    events = [event(str(index), f"Notícia {index}") for index in range(MODULE.MAX_NEW_ITEMS_PER_RUN + 10)]
    result = MODULE.build_radar({}, now, events, [{"source": "teste", "status": "ok", "items": len(events)}])
    assert result["consolidations"][0]["new_items"] == MODULE.MAX_NEW_ITEMS_PER_RUN
    assert len(result["events"]) == MODULE.MAX_NEW_ITEMS_PER_RUN


def test_unchanged_cvm_archive_is_not_downloaded(monkeypatch) -> None:
    monkeypatch.setattr(MODULE, "_current_cvm_resource", lambda year: {
        "url": "https://example.test/ipe.zip", "last_modified": "2026-08-17T11:01:00",
    })
    monkeypatch.setattr(MODULE, "_request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("download indevido")))
    events, fingerprint, cached = MODULE.fetch_cvm_ipe(
        2026, datetime(2026, 8, 23, tzinfo=MODULE.BRT), known_fingerprint="2026-08-17T11:01:00",
    )
    assert events == []
    assert fingerprint == "2026-08-17T11:01:00"
    assert cached is True


def test_tickers_are_the_union_of_every_published_profile(tmp_path: Path) -> None:
    def live(*tickers: str) -> str:
        allocation = [{"ticker": ticker, "weight": 0.1} for ticker in (*tickers, "CDI")]
        return json.dumps({"portfolio_definitions": {"benevente2": {"target_allocation": allocation}}})

    (tmp_path / "live_performance_arrojado.json").write_text(live("VIVA3", "CURY3"), encoding="utf-8")
    (tmp_path / "live_performance_conservador.json").write_text(live("CURY3", "PLPL3", "IVVB11"), encoding="utf-8")
    (tmp_path / "live_performance.json").write_text(live("ZZZZ3"), encoding="utf-8")  # legado, ignorado
    assert MODULE.load_portfolio_tickers(tmp_path) == ("VIVA3", "CURY3", "PLPL3", "IVVB11")


def test_published_radar_watches_every_profile() -> None:
    published = json.loads((ROOT / "web" / "event_radar.json").read_text(encoding="utf-8"))
    assert set(MODULE.load_portfolio_tickers(ROOT / "web")) <= set(published["portfolio_tickers"])


def test_nothing_collected_is_not_reported_as_normal() -> None:
    now = datetime(2026, 8, 23, 12, 10, tzinfo=MODULE.BRT)
    failed = [{"source": "CVM IPE", "status": "indisponivel", "items": 0}, {"source": "Google", "status": "indisponivel", "items": 0}]
    result = MODULE.build_radar({}, now, [], failed)
    assert result["current_state"] == "sem_coleta"
    assert result["consolidations"][0]["collection"] == "sem_coleta"
    partial = MODULE.build_radar({}, now, [], [failed[0], {"source": "Google", "status": "ok", "items": 0}])
    assert partial["current_state"] == "normal"
    assert partial["consolidations"][0]["collection"] == "parcial"
    assert partial["consolidations"][0]["sources_ok"] == "1/2"


def test_cvm_rows_left_out_are_counted_not_swallowed() -> None:
    cutoff = datetime(2026, 8, 20, tzinfo=MODULE.BRT)
    rows = [
        {"Categoria": "Fato Relevante", "Data_Entrega": "2026-08-22 10:00:00", "Nome_Companhia": "ACME", "Assunto": "Aquisição"},
        {"Categoria": "Fato Relevante", "Data_Entrega": "2026-08-01 10:00:00", "Nome_Companhia": "ACME", "Assunto": "Antigo"},
        {"Categoria": "Fato Relevante", "Data_Entrega": "sem data", "Nome_Companhia": "ACME", "Assunto": "Ilegível"},
        {"Categoria": "Ata de Assembleia", "Data_Entrega": "2026-08-22 10:00:00", "Nome_Companhia": "ACME", "Assunto": "AGO"},
    ]
    counters: dict = {}
    events = MODULE.read_cvm_rows(rows, cutoff, counters)
    assert len(events) == 1
    assert counters["rows_read"] == 4
    assert counters["rows_kept"] == 1
    assert counters["rows_before_window"] == 1
    assert counters["rows_without_date"] == 1
    assert counters["rows_other_category"] == 1
    assert counters["columns_recognised"] is True
    renamed: dict = {}
    assert MODULE.read_cvm_rows([{"Tipo_Documento": "Fato Relevante", "Data": "2026-08-22"}], cutoff, renamed) == []
    assert renamed["columns_recognised"] is False
