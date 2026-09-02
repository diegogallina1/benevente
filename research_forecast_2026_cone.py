"""A faixa de 2026 por pregão decorrido, contra o que está acontecendo.

A calibração do ano fechado responde uma pergunta de trás para frente: o ano
acabou, o resultado chegou, caiu dentro ou fora. Ela não serve para o ano em
curso, e comparar um ano pela metade com a faixa de um ano inteiro é comparar
coisas diferentes: em agosto o realizado está baixo porque faltam quatro meses,
não porque a carteira está atrás.

O que resolve é uma faixa por horizonte. Para cada quantidade de pregões
decorridos, a mesma reamostragem em blocos produz o intervalo de 80% daquele
pedaço de ano. Em agosto o realizado é comparado com a faixa de agosto.

A faixa inteira é calculada uma vez, com dados anteriores ao primeiro pregão de
2026, e não muda mais. O que muda todo dia é o outro lado: o realizado, que sai
do acompanhamento diário. Isso é deliberado. Uma faixa que se ajusta ao que
aconteceu não mede nada, porque nunca erra.

Continua valendo o que a calibração diz: isto é instrumento de medição do
modelo, não previsão de patrimônio. A faixa é larga de propósito, e o site
publica a cobertura observada ao lado dela.
"""
from __future__ import annotations

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd

from profile_ladder_v2 import LADDER_V2, evaluate
from research_real_cash import _engine, panels

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "forecast_2026_cone_v1"
ANO = 2026
START_YEAR, END_YEAR = 2015, 2026
BLOCK = 20
DRAWS = 20_000
QUANTILES = (0.10, 0.50, 0.90)
SEED = 20260826
#: A data de produção do artefato, gravada nele. O primeiro foi feito em
#: 27/08/2026, e o código dizia "calculada em janeiro" porque os dados eram de
#: antes de janeiro. Ninguém a calculou em janeiro.
DESENHADO_EM = "2026-08-27"
#: Pregões de um ano cheio na B3. A faixa é calculada até aqui, e o site usa a
#: linha correspondente ao número de pregões que já passaram.
HORIZONTE_MAXIMO = 250
#: A faixa é gravada de cinco em cinco pregões. Guardar as 250 linhas engordaria
#: o arquivo do site sem mudar nada que se enxergue: entre um pregão e o
#: seguinte a faixa se move menos de um décimo de ponto.
PASSO = 5


def cone(retornos: np.ndarray, horizonte: int, draws: int, rng) -> list[dict]:
    """A faixa acumulada em cada horizonte, de um conjunto só de caminhos.

    Reamostrar uma vez por horizonte daria faixas que não se encaixam: a de
    cem pregões poderia ficar acima da de duzentos, por ruído de amostragem. Os
    caminhos são sorteados uma vez e lidos em cada ponto, então a faixa cresce
    de forma monótona, como a de uma carteira de verdade.
    """
    blocos = max(1, math.ceil(horizonte / BLOCK))
    inicios = rng.integers(0, max(1, len(retornos) - BLOCK), size=(draws, blocos))
    caminhos = np.empty((draws, horizonte))
    for i in range(draws):
        amostra = np.concatenate([retornos[s:s + BLOCK] for s in inicios[i]])[:horizonte]
        caminhos[i] = np.cumprod(1.0 + amostra) - 1.0

    pontos = list(range(PASSO, horizonte + 1, PASSO))
    if pontos[-1] != horizonte:
        pontos.append(horizonte)
    linhas = []
    for h in pontos:
        corte = caminhos[:, h - 1]
        p10, p50, p90 = (float(np.quantile(corte, q)) for q in QUANTILES)
        linhas.append({"sessions": h, "p10": round(p10, 6),
                       "p50": round(p50, 6), "p90": round(p90, 6)})
    return linhas


def main() -> None:
    published, real = panels()
    engine = _engine(real)
    rng = np.random.default_rng(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    documento = {
        "status": "instrumento de medição do modelo, não previsão de patrimônio",
        "year": ANO,
        "question": ("Para o número de pregões já decorridos de 2026, o resultado "
                     "está dentro da faixa que a regra projetou em janeiro?"),
        "method": {
            "estimator": "block bootstrap",
            "block_days": BLOCK,
            "draws": DRAWS,
            "seed": SEED,
            "point_in_time": "só retornos anteriores ao primeiro pregão de 2026",
            "step_sessions": PASSO,
        },
        # A data em que este arquivo foi produzido. Sem ela, quem lê supõe que a
        # faixa é de janeiro porque os dados são anteriores a janeiro, e não é: a
        # disciplina de entrada (só dados anteriores ao ano) e a de declaração
        # (existir antes do ano) são coisas diferentes, e esta faixa só tem a
        # primeira.
        "drawn_on": DESENHADO_EM,
        "limitation": ("A faixa é uma só, desenhada com dados anteriores a 2026, e não "
                       "se ajusta ao que foi acontecendo. Um ano dentro da faixa não "
                       "confirma a regra: a cobertura só significa alguma coisa somando "
                       "muitos anos."),
        "profiles": {},
    }

    for profile in LADDER_V2:
        series, meta = evaluate(profile, engine, real, START_YEAR, END_YEAR)
        datas = pd.to_datetime(meta["daily"].date)
        historia = np.asarray(series)[(datas.dt.year < ANO).to_numpy()]
        documento["profiles"][profile] = {
            "history_days": int(len(historia)),
            "band": cone(historia, HORIZONTE_MAXIMO, DRAWS, rng),
        }
        b = documento["profiles"][profile]["band"]
        print(f"{profile:<13} {len(historia)} pregões de história · "
              f"faixa de {len(b)} pontos · ano cheio "
              f"{b[-1]['p10']*100:+.1f}% a {b[-1]['p90']*100:+.1f}%")

    destino = OUT / "cone.json"
    destino.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print(f"\n{destino.relative_to(ROOT)}: {destino.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
