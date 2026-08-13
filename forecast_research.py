"""Generate an auditable conditional-return scenario, not a price prediction.

The module uses only returns that occurred *before* the decision being
described.  Its output is intentionally called a scenario range: it is a
historical distribution conditional on the rule, never a promised future
return or a target price.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def _percentile(series: pd.Series, q: float) -> float | None:
    clean = series.dropna()
    return None if clean.empty else float(clean.quantile(q))


def build_conditional_scenarios(holdings: pd.DataFrame, decision_year: int | None = None) -> dict:
    """Summarise only historical outcomes available before a selected decision."""
    rows = holdings.copy()
    rows = rows[(rows.ticker != "TITULO_CDI") & rows.eligible_at_decision.astype(bool)].copy()
    if rows.empty:
        raise ValueError("No eligible equity holdings are available for scenario construction.")
    latest_year = int(rows.decision_year.max()) if decision_year is None else int(decision_year)
    selected = rows[rows.decision_year == latest_year].copy()
    if selected.empty:
        raise ValueError(f"No eligible equity holdings exist for decision year {latest_year}.")
    prior = rows[rows.decision_year < latest_year].copy()
    assets: list[dict] = []
    for item in selected.sort_values("weight", ascending=False).itertuples():
        outcomes = prior.loc[prior.ticker == item.ticker, "realised_next_year_return"]
        assets.append({
            "ticker": item.ticker.replace(".SA", ""),
            "weight": float(item.weight),
            "historical_observations": int(outcomes.notna().sum()),
            "historical_median_return": _percentile(outcomes, .50),
            "historical_downside_p20": _percentile(outcomes, .20),
            "historical_upside_p80": _percentile(outcomes, .80),
            "why": "Selecionado pelo score qualidade + valuation + momento disponível na data anual de decisão.",
        })
    selected_tickers = selected.ticker.tolist()
    # Assess the *selection rule* on prior annual decisions. Matching the
    # latest tickers would instead leave only a handful of observations and
    # smuggle survivorship into the portfolio range.
    historical_portfolio = prior.pivot_table(index="decision_year", columns="ticker",
                                              values="realised_next_year_return", aggfunc="first")
    historical_weights = prior.pivot_table(index="decision_year", columns="ticker", values="weight", aggfunc="first")
    aligned = historical_portfolio.reindex_like(historical_weights)
    portfolio_outcomes = aligned.mul(historical_weights, axis=1).sum(axis=1)
    return {
        "decision_year": latest_year,
        "decision_date": str(selected.decision_date.iloc[0]),
        "method": "conditional_historical_distribution",
        "label": "Faixa histórica condicional — não é previsão ou meta de rentabilidade",
        "assets": assets,
        "portfolio": {
            "historical_observations": int(portfolio_outcomes.size),
            "historical_median_return": _percentile(portfolio_outcomes, .50),
            "historical_downside_p20": _percentile(portfolio_outcomes, .20),
            "historical_upside_p80": _percentile(portfolio_outcomes, .80),
        },
        "limitations": [
            "A faixa resume retornos passados condicionais aos ativos e à regra; não estima preço-alvo.",
            "A decisão mais recente do painel é histórica. Uma proposta atual exige fundamentos CVM e snapshot de mercado atuais.",
            "Poucas observações e mudanças de regime podem tornar a faixa inadequada para o futuro.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a transparent historical scenario range for a Benevente decision.")
    parser.add_argument("--holdings", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--decision-year", type=int)
    args = parser.parse_args()
    result = build_conditional_scenarios(pd.read_csv(args.holdings), args.decision_year)
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote historical conditional scenario for {result['decision_year']} to {args.output}")


if __name__ == "__main__":
    main()
