"""Publish one self-consistent, Portuguese research bundle for the web UI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


ACTION_PT = {
    "entered": "Entrada", "exited": "Sa\u00edda", "increased": "Aumento",
    "reduced": "Redu\u00e7\u00e3o", "maintained": "Manuten\u00e7\u00e3o",
}
REASON_PT = {
    "entered_after_point_in_time_screen": "Inclu\u00eddo ap\u00f3s aprova\u00e7\u00e3o na triagem datada.",
    "removed_by_constrained_allocator": "Retirado na revis\u00e3o por n\u00e3o permanecer na sele\u00e7\u00e3o sujeita aos limites.",
    "rebalanced_after_point_in_time_review": "Peso ajustado na revis\u00e3o anual, dentro dos limites da pol\u00edtica.",
    "defensive_residual_adjustment": "Parcela defensiva definida depois de aplicar limites de concentra\u00e7\u00e3o e elegibilidade.",
}


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def build_web_research_bundle(source: str | Path, destination: str | Path,
                              b3_universe: str | Path | None = None) -> dict:
    """Write annual results, holdings and transitions from exactly one run."""
    root = Path(source)
    annual = pd.read_csv(root / "annual_results.csv")
    holdings = pd.read_csv(root / "annual_holdings.csv")
    transitions = pd.read_csv(root / "annual_transitions.csv")
    protocol = json.loads((root / "protocol.json").read_text(encoding="utf-8"))
    for frame in (annual, holdings, transitions):
        for column in frame.columns:
            if frame[column].dtype == "object":
                frame[column] = frame[column].where(frame[column].notna(), None)

    holdings["decision_action_pt"] = holdings.decision_action.map(ACTION_PT).fillna("Sem altera\u00e7\u00e3o")
    holdings["decision_rationale_pt"] = holdings.apply(
        lambda item: (
            "Parcela defensiva ap\u00f3s os limites de concentra\u00e7\u00e3o e elegibilidade."
            if item.ticker == "TITULO_CDI" else
            "Ativo aprovado pela regra multifatorial dispon\u00edvel na data de decis\u00e3o; peso limitado pela pol\u00edtica."
        ), axis=1)
    transitions["decision_action_pt"] = transitions.decision_action.map(ACTION_PT).fillna("Sem altera\u00e7\u00e3o")
    transitions["reason_pt"] = transitions.reason.map(REASON_PT).fillna("Revis\u00e3o anual documentada.")

    coverage = {
        "fundamental_snapshots": int(len(holdings[holdings.ticker != "TITULO_CDI"])),
        "issuers": int(holdings.loc[holdings.ticker != "TITULO_CDI", "ticker"].nunique()),
        "scope": "painel hist\u00f3rico fundamental dispon\u00edvel",
    }
    b3_note = ""
    if b3_universe:
        universe = json.loads(Path(b3_universe).read_text(encoding="utf-8"))
        coverage.update({
            "b3_instruments": universe["instrument_count"],
            "b3_equities_current": int(universe["coverage_by_class"].get("equity", 0)),
            "b3_observed_at": universe["observed_at"],
        })
        b3_note = (
            f" O explorador cont\u00e9m {universe['instrument_count']} instrumentos B3 observados em "
            f"{universe['observed_at']}; o painel hist\u00f3rico ainda cont\u00e9m somente emissores com "
            "fundamentos ponto-no-tempo completos."
        )

    payload = {
        "meta": {
            "title": "Estrat\u00e9gia multifatorial anual \u2014 execu\u00e7\u00e3o ponto-no-tempo",
            "sample": f"{int(annual.decision_year.min())}\u2013{int(annual.decision_year.max())}",
            "currency": "BRL",
            "strategy": "Qualidade + valor + momento de 12 meses",
            "sources": "CVM ITR/DFP, BCB CDI e pre\u00e7os B3 hist\u00f3ricos documentados",
            "coverage": coverage,
            "limitations": (
                "A estrat\u00e9gia \u00e9 pesquisa. N\u00e3o \u00e9 previs\u00e3o, recomenda\u00e7\u00e3o individual ou "
                "promessa de superar benchmarks." + b3_note
            ),
            "protocol": protocol,
        },
        "annual": _records(annual),
        "holdings": _records(holdings),
        "transitions": _records(transitions),
    }
    Path(destination).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the web research JSON from one annual strategy run.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--b3-universe")
    args = parser.parse_args()
    result = build_web_research_bundle(args.source, args.output, args.b3_universe)
    print(f"Wrote {len(result['annual'])} annual decisions from {result['meta']['strategy']} to {args.output}")


if __name__ == "__main__":
    main()
