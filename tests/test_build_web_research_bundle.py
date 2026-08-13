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
    assert result["holdings"][0]["decision_action_pt"] == "Entrada"
    assert "defensiva" in result["holdings"][1]["decision_rationale_pt"]
