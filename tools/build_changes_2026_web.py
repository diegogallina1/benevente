# -*- coding: utf-8 -*-
"""O que mudou em cada carteira neste ano, quando e por quê.

A série diária de cada perfil tem 249 KB e a página não precisa dela: precisa
dos dias em que alguma coisa mudou, que são poucos. Este programa lê a série,
encontra as trocas de estado da camada de proteção e escreve só elas.

O "por quê" não é interpretação. A camada tem limites declarados na política
congelada em janeiro, e a troca acontece quando a queda ou a volatilidade do
mercado cruza um deles. O que se publica é o número que cruzou e o limite que
ele cruzou, lado a lado.

Um detalhe que muda a leitura: o sinal é lido no fechamento e a mudança é
executada no pregão seguinte. Sem isso a tabela pareceria dizer que a carteira
reagiu no mesmo instante, que é uma promessa que nenhum sistema real cumpre.
"""
from __future__ import annotations

from pathlib import Path
import json
from politica import escada

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DESTINO = WEB / "mudancas_2026.json"
#: Os degraus vêm da política. Ver tools/politica.py.
PERFIS = escada()
#: A perna global não é tocada pela camada: o sinal é doméstico.
GLOBAL = "IVVB11"


def _motivo(ponto: dict, cfg: dict) -> str:
    """Qual limite foi cruzado. Vem do dado, não de leitura de gráfico."""
    queda = abs(ponto.get("market_drawdown") or 0.0)
    vol = ponto.get("market_volatility") or 0.0
    razoes = []
    if queda >= cfg["severe_drawdown"]:
        razoes.append(f"queda de {queda * 100:.1f}%, acima do limite grave de "
                      f"{cfg['severe_drawdown'] * 100:.0f}%")
    elif queda >= cfg["alert_drawdown"]:
        razoes.append(f"queda de {queda * 100:.1f}%, acima do limite de alerta de "
                      f"{cfg['alert_drawdown'] * 100:.0f}%")
    if vol >= cfg["severe_volatility"]:
        razoes.append(f"volatilidade de {vol * 100:.1f}%, acima do limite grave de "
                      f"{cfg['severe_volatility'] * 100:.0f}%")
    elif vol >= cfg["alert_volatility"]:
        razoes.append(f"volatilidade de {vol * 100:.1f}%, acima do limite de alerta de "
                      f"{cfg['alert_volatility'] * 100:.0f}%")
    if not razoes:
        return (f"queda e volatilidade voltaram abaixo dos limites e ficaram assim por "
                f"{cfg['recovery_days']} pregões")
    return " e ".join(razoes)


def _por_ativo(holdings: list[dict], peso_global: float,
               antes: float, depois: float) -> list[dict]:
    """O peso de cada posição antes e depois de uma mudança.

    A camada multiplica a perna de ações inteira pelo mesmo fator, então o peso
    de cada ação é o de janeiro vezes o fator do momento. A perna global não é
    tocada, e o CDI é o resto: ele entra na lista como linha para que a soma
    feche em cem por cento na tela, sem a pessoa ter de fazer a conta.
    """
    linhas = []
    for h in holdings:
        f_antes = 1.0 if h["ticker"] == GLOBAL else antes
        f_depois = 1.0 if h["ticker"] == GLOBAL else depois
        linhas.append({"ticker": h["ticker"],
                       "before": round(h["weight"] * f_antes, 4),
                       "after": round(h["weight"] * f_depois, 4)})
    br_antes = sum(l["before"] for l in linhas if l["ticker"] != GLOBAL)
    br_depois = sum(l["after"] for l in linhas if l["ticker"] != GLOBAL)
    linhas.append({"ticker": "CDI",
                   "before": round(1.0 - br_antes - peso_global, 4),
                   "after": round(1.0 - br_depois - peso_global, 4)})
    return linhas


