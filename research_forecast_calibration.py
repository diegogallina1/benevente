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
import hashlib
import json
import math

import numpy as np
import pandas as pd

from profile_ladder_v2 import GLOBAL_FRACTION, LADDER_V2, evaluate
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
#: Um ano cujo realizado está a menos disto de uma das pontas da faixa é decidido
#: por ruído de Monte Carlo, não pelo método. Publicar a contagem sem marcar
#: esses anos esconde que a contagem tem casas decimais que ninguém tem.
BORDA_PP = 0.0025


def block_bootstrap(returns: np.ndarray, horizon: int, draws: int, rng: np.random.Generator) -> np.ndarray:
    """Distribuição do retorno acumulado em ``horizon`` pregões."""
    blocks = max(1, math.ceil(horizon / BLOCK))
    starts = rng.integers(0, max(1, len(returns) - BLOCK), size=(draws, blocks))
    paths = np.empty(draws)
    for i in range(draws):
        sample = np.concatenate([returns[s:s + BLOCK] for s in starts[i]])[:horizon]
        paths[i] = np.prod(1.0 + sample) - 1.0
    return paths


#: Abaixo deste peso em risco, o retorno do perfil é dominado pelo caixa e a
#: reamostragem de blocos deixa de valer. Ver ``forecast_year_cash``.
DOMINADO_POR_CAIXA = 0.20
CAIXA = ROOT / "data" / "tesouro_selic_cash_index.csv"


def _caixa_doze_meses() -> pd.Series:
    """Retorno de doze meses do caixa, por dia de início.

    É a série que carrega a variação da Selic *entre* anos, que é justamente o
    que a reamostragem de blocos diários apaga.
    """
    nivel = pd.read_csv(CAIXA, parse_dates=["date"]).set_index("date")["level"]
    return (nivel.shift(-252) / nivel - 1).dropna()


def forecast_year_cash(carteira: pd.Series, sleeve: pd.Series, dates: pd.Series, year: int,
                       peso_risco: float, caixa12: pd.Series, rng) -> dict | None:
    """A faixa de um perfil dominado por caixa, onde a incerteza é a da Selic.

    O método padrão reamostra blocos de vinte pregões do retorno do próprio
    perfil. Num perfil quase todo caixa, esses blocos carregam o nível de Selic
    que existia então, e o resultado é uma faixa de três pontos de largura que
    erra sempre que a taxa muda de patamar: entre 2018 e 2025 ela foi de dois
    dígitos a 2% e voltou, e a faixa acertou uma vez em oito.

    Aqui a perna de caixa é sorteada da distribuição de retornos de doze meses
    do caixa conhecida até janeiro daquele ano, e a perna de risco continua com
    a reamostragem em blocos. A faixa passa a descrever a incerteza que de fato
    manda no perfil.

    O que ela continua sem cobrir é taxa fora de tudo que já se viu, e isso é
    honesto: em 2020 a Selic foi a 2%, abaixo de qualquer janela de 2010 a 2019.
    """
    # O realizado é o da carteira. A perna de risco só alimenta o sorteio: medir
    # a carteira contra uma faixa e comparar com o retorno da perna de ações foi
    # o primeiro erro desta função, e ele aparecia como viés de nove pontos.
    frame = pd.DataFrame({"r": sleeve.to_numpy(), "c": carteira.to_numpy(),
                          "d": pd.to_datetime(dates).to_numpy()})
    history = frame[frame.d.dt.year < year]
    target = frame[frame.d.dt.year == year]
    if len(history) < MINIMUM_HISTORY_DAYS or len(target) < 200:
        return None
    conhecido = caixa12[caixa12.index < f"{year}-01-01"].to_numpy()
    if len(conhecido) < 252:
        return None

    risco = block_bootstrap(history.r.to_numpy(), len(target), DRAWS, rng)
    caixa = rng.choice(conhecido, size=DRAWS, replace=True)
    amostra = (1 - peso_risco) * caixa + peso_risco * risco
    low, mid, high = (float(np.quantile(amostra, q)) for q in QUANTILES)
    realised = float(np.prod(1.0 + target.c.to_numpy()) - 1.0)
    return {
        "year": int(year), "history_days": int(len(history)),
        "horizon_days": int(len(target)), "cash_windows_known": int(len(conhecido)),
        "p10": round(low, 6), "p50": round(mid, 6), "p90": round(high, 6),
        "realised": round(realised, 6),
        "inside": bool(low <= realised <= high),
        "above": bool(realised > high), "below": bool(realised < low),
        "on_edge": bool(min(abs(realised - low), abs(realised - high)) < BORDA_PP),
        "band_source": "retorno de doze meses do caixa conhecido até janeiro",
    }


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
        "on_edge": bool(min(abs(realised - low), abs(realised - high)) < BORDA_PP),
    }


