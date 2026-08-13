"""Deterministic, auditable portfolio-proposal service used by the local UI.

This module intentionally does not make investment claims or call an LLM.  It
turns dated input data plus an investor policy into a constrained proposal and
an audit bundle.  Any future LLM layer may explain the result, never select
assets or set weights.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

import numpy as np
import pandas as pd

from config import SystemConfig
from data_loader import PointInTimeDataLoader
from fundamentals import FundamentalSnapshot
from horizon import estimation_window_days
from portfolio_recommendation import PortfolioProposal, ValuePortfolioPlanner
from production_policy import ProductionPolicy


DEMO_SOURCE = "DEMONSTRACAO_SINTETICA — nao usar para investir"


def demo_snapshots(decision_date: pd.Timestamp) -> list[FundamentalSnapshot]:
    """Stable fictitious observations that exercise the screen in the UI."""
    available = (decision_date - pd.Timedelta(days=30)).to_pydatetime()
    as_of = (decision_date - pd.Timedelta(days=90)).to_pydatetime()
    rows = [
        ("PETR4.SA", "Energy", False, 10.0, 1.1, .10, .18, 1.1, 6.0, .23, 8e10),
        ("VALE3.SA", "Materials", False, 8.0, 1.3, .08, .15, 0.9, 7.0, .28, 7e10),
        ("ITUB4.SA", "Financials", True, 9.0, 1.4, None, .18, None, None, .30, 9e10),
        ("BBDC4.SA", "Financials", True, 8.5, 1.0, None, .14, None, None, .27, 5e10),
        ("BBAS3.SA", "Financials", True, 5.5, .8, None, .19, None, None, .31, 4e10),
        ("ABEV3.SA", "Staples", False, 16.0, 3.2, .04, .12, 0.4, 14.0, .25, 3e10),
        # Intentionally ineligible: the UI must visibly show rejected assets.
        ("RENT3.SA", "Consumer", False, 22.0, 4.0, .01, .10, 4.5, 1.5, .15, 2e10),
        ("WEGE3.SA", "Industrials", False, 30.0, 8.0, .03, .20, .2, 30.0, .22, 2e10),
    ]
    result = []
    for ticker, sector, financial, pe, pb, fcf, roe, debt, cover, margin, adv in rows:
        result.append(FundamentalSnapshot(
            ticker=ticker, as_of_date=as_of, available_date=available, sector=sector,
            is_financial=financial, market_cap_brl=20_000_000_000,
            price_to_earnings=pe, price_to_book=pb, ev_to_ebit=pe * .8,
            free_cash_flow_yield=fcf, roe=roe, roic=None if financial else roe,
            debt_to_ebitda=debt, interest_coverage=cover,
            operating_margin=margin, revenue_growth_3y=.08,
            average_daily_value_brl=adv, source=DEMO_SOURCE,
        ))
    return result


def snapshots_from_frame(frame: pd.DataFrame) -> list[FundamentalSnapshot]:
    """Validate uploaded point-in-time records without silently filling gaps."""
    records = frame.replace({np.nan: None}).to_dict(orient="records")
    return [FundamentalSnapshot.model_validate(record) for record in records]


def returns_from_price_frame(prices: pd.DataFrame, decision_date: pd.Timestamp, horizon_years: int) -> pd.DataFrame:
    required = estimation_window_days(horizon_years)
    frame = prices.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.set_index("date")
    frame.index = pd.to_datetime(frame.index)
    frame = frame.loc[frame.index <= decision_date].sort_index()
    if "TITULO_CDI" not in frame.columns:
        raise ValueError("O historico precisa conter a coluna TITULO_CDI.")
    frame = frame.apply(pd.to_numeric, errors="coerce").dropna(how="any")
    if len(frame) < required + 1:
        raise ValueError(f"O horizonte de {horizon_years} ano(s) exige pelo menos {required + 1} precos completos ate a data de decisao.")
    return frame.pct_change().dropna().iloc[-required:]


def build_proposal(policy: ProductionPolicy, decision_date: pd.Timestamp, prices: pd.DataFrame,
                   snapshots: list[FundamentalSnapshot]) -> tuple[PortfolioProposal, dict[str, float]]:
    returns = returns_from_price_frame(prices, decision_date, policy.horizon_years)
    config = replace(
        SystemConfig(), initial_portfolio_value_brl=policy.portfolio_value_brl,
        max_asset_weight=policy.maximum_asset_weight,
    )
    proposal = ValuePortfolioPlanner(config).propose(
        returns, snapshots, decision_date, horizon_years=policy.horizon_years,
        maximum_equity_weight=policy.maximum_equity_weight,
        maximum_asset_weight=policy.maximum_asset_weight,
    )
    realized = returns.reindex(columns=proposal.weights.index) @ proposal.weights
    annual_return = (1 + realized).prod() ** (252 / len(realized)) - 1
    annual_volatility = realized.std(ddof=1) * np.sqrt(252)
    sharpe = (annual_return - config.risk_free_rate_annual) / annual_volatility if annual_volatility else np.nan
    cdi = returns["TITULO_CDI"]
    cdi_return = (1 + cdi).prod() ** (252 / len(cdi)) - 1
    return proposal, {
        "model_historical_annual_return": float(annual_return),
        "model_historical_annual_volatility": float(annual_volatility),
        "model_historical_sharpe": float(sharpe),
        "cdi_historical_annual_return": float(cdi_return),
        "estimated_rebalance_cost_brl": float(proposal.estimated_rebalance_cost_brl),
        "equity_weight": float(proposal.weights.drop(labels="TITULO_CDI", errors="ignore").sum()),
    }


def candidate_memo(proposal: PortfolioProposal) -> pd.DataFrame:
    """Create a review sheet that explains every inclusion and exclusion.

    This is deliberately a factual eligibility memo, not a buy list.  It lets a
    reviewer see the same constraints that were used by the optimizer and the
    next checks required before any manual broker action.
    """
    screen = proposal.screen.copy().set_index("ticker", drop=False)
    weight_by_ticker = proposal.weights.to_dict()
    rows: list[dict[str, object]] = []
    for ticker, item in screen.iterrows():
        eligible = bool(item["eligible"])
        reasons = str(item.get("rejection_reasons", "")).strip(",")
        is_financial = bool(item.get("is_financial", False))
        if eligible:
            if is_financial:
                why = (
                    f"Aprovado no filtro para instituições financeiras: ROE {item.get('roe', float('nan')):.1%} "
                    f"e P/B {item.get('price_to_book', float('nan')):.2f} dentro das regras da política."
                )
            else:
                why = (
                    f"Aprovado no filtro valor-qualidade: FCF yield {item.get('free_cash_flow_yield', float('nan')):.1%}, "
                    f"ROIC {item.get('roic', float('nan')):.1%}, dívida/EBITDA {item.get('debt_to_ebitda', float('nan')):.2f} "
                    "e cobertura de juros atendem aos limites."
                )
            action = "Revisar fatos, liquidez, preço e risco antes de qualquer ordem manual."
        else:
            why = f"Bloqueado pela regra determinística: {reasons or 'dados insuficientes'} ."
            action = "Não incluir; atualizar o snapshot somente quando houver dado atribuível e disponível na data."
        rows.append({
            "ticker": ticker,
            "status": "Elegível para revisão" if eligible else "Bloqueado",
            "target_weight": float(weight_by_ticker.get(ticker, 0.0)),
            "why": why,
            "how": action,
            "next_review": f"Até {proposal.decision_date.date()} + política de revisão; revalidar antes de implementar.",
            "source": item.get("source", ""),
        })
    cdi_weight = float(weight_by_ticker.get("TITULO_CDI", 0.0))
    if cdi_weight > 0:
        rows.append({
            "ticker": "TITULO_CDI",
            "status": "Componente defensivo",
            "target_weight": cdi_weight,
            "why": "Reserva residual em índice/veículo de CDI; não representa a compra automática de um título específico.",
            "how": "Escolher manualmente um produto de renda fixa compatível com liquidez, tributação, risco de crédito e política.",
            "next_review": "Verificar remuneração, vencimento, emissor e condições do produto antes da aplicação.",
            "source": "Índice CDI arquivado na série de preços.",
        })
    return pd.DataFrame(rows).sort_values(["status", "target_weight"], ascending=[True, False]).reset_index(drop=True)


def write_audit_bundle(output: Path, policy: ProductionPolicy, proposal: PortfolioProposal,
                       metrics: dict[str, float], prices: pd.DataFrame, data_mode: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    proposal.weights.rename("weight").rename_axis("ticker").reset_index().to_csv(output / "target_weights.csv", index=False)
    proposal.screen.to_csv(output / "eligibility_screen.csv", index=False)
    candidate_memo(proposal).to_csv(output / "candidate_memo.csv", index=False)
    policy.model_dump_json(indent=2)
    (output / "policy.json").write_text(policy.model_dump_json(indent=2), encoding="utf-8")
    prices.to_csv(output / "price_history_used.csv", index_label="date")
    (output / "summary.json").write_text(json.dumps({
        "decision_date": str(proposal.decision_date.date()), "horizon_years": proposal.horizon_years,
        "data_mode": data_mode, "metrics": metrics,
        "required_human_approval": proposal.required_human_approval,
        "method": "Deterministic value-quality eligibility plus constrained mean-variance optimization.",
    }, indent=2), encoding="utf-8")
