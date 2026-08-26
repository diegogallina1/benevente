"""Quanto do resultado publicado vinha de um caixa que ninguém compra.

A escada declarada mantém entre 25% e 65% do patrimônio em caixa, e esse caixa
sempre foi modelado como 100% do CDI capitalizado diariamente. O CDI é um
índice: não tem custódia, não tem spread de compra e venda, não tem rolagem.
O instrumento que um escritório de fato aloca é Tesouro Selic, e ele rende
menos que o índice por essas três razões.

Este experimento troca uma única entrada — a coluna de caixa do painel — e roda
o mesmo código, a mesma janela e a mesma política congelada. Tudo o que mudar no
resultado é atribuível ao instrumento, porque nada mais mudou.
"""
from __future__ import annotations

from pathlib import Path
import json
import math

import pandas as pd

from advisor import snapshots_from_frame
from annual_decision_evidence import load_decision_evidence
from annual_walk_forward import AnnualWalkForwardEngine
from config import SystemConfig
from profile_ladder_v2 import LADDER_V2, evaluate
from research_global_sleeve import GLOBAL_INPUTS
from total_return_adapter import load_total_return_export

ROOT = Path(__file__).resolve().parent
SELIC = ROOT / "data" / "tesouro_selic_cash_index.csv"
OUT = ROOT / "artifacts" / "real_cash_v1"
START_YEAR, END_YEAR = 2015, 2026


def _engine(panel: pd.DataFrame) -> AnnualWalkForwardEngine:
    fundamentals = pd.read_csv(GLOBAL_INPUTS["fundamentals"], parse_dates=["as_of_date", "available_date"])
    evidence, _ = load_decision_evidence(str(GLOBAL_INPUTS["universe"]), str(GLOBAL_INPUTS["mapping"]))
    benchmarks = pd.read_csv(GLOBAL_INPUTS["benchmarks"], parse_dates=["date"]).set_index("date")
    return AnnualWalkForwardEngine(panel, snapshots_from_frame(fundamentals), SystemConfig(), evidence, benchmarks)


def panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    """O painel publicado e o mesmo painel com o caixa real no lugar do índice."""
    prices, _ = load_total_return_export(str(GLOBAL_INPUTS["prices"]), str(GLOBAL_INPUTS["total_return_manifest"]))
    published = prices.set_index("date")

    selic = pd.read_csv(SELIC, parse_dates=["date"]).set_index("date")["level"]
    aligned = selic.reindex(published.index).ffill()
    first = aligned.first_valid_index()
    if first is None:
        raise SystemExit("A série do Tesouro Selic não cobre o painel.")
    # Reescala para começar no mesmo nível do caixa publicado: o que interessa é
    # a trajetória do instrumento, não o número absoluto do índice.
    real = published.copy()
    real["TITULO_CDI"] = aligned * (published.at[first, "TITULO_CDI"] / aligned.loc[first])
    return published, real


def metrics(series: pd.Series, dates: pd.Series) -> dict:
    clean = series.fillna(0.0)
    wealth = (1 + clean).cumprod()
    years = max(int(pd.to_datetime(dates).dt.year.nunique()), 1)
    return {
        "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "vol": float(clean.std(ddof=1) * math.sqrt(252)),
        "drawdown": float((wealth / wealth.cummax() - 1).min()),
    }


def main() -> None:
    published, real = panels()
    rows = []
    for label, panel in (("índice (100% do CDI)", published), ("Tesouro Selic real", real)):
        engine = _engine(panel)
        for profile in LADDER_V2:
            series, meta = evaluate(profile, engine, panel, START_YEAR, END_YEAR)
            daily = meta["daily"]
            cash = panel["TITULO_CDI"].reindex(pd.to_datetime(daily.date)).dropna()
            years = max(int(pd.to_datetime(daily.date).dt.year.nunique()), 1)
            rows.append({
                "caixa": label, "perfil": profile,
                **metrics(series, daily.date),
                "caixa_cagr": float((cash.iloc[-1] / cash.iloc[0]) ** (1 / years) - 1),
            })
    frame = pd.DataFrame(rows)
    frame["excesso_pp"] = (frame.cagr - frame.caixa_cagr) * 100

    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "profiles_by_cash_instrument.csv", index=False)

    print(f"{'perfil':<13}{'caixa':<24}{'retorno':>9}{'queda':>9}{'caixa':>9}{'excesso':>10}")
    for _, r in frame.iterrows():
        print(f"{r.perfil:<13}{r.caixa:<24}{r.cagr*100:>8.2f}%{r.drawdown*100:>8.2f}%"
              f"{r.caixa_cagr*100:>8.2f}%{r.excesso_pp:>9.2f}pp")

    delta = []
    for profile in LADDER_V2:
        a = frame[(frame.perfil == profile) & (frame.caixa.str.startswith("índice"))].iloc[0]
        b = frame[(frame.perfil == profile) & (frame.caixa.str.startswith("Tesouro"))].iloc[0]
        delta.append({"perfil": profile,
                      "retorno_pp": round((b.cagr - a.cagr) * 100, 3),
                      "excesso_pp": round(b.excesso_pp - a.excesso_pp, 3)})
        print(f"\n{profile}: retorno {(b.cagr-a.cagr)*100:+.2f} pp · "
              f"excesso sobre o caixa {b.excesso_pp-a.excesso_pp:+.2f} pp")

    (OUT / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "question": "Quanto do resultado publicado dependia de um caixa que não é comprável?",
        "note": ("Única entrada trocada: a coluna TITULO_CDI do painel, do índice para o nível do "
                 "Tesouro Selic líquido de custódia e de spread de rolagem. Mesmo código, mesma "
                 "janela, mesma política congelada."),
        "delta": delta,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
