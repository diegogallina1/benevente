"""Build and verify the canonical research release manifest.

The manifest is deliberately derived from the published artifacts.  It is the
single machine-readable contract used by the site and the two manuscripts; it
does not upgrade public research data to institutional-grade evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "artifacts" / "release_manifest.json"

CANONICAL_FILES = [
    "artifacts/published_nested/annual_results.csv",
    "artifacts/published_nested/annual_holdings.csv",
    "artifacts/published_nested/annual_transitions.csv",
    "artifacts/published_nested/daily_curve.csv",
    "artifacts/published_nested/protocol.json",
    "artifacts/audit_evidence/audit_evidence.json",
    "artifacts/configuration_search_2012/summary.json",
    "artifacts/llm_contamination/summary.json",
    "artifacts/llm_contamination/constraint_audit.csv",
    "artifacts/benevente2_event_risk/summary.json",
    "artifacts/benevente2_event_risk/candidate_annual_comparison.csv",
    "artifacts/benevente2_event_risk/candidate_daily_comparison.csv",
    "artifacts/benevente2_event_risk/sensitivity_grid.csv",
    "data/prices_b3_total_return_full_2011_2025.csv",
    "data/prices_b3_total_return_full_2011_2025_manifest.json",
    "data/fundamentals_b3_cvm_full_2012_2025.csv",
    "data/b3_historical_universes_2012_2025.csv",
    "data/b3_historical_cvm_ticker_map_2012_2025.csv",
    "data/benchmarks_market_2011_2025.csv",
    "data/benchmarks_market_2011_2025_manifest.json",
]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def file_record(relative: str) -> dict:
    path = ROOT / relative
    if not path.exists():
        raise FileNotFoundError(relative)
    return {"path": relative.replace("\\", "/"), "bytes": path.stat().st_size, "sha256": digest(path)}


def cagr(values: pd.Series) -> float:
    return float((1.0 + values.astype(float)).prod() ** (1.0 / len(values)) - 1.0)


def build() -> dict:
    annual = pd.read_csv(ROOT / "artifacts/published_nested/annual_results.csv")
    fundamentals = pd.read_csv(ROOT / "data/fundamentals_b3_cvm_full_2012_2025.csv")
    universe = pd.read_csv(ROOT / "data/b3_historical_universes_2012_2025.csv")
    price_manifest = json.loads((ROOT / "data/prices_b3_total_return_full_2011_2025_manifest.json").read_text(encoding="utf-8"))
    audit = json.loads((ROOT / "artifacts/audit_evidence/audit_evidence.json").read_text(encoding="utf-8"))
    search = json.loads((ROOT / "artifacts/configuration_search_2012/summary.json").read_text(encoding="utf-8"))
    llm = json.loads((ROOT / "artifacts/llm_contamination/summary.json").read_text(encoding="utf-8"))
    benevente2 = json.loads((ROOT / "artifacts/benevente2_event_risk/summary.json").read_text(encoding="utf-8"))
    daily = pd.read_csv(ROOT / "artifacts/published_nested/daily_curve.csv")

    raw_cvm = sorted((ROOT / "work/cvm_cache").glob("*")) if (ROOT / "work/cvm_cache").exists() else []
    raw_cvm_records = [file_record(path.relative_to(ROOT).as_posix()) for path in raw_cvm if path.is_file()]
    strategy_peak = daily["strategy"].cummax()
    market_peak = daily["IBOVESPA"].cummax()

    payload = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "research_only",
        "names": {
            "academic": "Benevente Quant AI",
            "commercial": "Benevente Wealth System",
            "published_strategy": "Benevente",
        },
        "role_contract": {
            "selection": "Fundamentalista multifatorial: qualidade, valor e momento, com liquidez e disponibilidade documental.",
            "allocation": "Regra quantitativa anual, com configuração escolhida apenas pelos anos já encerrados.",
            "llm": "Explica teses, riscos e perguntas de revisão; não seleciona ativos nem define pesos.",
            "mvo": "Comparador quantitativo independente e alocador apenas nos braços experimentais.",
            "benevente2": "Extensão experimental: preserva a cesta anual e reduz exposição após estresse observável no fechamento anterior.",
        },
        "evaluation": {
            "decision_years": [int(annual.decision_year.min()), int(annual.decision_year.max())],
            "annual_decisions": int(len(annual)),
            "selection_years": [2012, 2014],
            "prospective_status": "A validação prospectiva começa depois do registro congelado.",
        },
        "claims": {
            "strategy_cagr_net_costs": cagr(annual.net_return),
            "strategy_cagr_after_modeled_tax": cagr(annual.net_return_after_tax),
            "cdi_cagr": cagr(annual.cdi_net_return),
            "ibovespa_cagr": cagr(annual.benchmark_IBOVESPA),
            "bova11_cagr": cagr(annual.benchmark_BOVA11),
            "mvo_reference_cagr": cagr(annual.mvo_eligible_net_return),
            "strategy_max_daily_drawdown": float((daily.strategy / strategy_peak - 1.0).min()),
            "ibovespa_max_daily_drawdown": float((daily.IBOVESPA / market_peak - 1.0).min()),
            "deflated_sharpe": float(search["deflated_sharpe"]["deflated_sharpe_probability"]),
            "hindsight_premium_annual": float(search["hindsight"]["premium_over_nested"]),
            "configurations_evaluated": int(search["configurations_evaluated"]),
            "llm_named_cagr": float(llm["arms"]["named"]["cagr"]),
            "llm_anonymised_cagr": float(llm["arms"]["anonymised"]["cagr"]),
            "deterministic_cagr": float(llm["arms"]["deterministic"]["cagr"]),
            "llm_added_value_p_value": float(llm["model_added_value_vs_deterministic"]["p_value"]),
            "benevente2_candidate_cagr": float(benevente2["training_only_selection"]["full_period_metrics"]["cagr"]),
            "benevente2_candidate_max_drawdown": float(benevente2["training_only_selection"]["full_period_metrics"]["max_drawdown"]),
            "benevente2_holdout_cagr": float(benevente2["training_only_selection"]["holdout_2019_2025_metrics"]["cagr"]),
            "benevente2_paired_p_value": float(benevente2["training_only_selection"]["paired_annual_test_2019_2025"]["p_value"]),
        },
        "coverage": {
            "price_tickers": int(price_manifest.get("ticker_count", 0)),
            "fundamental_records": int(len(fundamentals)),
            "historical_universe_records": int(len(universe)),
            "historical_issuers": int(universe.issuer_name.nunique()),
            "historical_asset_classes": sorted(universe.asset_class.dropna().astype(str).unique().tolist()),
            "cvm_source_archives": len(raw_cvm_records),
        },
        "sources": "B3 COTAHIST, CVM ITR/DFP e BCB SGS 12; complemento de retorno total público documentado no manifesto do painel.",
        "source_tier": price_manifest.get("source_tier", "public_reproducible_research"),
        "institutional_performance_verified": False,
        "limitations": [
            "A janela 2015–2025 também participou do desenvolvimento; não é validação prospectiva.",
            "O detector de eventos societários tem recall documentado de 23,3%.",
            "Parte das distribuições é imputada quando a fonte pública não cobre o papel.",
            "Custos e tributos são modelados, não conciliados com notas reais de corretagem.",
        ],
        "canonical_files": [file_record(path) for path in CANONICAL_FILES],
        "cvm_source_archives": raw_cvm_records,
        "audit_evidence_sha256": digest(ROOT / "artifacts/audit_evidence/audit_evidence.json"),
        "audit_years": int(audit["years"]),
    }
    return payload


def verify(manifest: dict) -> list[str]:
    failures: list[str] = []
    for record in [*manifest.get("canonical_files", []), *manifest.get("cvm_source_archives", [])]:
        path = ROOT / record["path"]
        if not path.exists():
            failures.append(f"missing: {record['path']}")
        elif path.stat().st_size != record["bytes"] or digest(path) != record["sha256"]:
            failures.append(f"mismatch: {record['path']}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    output = Path(args.output)
    if args.verify:
        failures = verify(json.loads(output.read_text(encoding="utf-8")))
        if failures:
            raise SystemExit("\n".join(failures))
        print(f"Verified {output}")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(build(), indent=2, ensure_ascii=False), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
