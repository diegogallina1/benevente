# -*- coding: utf-8 -*-
"""O livro de 2026 do ultraconservador, derivado e não decidido.

O degrau foi declarado em 30/08/2026, com o ano já em curso. Escrever para ele
um "livro de janeiro" seria inventar uma decisão que ninguém tomou, e ela
ficaria indistinguível das três que foram de fato congeladas em 02/01.

A regra do degrau evita isso. Ela move o teto de ações e não toca na seleção:
os ativos do ultraconservador são os mesmos que o conservador escolheu em
janeiro, com metade do peso, e a diferença vai para o CDI. Nada aqui é uma
escolha nova sobre quais papéis comprar.

Por isso o arquivo sai marcado como derivado, com a data da derivação e o livro
de origem. Quem ler sabe que a seleção é de 02/01/2026 e que o teto é de
30/08/2026, que são coisas diferentes e precisam continuar diferentes.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
for _caminho in (ROOT, ROOT / "tools"):
    if str(_caminho) not in sys.path:
        sys.path.insert(0, str(_caminho))

from update_live_performance import update  # noqa: E402
WEB = ROOT / "web"
REGISTRO = ROOT / "data" / "benevente_profile_ladder_v4_registration.json"
ORIGEM = "conservador"
DESTINO_PERFIL = "ultraconservador"


def build() -> dict:
    registro = json.loads(REGISTRO.read_text(encoding="utf-8"))
    declarado = registro["profiles"][DESTINO_PERFIL]
    base = json.loads((WEB / f"current_decision_2026_{ORIGEM}.json").read_text(encoding="utf-8"))
    origem_teto = registro["profiles"][ORIGEM]["maximum_equity_weight"]
    fator = declarado["maximum_equity_weight"] / origem_teto

    livro = dict(base)
    livro["profile"] = DESTINO_PERFIL
    livro["declared"] = {
        "maximum_equity_weight": declarado["maximum_equity_weight"],
        "top_assets": declarado["top_assets"],
        "maximum_asset_weight": declarado["maximum_asset_weight"],
        "global_share_of_portfolio": declarado["global_share_of_portfolio"],
    }
    # Cada posição vale a mesma fração do que valia no conservador, inclusive a
    # global: o degrau é uma escala da carteira inteira, não uma nova seleção.
    livro["holdings"] = [dict(h, weight=round(h["weight"] * fator, 6)) for h in base["holdings"]]
    livro["cdi_weight"] = round(1.0 - sum(h["weight"] for h in livro["holdings"]), 6)
    livro["policy"] = registro["policy"]
    livro["registration_sha256"] = registro["registration_sha256"]
    livro["derivation"] = {
        "derived_from": f"current_decision_2026_{ORIGEM}.json",
        "derived_on": declarado["declared_on"],
        "factor": round(fator, 6),
        "selection_decided_on": base["decision_date"],
        "note": ("A seleção é a do conservador, congelada em 02/01/2026. O teto de ações "
                 "vem da regra do degrau, declarada em 30/08/2026. As duas datas são "
                 "diferentes de propósito e não devem ser fundidas."),
    }
    livro["honesty"] = declarado["status_note"]
    caminho = WEB / f"current_decision_2026_{DESTINO_PERFIL}.json"
    caminho.write_text(json.dumps(livro, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return livro


def acompanhar() -> dict:
    """A série de 2026 do degrau, pelo mesmo monitor que roda os outros três.

    O livro é derivado, a série não: ela sai da mesma função que produz as dos
    demais perfis, sobre os mesmos preços. O que difere é a procedência, e ela
    fica registrada: os outros três foram acompanhados dia a dia enquanto o ano
    acontecia, e este foi reconstruído de uma vez em 30/08/2026, com a seleção
    que já estava congelada desde janeiro.

    A reconstrução não tem liberdade nenhuma. A seleção é a do conservador, o
    fator vem da regra do degrau, e a camada de proteção é a mesma: não há
    escolha a fazer aqui que pudesse ser feita olhando o resultado.
    """
    destino = WEB / f"live_performance_{DESTINO_PERFIL}.json"
    return update(WEB / f"current_decision_2026_{DESTINO_PERFIL}.json", destino, None, True)


def main() -> None:
    livro = build()
    acoes = [h for h in livro["holdings"] if h["ticker"] != "IVVB11"]
    globais = [h for h in livro["holdings"] if h["ticker"] == "IVVB11"]
    print(f"web/current_decision_2026_{DESTINO_PERFIL}.json")
    print(f"  fator sobre o conservador: {livro['derivation']['factor']}")
    print(f"  ações {sum(h['weight'] for h in acoes) * 100:.1f}% · "
          f"global {sum(h['weight'] for h in globais) * 100:.1f}% · "
          f"CDI {livro['cdi_weight'] * 100:.1f}% · "
          f"soma {(sum(h['weight'] for h in livro['holdings']) + livro['cdi_weight']) * 100:.1f}%")
    live = acompanhar()
    print(f"  2026 até {live['through']}: "
          f"{live['summary']['portfolio_return'] * 100:+.2f}% (reconstruído, não acompanhado)")


if __name__ == "__main__":
    main()
