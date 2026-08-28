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

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DESTINO = WEB / "mudancas_2026.json"
PERFIS = ("conservador", "equilibrado", "arrojado")


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


def build() -> dict:
    documento = {"year": 2026, "profiles": {}}
    for perfil in PERFIS:
        livro = json.loads((WEB / f"current_decision_2026_{perfil}.json").read_text(encoding="utf-8"))
        cfg = livro["overlay"]["config"]
        serie = json.loads((WEB / f"live_performance_{perfil}.json").read_text(encoding="utf-8"))["series"]

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
                # O sinal é do fechamento anterior: é ele que dispara a ordem.
                "why": _motivo(anterior, cfg),
            })
        documento["profiles"][perfil] = {
            "through": serie[-1]["date"],
            "thresholds": cfg,
            "changes": mudancas,
        }
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    return documento


def main() -> None:
    d = build()
    print(f"{DESTINO.relative_to(ROOT)}: {DESTINO.stat().st_size} bytes")
    for perfil, r in d["profiles"].items():
        print(f"  {perfil:<13} {len(r['changes'])} mudança(s) até {r['through']}")
        for m in r["changes"]:
            print(f"     {m['date']}: ações {m['from_equity'] * 100:.1f}% para "
                  f"{m['to_equity'] * 100:.1f}% · {m['why']}")


if __name__ == "__main__":
    main()
