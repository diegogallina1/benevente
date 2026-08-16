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
    """Align the Ibovespa to the annual decision dates.

    An earlier version of this bundle labelled the Ibovespa a price index and
    warned that it excluded proventos.  That is the wrong way round: B3
    computes the Ibovespa as a total-return index which reinvests proventos, so
    it is directly comparable with an adjusted-close equity panel and the old
    caveat understated the bar the strategy had to clear.
    """
    if not price_input:
        return None
    source = pd.read_csv(price_input)
    if "IBOVESPA" not in source.columns:
        raise ValueError("Ibovespa input must contain a date column and IBOVESPA.")
    # The reference builder writes ``date``; older research exports wrote
    # ``Date``. Accept either rather than forcing a rename at every call site.
    date_column = "Date" if "Date" in source.columns else "date"
    source = source.rename(columns={date_column: "Date"})
    source["Date"] = pd.to_datetime(source["Date"])
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
        "label": "Ibovespa",
        "dates": [date.strftime("%Y-%m-%d") for date in dates],
        "values_base_100": [round(value / base * 100, 6) for value in values],
        "limitation": "Índice de retorno total da B3: reinveste proventos. Não é diretamente investível; para o custo real de comprar o mercado, veja BOVA11.",
    }


def _profile_curves(profile_results: dict[str, dict]) -> dict[str, dict]:
    """Build profile-aware annual curves without mixing policy runs."""
    payload: dict[str, dict] = {}
    for profile, records in profile_results.items():
        records = records["annual"]
        if not records:
            continue
        frame = pd.DataFrame(records).sort_values("decision_year")
        dates = [str(frame.decision_date.iloc[0]), *frame.holding_end_exclusive.astype(str).tolist()]
        # Every reference is compounded on exactly the same decision dates. The
        # after-tax pair is carried alongside so the page can show the strategy
        # and the CDI on the same footing instead of comparing a gross equity
        # result with a gross fixed-income one.
        tracks = {
            "Benevente Wealth System": "net_return",
            "Benevente após IR": "net_return_after_tax",
            "MVO de referência": "mvo_eligible_net_return",
            "CDI": "cdi_net_return",
            "CDI após IR": "cdi_net_return_after_tax",
            "Ibovespa": "benchmark_IBOVESPA",
            "BOVA11": "benchmark_BOVA11",
        }
        series: dict[str, list[float]] = {}
        for name, column in tracks.items():
            if column not in frame.columns or frame[column].isna().all():
                continue
            level = [100.0]
            for value in frame[column].fillna(0.0):
                level.append(round(level[-1] * (1 + float(value)), 6))
            series[name] = level
        payload[profile] = {"dates": dates, "series": series}
    return payload


MONTHLY_SERIES_LABELS = {
    "strategy": "Benevente",
    "mvo": "MVO de referência",
    "cdi": "CDI",
    "IBOVESPA": "Ibovespa",
    "BOVA11": "BOVA11",
}


def _monthly_curve(root: Path) -> dict | None:
    """Resample the exact daily book value to month ends.

    Eleven January points cannot show a drawdown or when a year turned, and the
    raw daily series is noisy enough to read as a smear at page width. Month
    ends keep every peak and trough that matters while giving the chart roughly
    a hundred points instead of eight.
    """
    path = root / "daily_curve.csv"
    if not path.exists():
        return None
    daily = pd.read_csv(path, parse_dates=["date"]).set_index("date").sort_index()
    columns = [column for column in MONTHLY_SERIES_LABELS if column in daily.columns]
    if not columns:
        return None
    monthly = daily[columns].resample("ME").last().dropna(how="all")
    # Carry the true first observation so the curve starts at the decision date
    # rather than at the end of the first month.
    opening = daily[columns].iloc[[0]]
    monthly = pd.concat([opening, monthly])
    monthly = monthly[~monthly.index.duplicated(keep="first")]
    base = monthly.iloc[0]
    rebased = monthly.divide(base).multiply(100).round(4)
    return {
        "dates": [date.date().isoformat() for date in rebased.index],
        "series": {MONTHLY_SERIES_LABELS[column]: rebased[column].tolist() for column in columns},
        "basis": "Valor diário exato da carteira mantida no ano, amostrado no fim de cada mês e rebaseado em 100.",
        "daily_observations": int(len(daily)),
    }


def _localized_records(root: Path) -> dict[str, list[dict]]:
    """Read one profile run and apply the same Portuguese dossier contract."""
    annual = pd.read_csv(root / "annual_results.csv")
    holdings = pd.read_csv(root / "annual_holdings.csv")
    transitions = pd.read_csv(root / "annual_transitions.csv")
    for frame in (annual, holdings, transitions):
        for column in frame.columns:
            if frame[column].dtype == "object":
                frame[column] = frame[column].where(frame[column].notna(), None)
    holdings["decision_action_pt"] = holdings.decision_action.map(ACTION_PT).fillna("Sem alteração")
    holdings["decision_rationale_pt"] = holdings.apply(
        lambda item: "Parcela defensiva após os limites de concentração e elegibilidade."
        if item.ticker == "TITULO_CDI" else
        "Ativo aprovado pela regra disponível na data de decisão; peso limitado pela política.", axis=1
    )
    transitions["decision_action_pt"] = transitions.decision_action.map(ACTION_PT).fillna("Sem alteração")
    transitions["reason_pt"] = transitions.reason.map(REASON_PT).fillna("Revisão anual documentada.")
    return {"annual": _records(annual), "holdings": _records(holdings), "transitions": _records(transitions)}

