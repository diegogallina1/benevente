import json
from pathlib import Path

import pandas as pd

from build_web_research_bundle import build_web_research_bundle


def test_bundle_keeps_annual_holdings_and_transitions_from_one_strategy_run(tmp_path: Path):
    source = tmp_path / "run"; source.mkdir()
    pd.DataFrame([{"decision_year": 2025, "net_return": .1, "mvo_eligible_net_return": .08, "cdi_net_return": .06}]).to_csv(source / "annual_results.csv", index=False)
    pd.DataFrame([{"decision_year": 2025, "ticker": "AAAA3.SA", "decision_action": "entered"}, {"decision_year": 2025, "ticker": "TITULO_CDI", "decision_action": "increased"}]).to_csv(source / "annual_holdings.csv", index=False)
    pd.DataFrame([{"decision_year": 2025, "ticker": "AAAA3.SA", "decision_action": "entered", "reason": "entered_after_point_in_time_screen"}]).to_csv(source / "annual_transitions.csv", index=False)
    (source / "protocol.json").write_text(json.dumps({"factor": "triple_factor"}), encoding="utf-8")
    output = tmp_path / "research.json"
    result = build_web_research_bundle(source, output)
    assert result["annual"][0]["decision_year"] == result["holdings"][0]["decision_year"]
    assert result["meta"]["protocol"]["factor"] == "triple_factor"
    assert result["meta"]["strategy"] == "Qualidade + valor + momento de 12 meses"
    assert result["holdings"][0]["decision_action_pt"] == "Entrada"
    assert "defensiva" in result["holdings"][1]["decision_rationale_pt"]


def test_bundle_carries_source_qualification_and_holdout_status(tmp_path: Path):
    source = tmp_path / "run"; source.mkdir()
    pd.DataFrame([{"decision_year": 2025, "net_return": .1, "mvo_eligible_net_return": .08, "cdi_net_return": .06}]).to_csv(source / "annual_results.csv", index=False)
    pd.DataFrame([{"decision_year": 2025, "ticker": "AAAA3.SA", "decision_action": "entered"}]).to_csv(source / "annual_holdings.csv", index=False)
    pd.DataFrame([{"decision_year": 2025, "ticker": "AAAA3.SA", "decision_action": "entered", "reason": "entered_after_point_in_time_screen"}]).to_csv(source / "annual_transitions.csv", index=False)
    (source / "protocol.json").write_text(json.dumps({"factor": "value_quality"}), encoding="utf-8")
    input_manifest = tmp_path / "input.json"; input_manifest.write_text(json.dumps({"price_tickers": 358, "fundamental_snapshots": 2748, "total_return_source_tier": "public_reproducible_research", "institutional_performance_verified": False}), encoding="utf-8")
    holdout = tmp_path / "holdout.json"; holdout.write_text(json.dumps({"status": "research_only"}), encoding="utf-8")
    result = build_web_research_bundle(source, tmp_path / "research.json", source_manifest=input_manifest, holdout_validation=holdout)
    assert result["meta"]["coverage"]["price_tickers"] == 358
    assert result["meta"]["source_tier"] == "public_reproducible_research"
    assert result["meta"]["holdout_validation"]["status"] == "research_only"
    assert result["meta"]["strategy"] == "Valor e qualidade"


def test_bundle_aligns_ibovespa_to_annual_decision_dates_as_a_total_return_index(tmp_path: Path):
    source = tmp_path / "run"; source.mkdir()
    pd.DataFrame([
        {"decision_year": 2024, "decision_date": "2024-01-02", "holding_end_exclusive": "2025-01-02", "net_return": .1, "mvo_eligible_net_return": .08, "cdi_net_return": .06},
    ]).to_csv(source / "annual_results.csv", index=False)
    pd.DataFrame([{"decision_year": 2024, "ticker": "AAAA3.SA", "decision_action": "entered"}]).to_csv(source / "annual_holdings.csv", index=False)
    pd.DataFrame([{"decision_year": 2024, "ticker": "AAAA3.SA", "decision_action": "entered", "reason": "entered_after_point_in_time_screen"}]).to_csv(source / "annual_transitions.csv", index=False)
    (source / "protocol.json").write_text(json.dumps({"factor": "value_quality"}), encoding="utf-8")
    ibov = tmp_path / "ibov.csv"
    pd.DataFrame({"Date": ["2024-01-02", "2025-01-02"], "IBOVESPA": [100000, 120000]}).to_csv(ibov, index=False)
    result = build_web_research_bundle(source, tmp_path / "research.json", ibovespa_price_input=ibov)
    assert result["meta"]["ibovespa"]["values_base_100"] == [100.0, 120.0]
    # B3 computes the Ibovespa as a total-return index. The bundle used to warn
    # that it excluded proventos, which understated the bar the strategy had to
    # clear; the caveat must now point at investability instead.
    limitation = result["meta"]["ibovespa"]["limitation"].lower()
    assert "índice de preço" not in limitation
    assert "retorno total" in limitation and "bova11" in limitation


def test_bundle_includes_profile_specific_history_when_sources_are_provided(tmp_path: Path):
    source = tmp_path / "equilibrado"; source.mkdir()
    conservative = tmp_path / "conservador"; conservative.mkdir()
    for root, yearly_return in ((source, .10), (conservative, .07)):
        pd.DataFrame([{"decision_year": 2025, "decision_date": "2025-01-02", "holding_end_exclusive": "2025-12-31", "net_return": yearly_return, "mvo_eligible_net_return": .08, "cdi_net_return": .06}]).to_csv(root / "annual_results.csv", index=False)
        pd.DataFrame([{"decision_year": 2025, "ticker": "AAAA3.SA", "decision_action": "entered"}]).to_csv(root / "annual_holdings.csv", index=False)
        pd.DataFrame([{"decision_year": 2025, "ticker": "AAAA3.SA", "decision_action": "entered", "reason": "entered_after_point_in_time_screen"}]).to_csv(root / "annual_transitions.csv", index=False)
        (root / "protocol.json").write_text(json.dumps({"factor": "value_quality"}), encoding="utf-8")
    result = build_web_research_bundle(source, tmp_path / "research.json", profile_sources={"conservador": conservative})
    assert result["profiles"]["conservador"]["annual"][0]["net_return"] == .07
    assert result["profile_curves"]["conservador"]["series"]["Benevente Wealth System"] == [100.0, 107.0]
