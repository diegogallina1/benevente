"""Acompanhamento diário dos livros de 2026, um por perfil declarado.

O monitor publicava um livro só, herdado da configuração que a busca aninhada
deixou viva antes de a política existir. Enquanto isso, o site mostrava onze
anos reconstruídos nos três perfis — e 2026 era outra coisa, sem que nada
avisasse o leitor.

Este programa converte a decisão de janeiro de 2026 nos perfis para o
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
import sys

# Rodado como script, o Python põe tools/ no sys.path, não a raiz do
# repositório — então os módulos de pesquisa que vivem na raiz não são
# encontrados. Sob pytest isso não aparece, porque o pytest insere a raiz
# sozinho: o teste passa e o script quebra, que foi exatamente o que houve.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from portfolio_risk import risk_profile_spec  # noqa: E402
from politica import REGISTRO, escada  # noqa: E402
from update_live_performance import update  # noqa: E402
BOOKS = ROOT / "artifacts" / "profile_books_2026" / "profile_books_2026.json"
WEB = ROOT / "web"
GLOBAL_TICKER = "IVVB11"
def overlay_for(profile: str, registration: dict) -> tuple[dict, list[float]]:
    """Gatilhos e ação da camada, lidos do registro congelado."""
    spec = risk_profile_spec(profile)
    return registration["intrayear_overlay"]["config"], [spec.alert_multiplier, spec.severe_multiplier]


def decision_document(book: dict, source: dict) -> dict:
    """O livro de um perfil no formato que o monitor consome."""
    # O registro vigente, lido de politica.py e não de um caminho escrito aqui.
    # Este arquivo apontava para a v3 enquanto a escada publicava a v4, e o resumo
    # diário saía carimbado com uma política que não declara o quarto degrau que
    # ele mesmo listava. A camada é a mesma nas duas versões; o selo não era.
    registration = json.loads(REGISTRO.read_text(encoding="utf-8"))
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
        # O livro foi construído sob a v3 e é governado pela v4, que a substitui
        # com os mesmos parâmetros para este perfil. As duas ficam nomeadas: a
        # vigente em policy, a de construção em built_under. Só a v3 aparecia, e o
        # site publicava dois hashes "vigentes" em páginas diferentes.
        "policy": registration["policy"],
        "registration_sha256": registration["registration_sha256"],
        "built_under_policy": source["policy"],
        "built_under_sha256": source["registration_sha256"],
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
    # Duas políticas viajam aqui, e as duas precisam ser nomeadas. Os livros de
    # janeiro foram construídos sob a v3, e isso é procedência: fica em
    # built_under. O que governa hoje é a v4, que a substitui com os mesmos
    # parâmetros para estes três perfis e acrescenta o quarto: fica em policy.
    # Antes só a v3 aparecia, num resumo que listava um perfil que ela não declara.
    vigente = json.loads(REGISTRO.read_text(encoding="utf-8"))
    summary = {"decision_date": source["decision_date"],
               "policy": vigente["policy"],
               "registration_sha256": vigente["registration_sha256"],
               "built_under_policy": source["policy"],
               "built_under_sha256": source["registration_sha256"],
               "approved_by": source["approved_by"], "honesty": source["honesty"],
               "profiles": {}}
    for profile in escada():
        decision_path = WEB / f"current_decision_2026_{profile}.json"
        if profile in source["books"]:
            document = decision_document(source["books"][profile], source)
            decision_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
            emissores = len(source["books"][profile]["positions"])
        else:
            # Um degrau declarado depois de janeiro não tem livro congelado em
            # janeiro, e não pode ganhar um agora: o livro dele é derivado do
            # conservador, e quem deriva é o gerador do degrau. Aqui só se lê, e
            # só se o arquivo disser de onde veio. Sem essa marca ele ficaria
            # indistinguível de uma decisão tomada na época, que é justamente a
            # confusão que este projeto existe para não cometer.
            document = json.loads(decision_path.read_text(encoding="utf-8"))
            if "derivation" not in document:
                raise SystemExit(
                    f"{profile}: sem livro em janeiro e sem procedência declarada em "
                    f"{decision_path.name}. Rode tools/build_ultraconservador_book.py.")
            emissores = sum(1 for h in document["holdings"] if h["ticker"] != GLOBAL_TICKER)
        live = update(decision_path, WEB / f"live_performance_{profile}.json",
                      args.as_of, args.force)
        summary["profiles"][profile] = {
            "through": live["through"],
            "portfolio_return": live["summary"]["portfolio_return"],
            "equity_weight": document["declared"]["maximum_equity_weight"],
            "issuers": emissores,
            "record_sha256": live["record_sha256"],
            # Os três primeiros foram marcados a mercado dia a dia enquanto o ano
            # acontecia. O quarto foi reconstruído de uma vez, depois. Mesma
            # seleção, mesmos preços, mesma função: procedência diferente, e ela
            # viaja junto do número em vez de ficar só no texto ao lado.
            "reconstructed": profile not in source["books"],
        }
        marca = "" if profile in source["books"] else " · reconstruído"
        print(f"{profile:<17} até {live['through']} · "
              f"{live['summary']['portfolio_return']:+.2%} · "
              f"registro {live['record_sha256'][:12]}{marca}")


    (WEB / "live_profiles_2026.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