def main() -> None:
    published, real = panels()
    engine = _engine(real)
    OUT.mkdir(parents=True, exist_ok=True)

    resultado = {}
    linhas = []
    caixa12 = _caixa_doze_meses()
    for profile in LADDER_V2:
        # Um gerador por perfil, derivado do nome. Com um só, acrescentar um
        # perfil na frente da lista muda os sorteios de todos os outros, e
        # números publicados se mexem sem que o método deles tenha mudado.
        rng = np.random.default_rng(
            [SEED, int(hashlib.sha256(profile.encode("utf-8")).hexdigest()[:8], 16)])
        series, meta = evaluate(profile, engine, real, START_YEAR, END_YEAR)
        dates = meta["daily"].date
        anos_disponiveis = sorted(set(pd.to_datetime(dates).dt.year))
        # O peso em risco do perfil decide qual estimador vale. Não é escolha por
        # perfil: é o domínio de validade do método, e ele está no número.
        peso_risco = float(LADDER_V2[profile]["maximum_equity_weight"]) * (1 + GLOBAL_FRACTION)
        if peso_risco <= DOMINADO_POR_CAIXA:
            anos = [forecast_year_cash(series, meta["daily"].equity_sleeve.pct_change().fillna(0.0),
                                       dates, y, peso_risco, caixa12, rng)
                    for y in anos_disponiveis]
        else:
            anos = [forecast_year(series, dates, y, rng) for y in anos_disponiveis]
        anos = [a for a in anos if a]
        dentro = sum(a["inside"] for a in anos)
        resultado[profile] = {
            "years": anos,
            "coverage": {"inside": dentro, "total": len(anos),
                         "observed": round(dentro / len(anos), 4) if anos else None,
                         "nominal": 0.80,
                         "standard_error": round(math.sqrt(.8 * .2 / len(anos)), 4) if anos else None},
            "median_bias_pp": round(float(np.mean([a["realised"] - a["p50"] for a in anos])) * 100, 3),
            # Anos decididos na borda. A contagem de cobertura vira ou não vira
            # conforme eles, e quem lê precisa saber quantos são.
            "on_edge_years": [a["year"] for a in anos if a["on_edge"]],
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

    _amostra = min(len(r["years"]) for r in resultado.values())
    (OUT / "calibration.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "question": ("O intervalo de 80% que a regra projeta em cada janeiro contém o ano seguinte "
                     "em 80% das vezes? A pergunta é sobre a honestidade da incerteza, não sobre "
                     "acerto de retorno."),
        "method": {"estimator": "block bootstrap", "block_days": BLOCK, "draws": DRAWS,
                   "seed": SEED, "point_in_time": "só retornos anteriores ao primeiro pregão do ano previsto",
                   "minimum_history_days": MINIMUM_HISTORY_DAYS},
        # Derivada da amostra, não escrita à mão. A versão anterior dizia "onze
        # observações" e "doze pontos" enquanto o artefato trazia oito e catorze
        # — e o site publicava as duas contas contraditórias no mesmo parágrafo.
        "limitation": (
            f"{_amostra} observações anuais dão erro padrão de "
            f"{round(math.sqrt(.8 * .2 / _amostra) * 100)} pontos na cobertura: só um desvio "
            f"grande é distinguível de ruído. E a distribuição é reamostrada da própria "
            f"janela, então não contém regime que a janela não tenha."),
        "profiles": resultado,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
