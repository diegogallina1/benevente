"""Export the unrestricted momentum candidate, labelled for what it is.

This rule was published as a frozen candidate. It was not: it ranked 57th of 73
on the grid's own declared training score and 1st on the holdout, so it was
picked after the holdout was read. The export keeps the series for the record
and states that selection openly instead of calling it frozen.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research_unrestricted_signal_grid import evaluate, make_weights, market_sessions, LOOKBACK
from total_return_adapter import load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "web" / "final_strategy_research.json"


def main() -> None:
    raw, manifest = load_total_return_export(
        ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv",
        ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json",
    )
    prices = raw.set_index("date").sort_index()
    annual = evaluate(prices, "momentum_12m_squared_inverse_volatility", "momentum", 252, 2.0, 1.0)
    years: list[dict] = []
    assets = prices.columns.drop("TITULO_CDI")
    for row in annual.itertuples(index=False):
        decision = prices.index[prices.index.year == row.year][0]
        prior = market_sessions(prices.loc[prices.index < decision, assets]).tail(LOOKBACK + 1)
        eligible = prior.columns[prior.notna().all()].tolist()
        weights = make_weights(prior.loc[:, eligible], "momentum", 252, 2.0, 1.0).sort_values(ascending=False)
        years.append({
            "year": int(row.year), "decision_date": decision.date().isoformat(),
            "eligible_assets": int(row.eligible_assets), "net_return": float(row.net_return),
            "gross_return": float(row.gross_return), "cdi_return": float(row.cdi_return),
            "turnover": float(row.turnover),
            "top_holdings": [{"ticker": ticker, "weight": float(weight)} for ticker, weight in weights.head(15).items()],
        })
    wealth, cdi, mvo = [100.0], [100.0], [100.0]
    for row in annual.itertuples(index=False):
        wealth.append(round(wealth[-1] * (1 + row.net_return), 4))
        cdi.append(round(cdi[-1] * (1 + row.cdi_return), 4))
    mvo_ledger = pd.read_csv(ROOT / "data" / "shadow_retro_momentum_2015_2025" / "annual_ledger.csv")
    for row in mvo_ledger.itertuples(index=False):
        mvo.append(round(mvo[-1] * (1 + row.mvo_net_return), 4))
    ibovespa_meta = json.loads((ROOT / "web" / "annual_research.json").read_text(encoding="utf-8"))["meta"]["ibovespa"]
    ibovespa_by_date = dict(zip(ibovespa_meta["dates"], ibovespa_meta["values_base_100"]))
    curve_dates = [item["decision_date"] for item in years] + ["2025-12-31"]
    ibovespa = [round(float(ibovespa_by_date[date]), 4) for date in curve_dates]
    OUT.write_text(json.dumps({
        "name": "Momentum Anual Diversificado Ajustado por Volatilidade",
        "status": "exploratory_selected_after_reading_the_holdout",
        "selection_warning": ("Esta regra ficou em 57º de 73 pelo critério de treino declarado e em 1º no holdout. "
                              "Foi escolhida depois de olhar o resultado do holdout, portanto o excesso sobre o CDI "
                              "que ela mostra é estatística dentro da amostra, não evidência fora dela. "
                              "Ver artifacts/inference_audit/signal_grid_inference.json."),
        "method": "Retorno de 12 meses em ranking transversal; peso proporcional ao quadrado do ranking dividido pela volatilidade de 12 meses.",
        "rule_limits": "Nenhum filtro de qualidade, setor, emissor, peso máximo ou número máximo de ativos.",
        "data_limitation": "Pesquisa com preços ajustados de fonte pública, restrita aos emissores que o provedor ainda serve: esta série específica ainda carrega viés de sobrevivência. O painel corrigido está em data/prices_b3_total_return_full_2013_2025.csv.",
        "source": manifest.get("provider"),
        "years": years,
        "curve": {
            "dates": curve_dates,
            "strategy": wealth,
            "mvo": mvo,
            "cdi": cdi,
            "ibovespa": ibovespa,
        },
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
