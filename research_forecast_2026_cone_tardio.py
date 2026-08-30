# -*- coding: utf-8 -*-
"""A faixa de 2026 de um degrau declarado depois de janeiro.

O cone de janeiro não pode ser recalculado. Ele foi desenhado uma vez, com
dados anteriores ao primeiro pregão de 2026, e reabrir o arquivo para
acrescentar um perfil moveria as faixas dos outros três: o gerador sorteia com
um contador único, então a ordem dos perfis decide os sorteios de todos.
Números publicados em janeiro se mexeriam em agosto sem que o método deles
tivesse mudado, e a faixa deixaria de medir o que promete medir.

Então o degrau tardio ganha faixa própria, num arquivo separado, e com três
diferenças declaradas em vez de escondidas:

* o gerador de números vem do nome do perfil, e não de um contador
  compartilhado. Nada que se faça aqui alcança as faixas de janeiro;
* o estimador é o de perfil dominado por caixa. A reamostragem em blocos, que
  serve para os outros três, acerta uma vez em oito num perfil que é 96% caixa,
  porque os blocos carregam o nível de Selic que existia então. A perna de caixa
  é sorteada da distribuição de retornos de doze meses do caixa, e só a perna de
  risco continua reamostrada. Isso está medido em research_forecast_calibration;
* a data em que a faixa foi desenhada viaja com ela. As de janeiro foram
  declaradas antes do ano. Esta foi desenhada em 30/08/2026, com dados
  anteriores a 2026: a disciplina de entrada se manteve, a de declaração não, e
  quem lê precisa poder distinguir as duas coisas.

O que isto não é: uma faixa que previu 2026. Nenhuma linha aqui viu um preço de
2026, mas ninguém a desenhou antes do ano tampouco. Ela serve para enquadrar o
resultado do degrau, e não para entrar na contagem de cobertura, que continua
sendo dos anos fechados de 2015 a 2025.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math

import numpy as np
import pandas as pd

from profile_ladder_v2 import GLOBAL_FRACTION, LADDER_V2, evaluate
from research_forecast_calibration import DOMINADO_POR_CAIXA, _caixa_doze_meses
from research_forecast_2026_cone import (ANO, BLOCK, DRAWS, END_YEAR, HORIZONTE_MAXIMO,
                                         OUT, PASSO, QUANTILES, SEED, START_YEAR)
from research_real_cash import _engine, panels

ROOT = Path(__file__).resolve().parent
DESTINO = OUT / "cone_tardio.json"
#: Pregões num ano. Converte o retorno de doze meses do caixa no pedaço de ano
#: que já passou: o carrego acumula liso, sem caminho, que é o que ele é.
PREGOES_NO_ANO = 252
#: Quando a faixa foi desenhada. Não é a data da decisão nem a do congelamento
#: da cesta: é a data em que esta faixa passou a existir, e ela é diferente da
#: dos outros três perfis de propósito.
DESENHADA_EM = "2026-08-30"


def caminhos_de_risco(retornos: np.ndarray, horizonte: int, rng) -> np.ndarray:
    """Os caminhos acumulados da perna de risco, sorteados uma vez só."""
    blocos = max(1, math.ceil(horizonte / BLOCK))
    inicios = rng.integers(0, max(1, len(retornos) - BLOCK), size=(DRAWS, blocos))
    caminhos = np.empty((DRAWS, horizonte))
    for i in range(DRAWS):
        amostra = np.concatenate([retornos[s:s + BLOCK] for s in inicios[i]])[:horizonte]
        caminhos[i] = np.cumprod(1.0 + amostra) - 1.0
    return caminhos


def faixa(perfil: str, engine, real) -> dict:
    """A faixa por horizonte do degrau, com a incerteza que manda nele."""
    rng = np.random.default_rng(
        [SEED, int(hashlib.sha256(perfil.encode("utf-8")).hexdigest()[:8], 16)])
    _, meta = evaluate(perfil, engine, real, START_YEAR, END_YEAR)
    datas = pd.to_datetime(meta["daily"].date)
    antes = (datas.dt.year < ANO).to_numpy()

    risco_diario = meta["daily"].equity_sleeve.pct_change().fillna(0.0).to_numpy()[antes]
    peso_risco = float(LADDER_V2[perfil]["maximum_equity_weight"]) * (1 + GLOBAL_FRACTION)
    if peso_risco > DOMINADO_POR_CAIXA:
        raise SystemExit(f"{perfil}: com {peso_risco:.1%} em risco o estimador daqui não vale.")

    conhecido = _caixa_doze_meses()
    conhecido = conhecido[conhecido.index < f"{ANO}-01-01"].to_numpy()
    caixa_ano = rng.choice(conhecido, size=DRAWS, replace=True)
    risco = caminhos_de_risco(risco_diario, HORIZONTE_MAXIMO, rng)

    pontos = list(range(PASSO, HORIZONTE_MAXIMO + 1, PASSO))
    if pontos[-1] != HORIZONTE_MAXIMO:
        pontos.append(HORIZONTE_MAXIMO)
    linhas = []
    for h in pontos:
        caixa_h = (1.0 + caixa_ano) ** (h / PREGOES_NO_ANO) - 1.0
        corte = (1 - peso_risco) * caixa_h + peso_risco * risco[:, h - 1]
        p10, p50, p90 = (float(np.quantile(corte, q)) for q in QUANTILES)
        linhas.append({"sessions": h, "p10": round(p10, 6),
                       "p50": round(p50, 6), "p90": round(p90, 6)})
    return {
        "history_days": int(antes.sum()),
        "cash_windows_known": int(len(conhecido)),
        "risk_weight": round(peso_risco, 6),
        "drawn_on": DESENHADA_EM,
        "band": linhas,
    }


def main() -> None:
    published, real = panels()
    engine = _engine(real)
    OUT.mkdir(parents=True, exist_ok=True)
    cone = json.loads((OUT / "cone.json").read_text(encoding="utf-8"))
    tardios = [p for p in LADDER_V2 if p not in cone["profiles"]]

    documento = {
        "status": "instrumento de medição do modelo, não previsão de patrimônio",
        "year": ANO,
        "question": ("Para o número de pregões já decorridos de 2026, o resultado do "
                     "degrau está dentro da faixa que a regra projeta com dados "
                     "anteriores a 2026?"),
        "method": {
            "estimator": "caixa de doze meses mais bootstrap de blocos na perna de risco",
            "block_days": BLOCK, "draws": DRAWS, "seed": SEED,
            "seed_per_profile": "derivada do nome, para não alcançar as faixas de janeiro",
            "point_in_time": "só dados anteriores ao primeiro pregão de 2026",
            "step_sessions": PASSO,
        },
        "limitation": ("Esta faixa não foi declarada antes do ano: ela foi desenhada em "
                       f"{'/'.join(reversed(DESENHADA_EM.split('-')))}, depois que o degrau "
                       "passou a existir. Nenhum dado "
                       "de 2026 entrou nela, mas ela não tem a propriedade que as de "
                       "janeiro têm, e por isso não entra em contagem de cobertura."),
        "profiles": {p: faixa(p, engine, real) for p in tardios},
    }
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    for perfil, r in documento["profiles"].items():
        b = r["band"]
        print(f"{perfil:<17} {r['history_days']} pregões de história · "
              f"faixa de {len(b)} pontos · ano cheio "
              f"{b[-1]['p10']*100:+.1f}% a {b[-1]['p90']*100:+.1f}%")
    print(f"{DESTINO.relative_to(ROOT)}: {DESTINO.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    main()
