"""Acompanhamento diário dos três livros de 2026, um por perfil declarado.

O monitor publicava um livro só, herdado da configuração que a busca aninhada
deixou viva antes de a política existir. Enquanto isso, o site mostrava onze
anos reconstruídos nos três perfis — e 2026 era outra coisa, sem que nada
avisasse o leitor.

Este programa converte a decisão de janeiro de 2026 nos três perfis para o
formato que o monitor já entende e roda o acompanhamento para cada um. Não
seleciona ativo, não altera peso e não chama modelo de linguagem: marca a
mercado uma decisão já registrada.

A perna global entra no livro como qualquer outra posição, mas viaja na lista
de isenção da camada de proteção — a política declara que o sinal de estresse é
doméstico e não se aplica ao fundo que existe justamente por não seguir o
Ibovespa.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import argparse
import json

from update_live_performance import update

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ROOT / "artifacts" / "profile_books_2026" / "profile_books_2026.json"
WEB = ROOT / "web"
GLOBAL_TICKER = "IVVB11"
PROFILES = ("conservador", "equilibrado", "arrojado")


def overlay_for(profile: str, registration: dict) -> tuple[dict, list[float]]:
    """Gatilhos e ação da camada, lidos do registro congelado."""
    from portfolio_risk import risk_profile_spec
    spec = risk_profile_spec(profile)
    return registration["intrayear_overlay"]["config"], [spec.alert_multiplier, spec.severe_multiplier]


def decision_document(book: dict, source: dict) -> dict:
    """O livro de um perfil no formato que o monitor consome."""
    registration = json.loads(
        (ROOT / "data" / "benevente_profile_ladder_v3_registration.json").read_text(encoding="utf-8"))
    overlay_config, multipliers = overlay_for(book["profile"], registration)
    holdings = [{"ticker": p["ticker"], "weight": p["weight"],
                 "score": p.get("score"),
                 "why": "Aprovado na triagem datada e classificado por qualidade, "
                        "lucro sobre preço e momento de doze meses.",
                 "risk": "Revisar resultado, preço, liquidez e fatos relevantes antes "
                         "de qualquer implementação."}
                for p in book["positions"]]
    if book["global_sleeve"] > 0:
        holdings.append({"ticker": GLOBAL_TICKER, "weight": book["global_sleeve"],
                         "score": None,
                         "why": "Perna global declarada pela política: um quinto do orçamento de "
                                "ações num fundo listado na B3 que segue o S&P 500 em reais. "
                                "Nunca selecionada pelo fator.",
                         "risk": "Posição em dólar sem proteção cambial: em período de real forte "
                                 "a contribuição de retorno se inverte."})
    return {
        "decision_date": source["decision_date"],
        "profile": book["profile"],
        "status": source["status"],
        "policy": source["policy"],
        "registration_sha256": source["registration_sha256"],
        "approved_by": source["approved_by"],
        "declared": book["declared"],
        "holdings": holdings,
        "cdi_weight": book["cash"],
        "overlay_exempt": [GLOBAL_TICKER],
        # A camada vem do registro, não das constantes do monitor: a escada
        # declarada corta por multiplicador de perfil, e o livro anterior cortava
        # por teto fixo. Confundir os dois publica proteção que não aconteceu.
        "overlay": {"config": overlay_config, "multipliers": multipliers},
        "universe": source["universe"],
        "honesty": source["honesty"],
        "limitations": source["limitations"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--books", type=Path, default=BOOKS)
    parser.add_argument("--as-of", type=lambda v: datetime.strptime(v, "%Y-%m-%d").date())
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = json.loads(args.books.read_text(encoding="utf-8"))
    summary = {"decision_date": source["decision_date"], "policy": source["policy"],
               "registration_sha256": source["registration_sha256"],
               "approved_by": source["approved_by"], "honesty": source["honesty"],
               "profiles": {}}
    for profile in PROFILES:
        document = decision_document(source["books"][profile], source)
        decision_path = WEB / f"current_decision_2026_{profile}.json"
        decision_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
        live = update(decision_path, WEB / f"live_performance_{profile}.json",
                      args.as_of, args.force)
        summary["profiles"][profile] = {
            "through": live["through"],
            "portfolio_return": live["summary"]["portfolio_return"],
            "equity_weight": document["declared"]["maximum_equity_weight"],
            "issuers": len(source["books"][profile]["positions"]),
            "record_sha256": live["record_sha256"],
        }
        print(f"{profile:<12} até {live['through']} · "
              f"{live['summary']['portfolio_return']:+.2%} · registro {live['record_sha256'][:12]}")

    (WEB / "live_profiles_2026.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
