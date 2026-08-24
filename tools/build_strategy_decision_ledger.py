"""Publica o histórico compacto das decisões do Benevente 1 e 2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


STATE_LABELS = {0: "normal", 1: "alerta", 2: "severo"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _allocation(text: str) -> list[dict[str, Any]]:
    rows = []
    for part in text.split("|"):
        ticker, percentage = part.strip().split(":", 1)
        rows.append({
            "ticker": ticker.replace(".SA", ""),
            "weight": float(percentage.strip().rstrip("%")) / 100.0,
        })
    # O texto de origem exibe duas casas decimais e pode fechar em 99,99%.
    # A parcela meramente residual pertence ao CDI, sem alterar os pesos de ações.
    residual = 1.0 - sum(row["weight"] for row in rows)
    cash = next((row for row in rows if row["ticker"] == "TITULO_CDI"), None)
    if cash is not None and abs(residual) <= 0.001:
        cash["weight"] += residual
    return rows


def _source_label(path: Path) -> str:
    parts = path.as_posix().split("/")
    for anchor in ("web", "artifacts"):
        if anchor in parts:
            return "/".join(parts[parts.index(anchor):])
    return path.name


def _risk_target(allocation: list[dict[str, Any]], target_equity_weight: float) -> list[dict[str, Any]]:
    equity = sum(item["weight"] for item in allocation if item["ticker"] != "TITULO_CDI")
    scale = min(target_equity_weight, equity) / equity if equity else 0.0
    target = [
        {"ticker": item["ticker"], "weight": item["weight"] * scale}
        for item in allocation if item["ticker"] != "TITULO_CDI"
    ]
    target.append({"ticker": "TITULO_CDI", "weight": 1.0 - sum(item["weight"] for item in target)})
    return target


def _transition_reason(previous: dict[str, str], state_from: int, state_to: int) -> str:
    if state_to < state_from:
        return "recuperação após dez pregões mais calmos"
    drawdown = float(previous["market_drawdown"]) if previous["market_drawdown"] else None
    volatility = float(previous["market_volatility"]) if previous["market_volatility"] else None
    reasons = []
    if drawdown is not None:
        if drawdown <= -0.22:
            reasons.append("queda severa")
        elif drawdown <= -0.12:
            reasons.append("queda de alerta")
    if volatility is not None:
        if volatility >= 0.60:
            reasons.append("volatilidade severa")
        elif volatility >= 0.40:
            reasons.append("volatilidade de alerta")
    return " e ".join(reasons) if reasons else "mudança do estado composto"


def build_ledger(bundle_path: Path, annual_path: Path, daily_path: Path) -> dict[str, Any]:
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    annual_risk = {int(row["year"]): row for row in _read_csv(annual_path)}
    daily = _read_csv(daily_path)
    transitions: list[dict[str, Any]] = []
    previous: dict[str, str] | None = None
    for row in daily:
        state = int(row["risk_state"])
        previous_state = int(previous["risk_state"]) if previous else state
        if previous is not None and state != previous_state:
            transitions.append({
                "year": int(row["decision_year"]),
                "effective_on": row["date"],
                "observed_on": previous["date"],
                "from_state": STATE_LABELS[previous_state],
                "to_state": STATE_LABELS[state],
                "target_equity_weight": float(row["benevente2_equity_weight"]),
                "observed_market_drawdown": float(previous["market_drawdown"]) if previous["market_drawdown"] else None,
                "observed_market_volatility": float(previous["market_volatility"]) if previous["market_volatility"] else None,
                "reason": _transition_reason(previous, previous_state, state),
            })
        previous = row

    annual = []
    for row in bundle["annual"]:
        year = int(row["decision_year"])
        risk = annual_risk[year]
        annual.append({
            "year": year,
            "decision_date": row["decision_date"],
            "holding_end_exclusive": row["holding_end_exclusive"],
            "selected_configuration": row["selected_configuration"],
            "allocation": _allocation(row["weights_at_decision"]),
            "eligible_universe_size": int(row["eligible_universe_size"]),
            "estimated_cost_brl": float(row["estimated_cost_brl"]),
            "benevente1_return": float(row["net_return"]),
            "benevente2_return": float(risk["Benevente 2"]),
            "cdi_return": float(row["cdi_net_return"]),
            "mvo_return": float(row["mvo_eligible_net_return"]),
            "ibovespa_return": float(row["benchmark_IBOVESPA"]),
            "days_alert": int(float(risk["days_alert"])),
            "days_severe": int(float(risk["days_severe"])),
            "risk_transitions": [item for item in transitions if item["year"] == year],
            "decision_evidence_sha256": row["decision_evidence_sha256"],
        })

    annual_allocations = {item["year"]: item["allocation"] for item in annual}
    for transition in transitions:
        transition["target_allocation"] = _risk_target(
            annual_allocations[transition["year"]], transition["target_equity_weight"]
        )

    source_hashes = {
        _source_label(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (bundle_path, annual_path, daily_path)
    }
    return {
        "schema_version": "1.0.0",
        "status": "diagnostico_historico_retrospectivo",
        "period": "2015–2025",
        "interpretation": (
            "Benevente 1 registra a cesta anual. Benevente 2 reutiliza essa cesta e "
            "registra somente mudanças proporcionais de exposição."
        ),
        "annual_decisions": annual,
        "risk_transitions": transitions,
        "sources_sha256": source_hashes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("web/annual_research.json"))
    parser.add_argument(
        "--annual-risk", type=Path,
        default=Path("artifacts/benevente2_event_risk/candidate_annual_comparison.csv"),
    )
    parser.add_argument(
        "--daily-risk", type=Path,
        default=Path("artifacts/benevente2_event_risk/candidate_daily_comparison.csv"),
    )
    parser.add_argument("--output", type=Path, default=Path("web/strategy_decisions.json"))
    args = parser.parse_args()
    result = build_ledger(args.bundle, args.annual_risk, args.daily_risk)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(result['annual_decisions'])} decisões anuais; {len(result['risk_transitions'])} trocas de estado")


if __name__ == "__main__":
    main()
