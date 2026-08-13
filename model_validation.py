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
