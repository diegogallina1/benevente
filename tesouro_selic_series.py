"""Série diária do Tesouro Selic, líquida de custódia e de giro, como caixa real.

A parcela em caixa da escada foi sempre modelada como 100% do CDI capitalizado
diariamente — um índice, não um instrumento. Ninguém compra o CDI. O que um
escritório de fato aloca é Tesouro Selic, e ele rende um pouco menos que o
índice: paga taxa de custódia à B3, paga o spread entre o preço de compra e o de
venda a cada troca de papel, e negocia com um pequeno ágio ou deságio sobre a
Selic acumulada.

Este módulo reconstrói esse instrumento a partir da fonte primária — o arquivo
diário de preços e taxas do Tesouro Transparente — e produz um nível diário que
pode substituir a coluna de caixa do painel sem tocar em nenhuma outra parte do
motor. A diferença entre os dois é a resposta a uma pergunta que o projeto não
podia responder: quanto do resultado publicado vinha de um caixa que não existe.

Regras declaradas, todas verificáveis no arquivo de origem:

* Papel mantido: o Tesouro Selic de vencimento mais curto com pelo menos 180
  dias restantes. É o que minimiza o deságio de marcação e o que um caixa de
  fato carrega.
* Rolagem: quando o papel mantido cai abaixo de 180 dias, vende-se ao preço de
  venda e compra-se o próximo ao preço de compra. O spread é cobrado aí, uma vez
  por rolagem, e não diluído.
* Custódia da B3, pró-rata por pregão, na tabela histórica: 0,30% ao ano até
  2018, 0,25% de 2019 a 2021 e 0,20% de 2022 em diante. A isenção para os
  primeiros dez mil reais (agosto de 2020) não é aplicada: ela depende do saldo
  por CPF e favoreceria a série; deixá-la de fora mantém o número conservador.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import io
import json
import urllib.request

import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE_URL = ("https://www.tesourotransparente.gov.br/ckan/dataset/"
              "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
              "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv")
CACHE = ROOT / "data" / "tesouro_direto_precos_taxas.csv"
OUT = ROOT / "data" / "tesouro_selic_cash_index.csv"
MANIFEST = ROOT / "data" / "tesouro_selic_cash_index_manifest.json"

INSTRUMENT = "Tesouro Selic"
MINIMUM_DAYS_TO_MATURITY = 180
# Taxa de custódia da B3, ao ano, por período de vigência.
CUSTODY_SCHEDULE = ((2019, 0.0030), (2022, 0.0025), (9999, 0.0020))
SESSIONS_PER_YEAR = 252


def custody_rate(year: int) -> float:
    for limit, rate in CUSTODY_SCHEDULE:
        if year < limit:
            return rate
    return CUSTODY_SCHEDULE[-1][1]


def download(force: bool = False) -> pd.DataFrame:
    if force or not CACHE.exists():
        request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "benevente-research/1.0"})
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_bytes(urllib.request.urlopen(request, timeout=300).read())
    return pd.read_csv(io.BytesIO(CACHE.read_bytes()), sep=";", decimal=",", encoding="latin-1")


def build(frame: pd.DataFrame, start: str = "2010-01-01") -> tuple[pd.DataFrame, dict]:
    selic = frame[frame["Tipo Titulo"].eq(INSTRUMENT)].copy()
    selic["date"] = pd.to_datetime(selic["Data Base"], format="%d/%m/%Y")
    selic["maturity"] = pd.to_datetime(selic["Data Vencimento"], format="%d/%m/%Y")
    selic = selic[selic.date >= pd.Timestamp(start)].sort_values(["date", "maturity"])

    rows, held, held_pu, level, rolls = [], None, None, 100.0, 0
    for date, day in selic.groupby("date", sort=True):
        day = day.set_index("maturity")
        eligible = day[(day.index - date).days >= MINIMUM_DAYS_TO_MATURITY]
        if eligible.empty:
            continue
        target = eligible.index.min()

        if held is None:
            held, held_pu = target, float(day.at[target, "PU Compra Manha"])
            rows.append({"date": date, "level": level, "held": held.date(), "rolled": True})
            continue

        if held not in day.index:
            # Papel saiu da grade: rola no primeiro pregão em que isso aparece.
            target = eligible.index.min()
        elif (held - date).days < MINIMUM_DAYS_TO_MATURITY:
            target = eligible.index.min()
        else:
            target = held

        if target != held:
            proceeds = float(day.at[held, "PU Venda Manha"]) if held in day.index else held_pu
            level *= proceeds / held_pu
            held, held_pu = target, float(day.at[target, "PU Compra Manha"])
            rolls += 1
        else:
            today_pu = float(day.at[held, "PU Base Manha"])
            level *= today_pu / held_pu
            held_pu = today_pu

        level *= 1 - custody_rate(date.year) / SESSIONS_PER_YEAR
        rows.append({"date": date, "level": level, "held": held.date(), "rolled": target != held})

    series = pd.DataFrame(rows).drop_duplicates("date").reset_index(drop=True)
    years = (series.date.iloc[-1] - series.date.iloc[0]).days / 365.25
    summary = {
        "instrument": INSTRUMENT,
        "source": SOURCE_URL,
        "sessions": int(len(series)),
        "first": str(series.date.iloc[0].date()),
        "last": str(series.date.iloc[-1].date()),
        "rolls": int(rolls),
        "cagr": round(float((series.level.iloc[-1] / series.level.iloc[0]) ** (1 / years) - 1), 6),
        "rules": {
            "minimum_days_to_maturity": MINIMUM_DAYS_TO_MATURITY,
            "custody_schedule_annual": {"até 2018": 0.0030, "2019-2021": 0.0025, "2022+": 0.0020},
            "exemption_first_10k_applied": False,
            "roll_prices": "venda ao PU Venda, compra ao PU Compra; acúmulo diário ao PU Base",
        },
    }
    return series, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="rebaixa o arquivo de origem")
    args = parser.parse_args()

    raw = download(force=args.refresh)
    series, summary = build(raw)
    series[["date", "level", "held", "rolled"]].to_csv(OUT, index=False)
    summary["sha256"] = hashlib.sha256(OUT.read_bytes()).hexdigest()
    summary["source_sha256"] = hashlib.sha256(CACHE.read_bytes()).hexdigest()
    MANIFEST.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{summary['sessions']} pregões · {summary['first']} a {summary['last']} · "
          f"{summary['rolls']} rolagens · {summary['cagr']*100:.2f}% a.a. líquido de custódia")


if __name__ == "__main__":
    main()
