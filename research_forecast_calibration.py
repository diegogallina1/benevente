"""Esperado × realizado: o intervalo que a regra projeta contém o que aconteceu?

Existe uma versão desonesta desta pergunta e uma honesta, e elas se parecem.

A desonesta projeta um número — "este perfil rende 15% ao ano" — e o publica ao
lado do histórico. É a frase que todo material de venda tem, é indefensável, e
seria a primeira coisa que um comitê usaria contra o produto no primeiro ano
ruim. O site diz, hoje, que não há projeção de patrimônio futuro em página
alguma.

A honesta projeta uma **distribuição** e depois mede se ela estava certa. Em
cada janeiro, com apenas os dados daquele momento, a regra produz um intervalo:
"em 80% dos casos, o ano seguinte deve ficar entre X e Y". Doze meses depois o
resultado chega e cai dentro ou fora. Repetindo onze vezes, dá para perguntar:
dos onze anos, quantos caíram dentro? Se a resposta for muito menor que nove, o
intervalo é estreito demais e o modelo é confiante demais — e isso é informação
publicável, ao contrário de um número prometido.

A projeção aqui não é um produto: é um instrumento de medição do próprio
modelo. O que se publica é a calibração, não a previsão.

Disciplina de data: a distribuição do ano *t* usa exclusivamente retornos
diários anteriores ao primeiro pregão de *t*. Nenhuma reamostragem enxerga o
ano que está prevendo.
"""
from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

from profile_ladder_v2 import LADDER_V2, evaluate
from profile_ladder_v3 import V3_INPUTS
from research_real_cash import _engine, panels

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "forecast_calibration_v1"
START_YEAR, END_YEAR = 2015, 2026
#: Blocos de vinte pregões preservam a autocorrelação de curto prazo que uma
#: reamostragem independente destrói — e é justamente ela que faz um ano ruim
#: ser ruim por semanas seguidas, não por um dia.
BLOCK = 20
DRAWS = 20_000
QUANTILES = (0.10, 0.50, 0.90)
MINIMUM_HISTORY_DAYS = 252 * 2
SEED = 20260826


def block_bootstrap(returns: np.ndarray, horizon: int, draws: int, rng: np.random.Generator) -> np.ndarray:
    """Distribuição do retorno acumulado em ``horizon`` pregões."""
    blocks = max(1, math.ceil(horizon / BLOCK))
    starts = rng.integers(0, max(1, len(returns) - BLOCK), size=(draws, blocks))
    paths = np.empty(draws)
    for i in range(draws):
        sample = np.concatenate([returns[s:s + BLOCK] for s in starts[i]])[:horizon]
        paths[i] = np.prod(1.0 + sample) - 1.0
    return paths


def forecast_year(daily: pd.Series, dates: pd.Series, year: int, rng) -> dict | None:
    """O intervalo de um ano, estimado só com o que existia em janeiro dele."""
    frame = pd.DataFrame({"r": daily.to_numpy(), "d": pd.to_datetime(dates).to_numpy()})
    history = frame[frame.d.dt.year < year]
    target = frame[frame.d.dt.year == year]
    if len(history) < MINIMUM_HISTORY_DAYS or len(target) < 200:
        return None
    paths = block_bootstrap(history.r.to_numpy(), len(target), DRAWS, rng)
    low, mid, high = (float(np.quantile(paths, q)) for q in QUANTILES)
    realised = float(np.prod(1.0 + target.r.to_numpy()) - 1.0)
    return {
        "year": int(year),
        "history_days": int(len(history)),
        "horizon_days": int(len(target)),
        "p10": round(low, 6), "p50": round(mid, 6), "p90": round(high, 6),
        "realised": round(realised, 6),
        "inside": bool(low <= realised <= high),
        "above": bool(realised > high),
        "below": bool(realised < low),
    }


def main() -> None:
    published, real = panels()
    engine = _engine(real)
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    resultado = {}
    linhas = []
    for profile in LADDER_V2:
        series, meta = evaluate(profile, engine, real, START_YEAR, END_YEAR)
        dates = meta["daily"].date
        anos = [forecast_year(series, dates, y, rng) for y in sorted(set(pd.to_datetime(dates).dt.year))]
        anos = [a for a in anos if a]
        dentro = sum(a["inside"] for a in anos)
        resultado[profile] = {
            "years": anos,
            "coverage": {"inside": dentro, "total": len(anos),
                         "observed": round(dentro / len(anos), 4) if anos else None,
                         "nominal": 0.80,
                         "standard_error": round(math.sqrt(.8 * .2 / len(anos)), 4) if anos else None},
            "median_bias_pp": round(float(np.mean([a["realised"] - a["p50"] for a in anos])) * 100, 3),
        }
        linhas.append((profile, anos, resultado[profile]))

    for profile, anos, r in linhas:
        c = r["coverage"]
        print(f"\n=== {profile.upper()} · intervalo de 80% ===")
        print(f"{'ano':>6}{'p10':>9}{'p50':>9}{'p90':>9}{'realizado':>11}  dentro")
        for a in anos:
            marca = "sim" if a["inside"] else ("ACIMA" if a["above"] else "ABAIXO")
            print(f"{a['year']:>6}{a['p10']*100:>8.1f}%{a['p50']*100:>8.1f}%{a['p90']*100:>8.1f}%"
                  f"{a['realised']*100:>10.1f}%  {marca}")
        print(f"  cobertura: {c['inside']} de {c['total']} = {c['observed']:.0%} "
              f"(nominal 80%, erro padrão {c['standard_error']:.0%})")
        print(f"  viés da mediana: {r['median_bias_pp']:+.2f} pp ao ano")

    (OUT / "calibration.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "question": ("O intervalo de 80% que a regra projeta em cada janeiro contém o ano seguinte "
                     "em 80% das vezes? A pergunta é sobre a honestidade da incerteza, não sobre "
                     "acerto de retorno."),
        "method": {"estimator": "block bootstrap", "block_days": BLOCK, "draws": DRAWS,
                   "seed": SEED, "point_in_time": "só retornos anteriores ao primeiro pregão do ano previsto",
                   "minimum_history_days": MINIMUM_HISTORY_DAYS},
        "limitation": ("Onze observações anuais dão erro padrão de doze pontos na cobertura: só "
                       "um desvio grande é distinguível de ruído. E a distribuição é reamostrada "
                       "da própria janela, então não contém regime que a janela não tenha."),
        "profiles": resultado,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
