"""Pre-registered gates for a healthy model-selection experiment.

The gate deliberately rejects the instruction "find parameters that beat this
past period".  A configuration is eligible for a frozen holdout only when it
passes minimum sample, net-of-CDI, drawdown and turnover conditions *inside the
training segment*.  Passing this gate is not a forecast and does not establish
alpha; it merely prevents post-hoc cherry-picking from being treated as model
validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SelectionGate:
    min_periods: int = 24
    min_excess_sharpe: float = 0.0
    max_drawdown: float = -0.35
    max_average_turnover: float = 0.50


@dataclass(frozen=True)
class CommercialReadinessGate:
    """Minimum evidence before an alpha claim can be shown commercially.

    The rule does not promise a future return. It simply prevents a strategy
    from being called production-ready when the frozen holdout did not beat
    both pre-declared baselines after estimated trading costs.
    """
    min_periods: int = 24
    min_excess_sharpe_cdi: float = 0.0
    max_drawdown: float = -0.35


@dataclass(frozen=True)
class AnnualHoldoutGate:
    """Pre-declared criteria for an annual, never-retuned holdout."""
    min_training_years: int = 5
    min_holdout_years: int = 3
    min_excess_sharpe_cdi: float = 0.0
    max_drawdown: float = -0.35


def commercial_readiness(results: pd.DataFrame, cdi: pd.DataFrame, mvo: pd.DataFrame,
                         gate: CommercialReadinessGate = CommercialReadinessGate()) -> tuple[bool, dict[str, float | str]]:
    """Assess a frozen holdout against CDI and classic MVO, net of modelled costs."""
    result = results.set_index("date")
    cdi_returns = cdi.set_index("date").net_return.reindex(result.index)
    mvo_returns = mvo.set_index("date").net_return.reindex(result.index)
    aligned = pd.concat([result.net_return, cdi_returns, mvo_returns], axis=1).dropna()
    aligned.columns = ["benevente", "cdi", "mvo"]
    reasons: list[str] = []
    if len(aligned) < gate.min_periods:
        reasons.append("insufficient_holdout_periods")
    wealth = (1 + aligned).cumprod()
    cumulative_vs_cdi = float(wealth.benevente.iloc[-1] / wealth.cdi.iloc[-1] - 1) if not wealth.empty else float("nan")
    cumulative_vs_mvo = float(wealth.benevente.iloc[-1] / wealth.mvo.iloc[-1] - 1) if not wealth.empty else float("nan")
    excess_cdi = float((aligned.benevente - aligned.cdi).mean() / ((aligned.benevente - aligned.cdi).std(ddof=1) + 1e-12) * np.sqrt(12)) if len(aligned) > 1 else float("nan")
    drawdown = float((wealth.benevente / wealth.benevente.cummax() - 1).min()) if not wealth.empty else float("nan")
    if not np.isfinite(cumulative_vs_cdi) or cumulative_vs_cdi <= 0:
        reasons.append("did_not_beat_cdi_net_of_costs")
    if not np.isfinite(cumulative_vs_mvo) or cumulative_vs_mvo <= 0:
        reasons.append("did_not_beat_classic_mvo_net_of_costs")
    if not np.isfinite(excess_cdi) or excess_cdi < gate.min_excess_sharpe_cdi:
        reasons.append("nonpositive_holdout_excess_sharpe_cdi")
    if not np.isfinite(drawdown) or drawdown < gate.max_drawdown:
        reasons.append("holdout_drawdown_limit")
    return not reasons, {
        "holdout_periods": float(len(aligned)),
        "cumulative_excess_vs_cdi": cumulative_vs_cdi,
        "cumulative_excess_vs_mvo": cumulative_vs_mvo,
        "holdout_sharpe_excess_cdi": excess_cdi,
        "holdout_max_drawdown": drawdown,
        "commercial_readiness": "approved" if not reasons else "research_only",
        "commercial_readiness_reasons": ",".join(reasons),
    }


def excess_sharpe(results: pd.DataFrame, cdi: pd.DataFrame) -> float:
    excess = results.set_index("date").net_return - cdi.set_index("date").net_return
    if len(excess) < 2:
        return float("nan")
    return float(excess.mean() / (excess.std(ddof=1) + 1e-12) * np.sqrt(12))


def passes_selection_gate(results: pd.DataFrame, cdi: pd.DataFrame, gate: SelectionGate = SelectionGate()) -> tuple[bool, dict[str, float | str]]:
    """Return a traceable accept/reject decision based only on training rows."""
    sharpe = excess_sharpe(results, cdi)
    wealth = results["wealth"]
    drawdown = float((wealth / wealth.cummax() - 1).min()) if not wealth.empty else float("nan")
    turnover = float(results["turnover"].mean()) if "turnover" in results and not results.empty else float("nan")
    reasons: list[str] = []
    if len(results) < gate.min_periods:
        reasons.append("insufficient_training_periods")
    if not np.isfinite(sharpe) or sharpe < gate.min_excess_sharpe:
        reasons.append("nonpositive_excess_sharpe")
    if not np.isfinite(drawdown) or drawdown < gate.max_drawdown:
        reasons.append("drawdown_limit")
    if not np.isfinite(turnover) or turnover > gate.max_average_turnover:
        reasons.append("turnover_limit")
    return not reasons, {
        "training_periods": float(len(results)),
        "training_sharpe_excess_cdi": sharpe,
        "training_max_drawdown": drawdown,
        "training_average_turnover": turnover,
        "selection_status": "accepted" if not reasons else "rejected",
        "selection_reasons": ",".join(reasons),
    }


def _annual_metrics(returns: pd.Series) -> dict[str, float]:
    """Compute annual-period metrics without pretending annual rows are monthly."""
    returns = returns.dropna()
    if returns.empty:
        return {"cumulative_return": float("nan"), "cagr": float("nan"), "max_drawdown": float("nan")}
    wealth = (1 + returns).cumprod()
    return {
        "cumulative_return": float(wealth.iloc[-1] - 1),
        "cagr": float(wealth.iloc[-1] ** (1 / len(wealth)) - 1),
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
    }


def annual_holdout_readiness(annual_results: pd.DataFrame, split_year: int,
                             input_performance_permitted: bool,
                             gate: AnnualHoldoutGate = AnnualHoldoutGate()) -> tuple[bool, dict[str, float | str]]:
    """Validate a frozen annual holdout against CDI and eligible-universe MVO.

    ``split_year`` is exclusive: decisions before it are training history;
    decisions from it onward are the untouched holdout.  This function does
    not select a factor or modify a portfolio.  It only evaluates output from
    a previously frozen annual walk-forward run.
    """
    required = {"decision_year", "net_return", "cdi_net_return", "mvo_eligible_net_return"}
    if missing := required - set(annual_results.columns):
        raise ValueError(f"annual results missing columns: {sorted(missing)}")
    frame = annual_results.copy()
    frame["decision_year"] = pd.to_numeric(frame.decision_year, errors="raise").astype(int)
    if frame.decision_year.duplicated().any():
        raise ValueError("annual results must contain at most one row per decision year")
    train = frame[frame.decision_year < split_year].sort_values("decision_year")
    holdout = frame[frame.decision_year >= split_year].sort_values("decision_year")
    reasons: list[str] = []
    if not input_performance_permitted:
        reasons.append("total_return_input_not_verified")
    if len(train) < gate.min_training_years:
        reasons.append("insufficient_training_years")
    if len(holdout) < gate.min_holdout_years:
        reasons.append("insufficient_holdout_years")
    aligned = holdout[["net_return", "cdi_net_return", "mvo_eligible_net_return"]].dropna()
    if len(aligned) < gate.min_holdout_years:
        reasons.append("incomplete_holdout_benchmarks")
    metrics = _annual_metrics(aligned.net_return)
    cdi_metrics = _annual_metrics(aligned.cdi_net_return)
    mvo_metrics = _annual_metrics(aligned.mvo_eligible_net_return)
    excess = aligned.net_return - aligned.cdi_net_return
    excess_std = float(excess.std(ddof=1)) if len(excess) > 1 else float("nan")
    # A constant synthetic excess has no empirical risk estimate. Treat its
    # information ratio as undefined rather than manufacturing a huge value
    # by dividing by a tiny numerical epsilon.
    excess_sharpe = (float(excess.mean() / excess_std)
                     if np.isfinite(excess_std) and excess_std > 1e-12 else float("nan"))
    relative_mvo = ((1 + aligned.net_return).cumprod() /
                    (1 + aligned.mvo_eligible_net_return).cumprod())
    excess_mvo = float(relative_mvo.iloc[-1] - 1) if not relative_mvo.empty else float("nan")
    excess_cdi = float((1 + aligned.net_return).cumprod().iloc[-1] /
                       (1 + aligned.cdi_net_return).cumprod().iloc[-1] - 1) if not aligned.empty else float("nan")
    if not np.isfinite(excess_cdi) or excess_cdi <= 0:
        reasons.append("did_not_beat_cdi_in_frozen_holdout")
    if not np.isfinite(excess_mvo) or excess_mvo <= 0:
        reasons.append("did_not_beat_mvo_in_frozen_holdout")
    if not np.isfinite(excess_sharpe) or excess_sharpe < gate.min_excess_sharpe_cdi:
        reasons.append("nonpositive_annual_excess_sharpe_cdi")
    if not np.isfinite(metrics["max_drawdown"]) or metrics["max_drawdown"] < gate.max_drawdown:
        reasons.append("annual_holdout_drawdown_limit")
    return not reasons, {
        "training_years": float(len(train)),
        "holdout_years": float(len(holdout)),
        "holdout_start_year": float(split_year),
        "holdout_cumulative_return": metrics["cumulative_return"],
        "holdout_cagr": metrics["cagr"],
        "holdout_cdi_cagr": cdi_metrics["cagr"],
        "holdout_mvo_cagr": mvo_metrics["cagr"],
        "holdout_excess_vs_cdi": excess_cdi,
        "holdout_excess_vs_mvo": excess_mvo,
        "holdout_excess_sharpe_cdi": excess_sharpe,
        "holdout_max_drawdown": metrics["max_drawdown"],
        "annual_validation_status": "approved" if not reasons else "research_only",
        "annual_validation_reasons": ",".join(reasons),
    }
