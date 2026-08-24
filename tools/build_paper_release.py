"""Build the canonical evidence bundle used by both Benevente manuscripts.

The papers must not copy figures from prose or from the web interface. This
builder reads the final research artefacts, independently recomputes the main
portfolio statistics, asserts that the published summaries agree, and writes a
small release bundle with hashes for every input.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "artifacts" / "paper_release"

INPUTS = {
    "annual_results": ROOT / "artifacts" / "published_nested" / "annual_results.csv",
    "published_protocol": ROOT / "artifacts" / "published_nested" / "protocol.json",
    "daily_curve": ROOT / "artifacts" / "published_nested" / "daily_curve.csv",
    "audit": ROOT / "artifacts" / "audit_evidence" / "audit_evidence.json",
    "configuration_search": ROOT / "artifacts" / "configuration_search_2012" / "summary.json",
    "benevente_2": ROOT / "artifacts" / "benevente2_event_risk" / "summary.json",
    "llm_experiment": ROOT / "artifacts" / "llm_contamination" / "summary.json",
    "llm_constraints": ROOT / "artifacts" / "llm_contamination" / "constraint_audit.csv",
    "rebalance_frequency": ROOT / "artifacts" / "rebalance_frequency" / "summary.json",
    "persistence": ROOT / "artifacts" / "persistence" / "summary.json",
    "primary_reconciliation": ROOT / "artifacts" / "primary_reconciliation" / "summary.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cagr(rows: list[dict[str, str]], column: str) -> float:
    wealth = math.prod(1.0 + float(row[column]) for row in rows)
    return wealth ** (1.0 / len(rows)) - 1.0


def max_drawdown(values: list[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def assert_close(label: str, actual: float, expected: float, tolerance: float = 1e-10) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise AssertionError(f"{label}: recomputed={actual:.12f}, artefact={expected:.12f}")


def build_bundle() -> dict[str, Any]:
    for path in INPUTS.values():
        if not path.exists():
            raise FileNotFoundError(path)

    annual = load_csv(INPUTS["annual_results"])
    protocol = load_json(INPUTS["published_protocol"])
    audit = load_json(INPUTS["audit"])
    search = load_json(INPUTS["configuration_search"])
    b2 = load_json(INPUTS["benevente_2"])
    llm = load_json(INPUTS["llm_experiment"])
    cadence = load_json(INPUTS["rebalance_frequency"])
    persistence = load_json(INPUTS["persistence"])
    reconciliation = load_json(INPUTS["primary_reconciliation"])
    constraints = load_csv(INPUTS["llm_constraints"])

    evaluation = [row for row in annual if 2015 <= int(row["decision_year"]) <= 2025]
    recomputed = {
        "benevente_1_cagr": cagr(evaluation, "net_return"),
        "benevente_1_after_tax_cagr": cagr(evaluation, "net_return_after_tax"),
        "cdi_cagr": cagr(evaluation, "cdi_net_return"),
        "mvo_cagr": cagr(evaluation, "mvo_eligible_net_return"),
        "ibovespa_cagr": cagr(evaluation, "benchmark_IBOVESPA"),
    }

    daily_rows = [
        row for row in load_csv(INPUTS["daily_curve"])
        if row["date"] >= "2015-01-02" and row["date"] <= "2025-12-31"
    ]
    recomputed["benevente_1_daily_max_drawdown"] = max_drawdown(
        [float(row["strategy"]) for row in daily_rows]
    )

    assert_close("Benevente 1 CAGR", recomputed["benevente_1_cagr"], audit["strategy_cagr"])
    assert_close(
        "Benevente 1 after-tax CAGR",
        recomputed["benevente_1_after_tax_cagr"],
        audit["strategy_cagr_after_tax"],
    )
    assert_close("CDI CAGR", recomputed["cdi_cagr"], search["references"]["cdi_cagr"])
    assert_close("MVO CAGR", recomputed["mvo_cagr"], search["references"]["mvo_cagr"])
    assert_close("Ibovespa CAGR", recomputed["ibovespa_cagr"], search["references"]["ibovespa_cagr"])
    assert_close(
        "Benevente 1 daily drawdown",
        recomputed["benevente_1_daily_max_drawdown"],
        b2["full_period_metrics"]["Benevente 1"]["max_drawdown"],
        tolerance=1e-8,
    )

    malformed = [row for row in constraints if abs(float(row["sum_before_normalisation"]) - 1.0) > 1e-3]
    omitted = [row for row in constraints if int(row["missing_ids"]) > 0]
    if len(malformed) != 5 or len(omitted) != 2:
        raise AssertionError("The monolithic-arm constraint audit no longer matches the manuscript.")

    return {
        "release_contract": {
            "annual_selection_strategy": "Benevente 1",
            "primary_shadow_strategy": "Benevente 2",
            "evaluation_window": "2015-2025",
            "decision_count": len(evaluation),
            "claim_status": "retrospective development evidence; not prospective validation",
        },
        "published_protocol": protocol,
        "recomputed": recomputed,
        "published_strategy": {
            "cumulative_return": math.prod(1 + float(row["net_return"]) for row in evaluation) - 1,
            "cagr": recomputed["benevente_1_cagr"],
            "after_tax_cagr": recomputed["benevente_1_after_tax_cagr"],
            "daily_max_drawdown": recomputed["benevente_1_daily_max_drawdown"],
            "years_beating_cdi": search["nested"]["years_beating_cdi"],
            "years_beating_mvo": search["nested"]["years_beating_mvo"],
            "years_beating_ibovespa": search["nested"]["years_beating_ibovespa"],
            "hindsight_premium": search["hindsight"]["premium_over_nested"],
            "deflated_sharpe_probability": search["deflated_sharpe"]["deflated_sharpe_probability"],
        },
        "benchmarks": {
            "cdi_cagr": recomputed["cdi_cagr"],
            "mvo_cagr": recomputed["mvo_cagr"],
            "ibovespa_cagr": recomputed["ibovespa_cagr"],
        },
        "benevente_2": {
            "status": b2["status"],
            "cumulative_return": b2["training_only_selection"]["full_period_metrics"]["cumulative_return"],
            "cagr": b2["training_only_selection"]["full_period_metrics"]["cagr"],
            "daily_max_drawdown": b2["training_only_selection"]["full_period_metrics"]["max_drawdown"],
            "evaluation_slice_cagr": b2["training_only_selection"]["holdout_2019_2025_metrics"]["cagr"],
            "paired_p_value": b2["training_only_selection"]["paired_annual_test_2019_2025"]["p_value"],
            "sensitivity_configurations": b2["sensitivity_grid"]["configurations"],
            "share_improving_both": b2["sensitivity_grid"]["share_improving_both"],
        },
        "llm_experiment": {
            "model": llm["model"],
            "years": llm["contamination"]["paired_years"],
            "arms": llm["arms"],
            "contamination_gap": llm["contamination"]["contamination_annualised"],
            "contamination_p_value": llm["contamination"]["p_value"],
            "added_value_gap": llm["model_added_value_vs_deterministic"]["annualised_gap"],
            "added_value_p_value": llm["model_added_value_vs_deterministic"]["p_value"],
            "decoupling_gap": llm["decoupled_vs_monolithic"]["annualised_gap"],
            "decoupling_p_value": llm["decoupled_vs_monolithic"]["p_value"],
            "malformed_weight_years": len(malformed),
            "years_with_omitted_eligible_assets": len(omitted),
        },
        "robustness": {
            "rebalance_frequency": cadence,
            "position_persistence": persistence,
        },
        "primary_event_reconciliation": reconciliation,
        "inputs": {
            label: {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for label, path in INPUTS.items()
        },
    }


def write_release(output: Path) -> dict[str, Any]:
    bundle = build_bundle()
    output.mkdir(parents=True, exist_ok=True)
    evidence_path = output / "paper_evidence.json"
    evidence_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "evidence": evidence_path.name,
        "evidence_sha256": sha256(evidence_path),
        "input_count": len(INPUTS),
        "status": "validated",
    }
    (output / "paper_release_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return bundle


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    bundle = write_release(args.output)
    print(json.dumps({"status": "validated", "metrics": bundle["published_strategy"]}, indent=2))


if __name__ == "__main__":
    main()