def build_web_research_bundle(source: str | Path, destination: str | Path,
                              b3_universe: str | Path | None = None,
                              source_manifest: str | Path | None = None,
                              holdout_validation: str | Path | None = None,
                              ibovespa_price_input: str | Path | None = None,
                              existing_bundle: str | Path | None = None,
                              profile_sources: dict[str, str | Path] | None = None,
                              audit_evidence: str | Path | None = None) -> dict:
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
        "scope": "painel CVM com os dados disponíveis na data de cada decisão e preços ajustados de pesquisa",
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
            "fundamentos completos disponíveis naquela data."
        )

    factor_label = {
        "value_quality": "Valor e qualidade",
        "triple_factor": "Qualidade + valor + momento de 12 meses",
        "momentum_12m": "Momento de 12 meses",
        "low_volatility": "Baixa volatilidade",
        "mvo_neutral": "MVO de cinco emissores com custos e limites por perfil",
        "mvo_low_volatility": "MVO de cinco emissores selecionados por baixa volatilidade",
        "mvo_risk_adjusted": "MVO de cinco emissores selecionados por retorno ajustado ao risco",
        "nested_annual_selection": "Seleção anual aninhada entre fatores pré-declarados",
        "nested_configuration_selection": "Seleção anual aninhada da configuração, por Sharpe dos anos encerrados",
    }.get(str(protocol.get("factor", "")), "Estratégia anual com dados datados")
    profile_results: dict[str, dict] = {}
    for profile, profile_source in (profile_sources or {}).items():
        profile_root = Path(profile_source)
        profile_results[str(profile)] = _localized_records(profile_root)
    payload = {
        "meta": {
            "title": "Estratégia anual — decisão com os dados da data",
            "sample": f"{int(annual.decision_year.min())}\u2013{int(annual.decision_year.max())}",
            "currency": "BRL",
            "strategy": factor_label,
            "sources": "CVM ITR/DFP, BCB SGS 12 (CDI) e Yahoo Finance ajustado via yfinance",
            "source_tier": source_metadata.get("total_return_source_tier", "public_reproducible_research"),
            "institutional_performance_verified": bool(source_metadata.get("institutional_performance_verified", False)),
            "holdout_validation": holdout,
            "coverage": coverage,
            "limitations": (
                "A estrat\u00e9gia \u00e9 pesquisa. N\u00e3o \u00e9 previs\u00e3o, recomenda\u00e7\u00e3o individual ou "
                "promessa de superar benchmarks. A janela 2015\u20132025 foi usada para escolher regra, "
                "fatores e restri\u00e7\u00f5es: \u00e9 amostra de desenvolvimento, n\u00e3o teste." + b3_note
            ),
            "evidence": (json.loads(Path(audit_evidence).read_text(encoding="utf-8")) if audit_evidence else None),
            "protocol": protocol,
            "ibovespa": (
                _ibovespa_on_decision_dates(annual, ibovespa_price_input)
                if ibovespa_price_input else
                json.loads(Path(existing_bundle).read_text(encoding="utf-8")).get("meta", {}).get("ibovespa")
                if existing_bundle else None
            ),
        },
        "annual": _records(annual),
        "monthly_curve": _monthly_curve(root),
        "profiles": profile_results,
        "profile_curves": _profile_curves(profile_results),
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
    parser.add_argument("--existing-bundle", help="Existing web bundle whose aligned Ibovespa curve should be retained.")
    parser.add_argument("--audit-evidence", help="audit_evidence.json produced by build_audit_evidence.py.")
    parser.add_argument("--profile-source", action="append", default=[], metavar="NOME=PASTA",
                        help="Optional audited profile run, e.g. conservador=artifacts/profile_conservador_2025")
    args = parser.parse_args()
    profile_sources = {}
    for item in args.profile_source:
        name, separator, folder = item.partition("=")
        if not separator or not name or not folder:
            raise ValueError("--profile-source must use NOME=PASTA")
        profile_sources[name] = folder
    result = build_web_research_bundle(args.source, args.output, args.b3_universe,
                                       args.source_manifest, args.holdout_validation, args.ibovespa_price_input,
                                       args.existing_bundle, profile_sources, args.audit_evidence)
    print(f"Wrote {len(result['annual'])} annual decisions from {result['meta']['strategy']} to {args.output}")


if __name__ == "__main__":
    main()
