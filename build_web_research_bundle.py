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
    "removed_or_blocked_by_eligibility": "Retirado por deixar de atender aos crit\u00e9rios de elegibilidade na data de revis\u00e3o.",
}


def _records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def _ibovespa_on_decision_dates(annual: pd.DataFrame, price_input: str | Path | None) -> dict | None:
    """Align a price-index reference to the annual decision dates.

    The Bovespa index source in the project is a price index, not a total
    return index.  Keeping that distinction in the bundle prevents an
    apparently like-for-like comparison with the adjusted equity series.
    """
    if not price_input:
        return None
    source = pd.read_csv(price_input, parse_dates=["Date"])
    if "IBOVESPA" not in source.columns:
        raise ValueError("Ibovespa input must contain Date and IBOVESPA columns.")
    source = source.sort_values("Date").dropna(subset=["IBOVESPA"])
    dates = pd.to_datetime([annual.decision_date.iloc[0], *annual.holding_end_exclusive.tolist()])
    values: list[float] = []
    for date in dates:
        visible = source[source.Date <= date]
        if visible.empty:
            raise ValueError(f"No Ibovespa observation exists on or before {date.date()}.")
        values.append(float(visible.iloc[-1].IBOVESPA))
    base = values[0]
    return {
        "label": "Ibovespa (índice de preço)",
        "dates": [date.strftime("%Y-%m-%d") for date in dates],
        "values_base_100": [round(value / base * 100, 6) for value in values],
        "limitation": "Índice de preço: não incorpora proventos como uma série de retorno total.",
    }

def build_web_research_bundle(source: str | Path, destination: str | Path,
                              b3_universe: str | Path | None = None,
                              source_manifest: str | Path | None = None,
                              holdout_validation: str | Path | None = None,
                              ibovespa_price_input: str | Path | None = None) -> dict:
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
            "Ativo aprovado pela regra disponível na data de decisão; peso limitado pela política."
        ), axis=1)
    transitions["decision_action_pt"] = transitions.decision_action.map(ACTION_PT).fillna("Sem altera\u00e7\u00e3o")
    transitions["reason_pt"] = transitions.reason.map(REASON_PT).fillna("Revis\u00e3o anual documentada.")

    source_metadata = json.loads(Path(source_manifest).read_text(encoding="utf-8")) if source_manifest else {}
    holdout = json.loads(Path(holdout_validation).read_text(encoding="utf-8")) if holdout_validation else {}
    coverage = {
        "fundamental_snapshots": int(source_metadata.get("fundamental_snapshots", len(holdings[holdings.ticker != "TITULO_CDI"]))),
        "selected_issuers": int(holdings.loc[holdings.ticker != "TITULO_CDI", "ticker"].nunique()),
        "price_tickers": int(source_metadata.get("price_tickers", 0)),
        "scope": "painel CVM ponto-no-tempo com preços ajustados de pesquisa",
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

    factor_label = {
        "value_quality": "Valor e qualidade",
        "triple_factor": "Qualidade + valor + momento de 12 meses",
        "momentum_12m": "Momento de 12 meses",
        "low_volatility": "Baixa volatilidade",
    }.get(str(protocol.get("factor", "")), "Estratégia anual ponto-no-tempo")
    payload = {
        "meta": {
            "title": "Estratégia anual — execução ponto-no-tempo",
            "sample": f"{int(annual.decision_year.min())}\u2013{int(annual.decision_year.max())}",
            "currency": "BRL",
            "strategy": factor_label,
            "sources": "CVM ITR/DFP, BCB SGS 12 (CDI) e Yahoo Finance ajustado via yfinance",
            "source_tier": source_metadata.get("total_return_source_tier", "unclassified"),
            "institutional_performance_verified": bool(source_metadata.get("institutional_performance_verified", False)),
            "holdout_validation": holdout,
            "coverage": coverage,
            "limitations": (
                "A estrat\u00e9gia \u00e9 pesquisa. N\u00e3o \u00e9 previs\u00e3o, recomenda\u00e7\u00e3o individual ou "
                "promessa de superar benchmarks." + b3_note
            ),
            "protocol": protocol,
            "ibovespa": _ibovespa_on_decision_dates(annual, ibovespa_price_input),
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
    parser.add_argument("--source-manifest", help="Annual input_manifest.json for source qualification.")
    parser.add_argument("--holdout-validation", help="Frozen holdout validation JSON for the same run.")
    parser.add_argument("--ibovespa-price-input", help="Dated Ibovespa price-index CSV (Date,IBOVESPA).")
    args = parser.parse_args()
    result = build_web_research_bundle(args.source, args.output, args.b3_universe,
                                       args.source_manifest, args.holdout_validation, args.ibovespa_price_input)
    print(f"Wrote {len(result['annual'])} annual decisions from {result['meta']['strategy']} to {args.output}")


if __name__ == "__main__":
    main()
