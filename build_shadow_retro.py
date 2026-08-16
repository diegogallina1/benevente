"""Create a reproducible retrospective shadow ledger for the frozen candidate.

Every January is processed independently from the data available before that
date.  The output records the complete target book, turnover, cost, realised
return, CDI and an unconstrained long-only MVO from the exact same observable
universe.  It is a process rehearsal, not a claim that the past was traded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd

from research_unrestricted_signal_grid import COST, LOOKBACK, make_weights, market_sessions
from total_return_adapter import file_sha256, load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "shadow_retro_momentum_2015_2025"


def unrestricted_mvo(history: pd.DataFrame, gamma: float = 10.0) -> pd.Series:
    returns = history.pct_change().dropna()
    if returns.shape[1] == 1:
        return pd.Series(1.0, index=returns.columns)
    mean = returns.mean().to_numpy() * 252
    covariance = returns.cov().to_numpy() * 252 + np.eye(returns.shape[1]) * 1e-5
    weights = cp.Variable(returns.shape[1])
    problem = cp.Problem(cp.Maximize(mean @ weights - gamma / 2 * cp.quad_form(weights, cp.psd_wrap(covariance))),
                         [cp.sum(weights) == 1, weights >= 0])
    problem.solve(solver=cp.CLARABEL)
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE} or weights.value is None:
        raise RuntimeError(f"MVO did not solve: {problem.status}")
    value = np.maximum(weights.value, 0)
    return pd.Series(value / value.sum(), index=returns.columns)


def annual_cagr(values: pd.Series) -> float:
    return float((1 + values).prod()) ** (1 / len(values)) - 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    price_path = ROOT / "data" / "prices_yahoo_adjusted_total_return_2013_2025.csv"
    manifest_path = ROOT / "data" / "yahoo_adjusted_total_return_2013_2025_manifest.json"
    loaded, manifest = load_total_return_export(price_path, manifest_path)
    prices = loaded.set_index("date").sort_index()
    assets = prices.columns.drop("TITULO_CDI")
    previous_candidate, previous_mvo = pd.Series(dtype=float), pd.Series(dtype=float)
    annual_rows, weight_rows = [], []
    for year in range(2015, 2026):
        decision_days = prices.index[prices.index.year == year]
        if decision_days.empty:
            continue
        decision = decision_days[0]
        following = prices.index[prices.index.year == year + 1]
        holding_end = following[0] if not following.empty else prices.index[-1] + pd.Timedelta(days=1)
        history = market_sessions(prices.loc[prices.index < decision, assets])
        if len(history) < LOOKBACK + 1:
            continue
        history = history.tail(LOOKBACK + 1)
        eligible = history.columns[history.notna().all()].tolist()
        history = history.loc[:, eligible]
        candidate = make_weights(history, "momentum", 252, 2.0, 1.0)
        mvo = unrestricted_mvo(history)
        realised = prices.loc[(prices.index >= decision) & (prices.index < holding_end), eligible].ffill()
        returns = realised.pct_change().dropna(how="all").fillna(0.0)
        candidate_gross = float((1 + returns @ candidate).prod() - 1)
        mvo_gross = float((1 + returns @ mvo).prod() - 1)
        candidate_turnover = float((candidate - previous_candidate.reindex(candidate.index, fill_value=0.0)).abs().sum())
        mvo_turnover = float((mvo - previous_mvo.reindex(mvo.index, fill_value=0.0)).abs().sum())
        cdi = prices.loc[(prices.index >= decision) & (prices.index < holding_end), "TITULO_CDI"]
        candidate_net = candidate_gross - COST * candidate_turnover
        mvo_net = mvo_gross - COST * mvo_turnover
        cdi_return = float(cdi.iloc[-1] / cdi.iloc[0] - 1)
        annual_rows.append({
            "decision_year": year, "decision_date": decision.date().isoformat(), "holding_end_exclusive": holding_end.date().isoformat(),
            "eligible_instruments": len(eligible), "candidate_gross_return": candidate_gross,
            "candidate_turnover": candidate_turnover, "candidate_cost_rate": COST * candidate_turnover,
            "candidate_net_return": candidate_net, "mvo_gross_return": mvo_gross,
            "mvo_turnover": mvo_turnover, "mvo_cost_rate": COST * mvo_turnover, "mvo_net_return": mvo_net,
            "cdi_return": cdi_return, "beats_cdi": candidate_net > cdi_return, "beats_mvo": candidate_net > mvo_net,
            "beats_both": candidate_net > cdi_return and candidate_net > mvo_net,
        })
        weight_rows.extend({"decision_year": year, "strategy": "momentum_candidate", "ticker": ticker, "weight": float(weight)} for ticker, weight in candidate.items())
        weight_rows.extend({"decision_year": year, "strategy": "mvo_same_universe", "ticker": ticker, "weight": float(weight)} for ticker, weight in mvo.items())
        growth = (1 + returns).prod()
        previous_candidate = candidate * growth; previous_candidate /= previous_candidate.sum()
        previous_mvo = mvo * growth; previous_mvo /= previous_mvo.sum()
    annual = pd.DataFrame(annual_rows)
    weights = pd.DataFrame(weight_rows)
    annual.to_csv(OUT / "annual_ledger.csv", index=False)
    weights.to_csv(OUT / "target_weights.csv", index=False)
    payload = {
        "strategy": "Momentum Anual Diversificado Ajustado por Volatilidade",
        "status": "retrospective_shadow_process_rehearsal",
        "decision_rule": "At January t, rank 12-month returns and weight every eligible instrument by rank² / 12-month volatility.",
        "cost_model": {"rate_per_unit_turnover": COST, "description": "0.10% transaction cost + 0.05% slippage per unit of turnover"},
        "source_manifest": manifest_path.name, "source_hash": file_sha256(price_path),
        "summary": {
            "years": int(len(annual)), "candidate_cagr": annual_cagr(annual.candidate_net_return),
            "mvo_cagr": annual_cagr(annual.mvo_net_return), "cdi_cagr": annual_cagr(annual.cdi_return),
            "years_beating_cdi": int(annual.beats_cdi.sum()), "years_beating_mvo": int(annual.beats_mvo.sum()),
            "years_beating_both": int(annual.beats_both.sum()),
            "worst_candidate_year": float(annual.candidate_net_return.min()),
        },
        "limitations": [
            "Public adjusted-price research data; reconcile dividends, JCP, delistings and corporate actions before live use.",
            "MVO is a same-universe unconstrained long-only comparator, not an investable recommendation.",
            "The process is retrospective and does not establish prospective performance.",
        ],
    }
    (OUT / "shadow_manifest.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