def build() -> dict:
    documento = {"year": 2026, "profiles": {}}
    for perfil in PERFIS:
        livro = json.loads((WEB / f"current_decision_2026_{perfil}.json").read_text(encoding="utf-8"))
        cfg = livro["overlay"]["config"]
        serie = json.loads((WEB / f"live_performance_{perfil}.json").read_text(encoding="utf-8"))["series"]

        # O peso de cada ação hoje. A camada não escolhe ativo: ela multiplica a
        # perna de ações inteira por um fator, igual para todas, e o que sai vai
        # para o CDI. A perna global fica parada, porque o sinal é doméstico.
        acoes = [h for h in livro["holdings"] if h["ticker"] != GLOBAL]
        globais = [h for h in livro["holdings"] if h["ticker"] == GLOBAL]
        br_janeiro = sum(h["weight"] for h in acoes)
        peso_global = sum(h["weight"] for h in globais)
        br_hoje = serie[-1]["benevente2_equity_weight"]
        fator = br_hoje / br_janeiro if br_janeiro else 1.0

        mudancas = []
        for i, ponto in enumerate(serie):
            if i == 0 or ponto["risk_state"] == serie[i - 1]["risk_state"]:
                continue
            anterior = serie[i - 1]
            mudancas.append({
                "date": ponto["date"],
                "observed_on": anterior["date"],
                "from_state": anterior["risk_state"],
                "to_state": ponto["risk_state"],
                "from_equity": round(anterior["benevente2_equity_weight"], 4),
                "to_equity": round(ponto["benevente2_equity_weight"], 4),
                # O que sai das ações vai para o CDI, e é isso que a pessoa vê
                # no extrato. O fator é o mesmo para todas as ações.
                "factor": round(ponto["benevente2_equity_weight"] / br_janeiro, 4)
                          if br_janeiro else None,
                "from_factor": round(anterior["benevente2_equity_weight"] / br_janeiro, 4)
                               if br_janeiro else None,
                "from_cdi": round(1.0 - anterior["benevente2_equity_weight"] - peso_global, 4),
                "to_cdi": round(1.0 - ponto["benevente2_equity_weight"] - peso_global, 4),
                # Ativo a ativo, porque "as ações caíram de 28% para 15%" não diz
                # quanto saiu de cada posição, que é o número que a pessoa
                # confere contra a corretora.
                "holdings": _por_ativo(
                    livro["holdings"], peso_global,
                    anterior["benevente2_equity_weight"] / br_janeiro if br_janeiro else 1.0,
                    ponto["benevente2_equity_weight"] / br_janeiro if br_janeiro else 1.0),
                # O sinal é do fechamento anterior: é ele que dispara a ordem.
                "why": _motivo(anterior, cfg),
            })
        documento["profiles"][perfil] = {
            "through": serie[-1]["date"],
            "thresholds": cfg,
            "changes": mudancas,
            # O estado de hoje, calculado aqui e não na página: é aritmética de
            # política, e política não se recalcula em três lugares diferentes.
            "now": {
                "date": serie[-1]["date"],
                "risk_state": serie[-1]["risk_state"],
                "factor": round(fator, 4),
                "equity_br": round(br_hoje, 4),
                "equity_br_january": round(br_janeiro, 4),
                "global": round(peso_global, 4),
                # O CDI é o resto: é ele que recebe o que sai das ações.
                "cdi": round(1.0 - br_hoje - peso_global, 4),
                "cdi_january": round(livro["cdi_weight"], 4),
                "holdings": [{"ticker": h["ticker"],
                              "january": round(h["weight"], 4),
                              "now": round(h["weight"] * (1.0 if h["ticker"] == GLOBAL else fator), 4)}
                             for h in livro["holdings"]],
            },
        }
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    return documento


def main() -> None:
    d = build()
    print(f"{DESTINO.relative_to(ROOT)}: {DESTINO.stat().st_size} bytes")
    for perfil, r in d["profiles"].items():
        print(f"  {perfil:<13} {len(r['changes'])} mudança(s) até {r['through']}")
        n = r["now"]
        print(f"     hoje: ações {n['equity_br'] * 100:.1f}% · global "
              f"{n['global'] * 100:.1f}% · CDI {n['cdi'] * 100:.1f}% "
              f"(fator {n['factor']:.2f} sobre janeiro)")
        for m in r["changes"]:
            print(f"     {m['date']}: ações {m['from_equity'] * 100:.1f}% para "
                  f"{m['to_equity'] * 100:.1f}%, CDI {m['from_cdi'] * 100:.1f}% para "
                  f"{m['to_cdi'] * 100:.1f}% · {m['why']}")


if __name__ == "__main__":
    main()
