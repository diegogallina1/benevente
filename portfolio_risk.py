"""Pre-declared risk sizing for Benevente portfolios.

The selection engine answers *what* may be owned.  This module answers *how
much* risk the investor policy may take.  It reads trailing returns only,
enforces a real minimum number of issuers and leaves the residual in CDI.

The rules are intentionally simple enough to audit.  They are not described as
having predicted Covid-19 or any other event and a retrospective run of them is
an experiment, not prospective evidence.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskProfileSpec:
    name: str
    target_volatility: float
    maximum_equity_weight: float
    maximum_asset_weight: float
    minimum_equity_positions: int = 5
    minimum_position_weight: float = 0.02
    # Share of ``maximum_equity_weight`` the volatility target may never cut
    # below.  Zero reproduces the published behaviour, in which the target
    # alone decided the exposure and the declared cap was decorative: measured
    # over 2015-2025 the three profiles held 54%, 65% and 78% of their own caps
    # on average, so an investor who chose "arrojado" was not in the profile
    # they were sold.  The floor binds the target only; observable stress may
    # still cut below it, which is the one mechanism that did reduce drawdown.
    minimum_equity_fraction_of_cap: float = 0.0
    alert_multiplier: float = 0.70
    severe_multiplier: float = 0.40
    maximum_drawdown_tolerance: float = 0.25


PROFILE_SPECS: dict[str, RiskProfileSpec] = {
    "conservador": RiskProfileSpec(
        "conservador", target_volatility=.08, maximum_equity_weight=.35,
        maximum_asset_weight=.10, alert_multiplier=.55, severe_multiplier=.25,
        maximum_drawdown_tolerance=.15,
    ),
    "equilibrado": RiskProfileSpec(
        "equilibrado", target_volatility=.12, maximum_equity_weight=.55,
        maximum_asset_weight=.12, alert_multiplier=.70, severe_multiplier=.40,
        maximum_drawdown_tolerance=.25,
    ),
    "arrojado": RiskProfileSpec(
        "arrojado", target_volatility=.18, maximum_equity_weight=.75,
        maximum_asset_weight=.15, alert_multiplier=.85, severe_multiplier=.60,
        maximum_drawdown_tolerance=.40,
    ),
}
PROFILE_ALIASES = {
    "moderado": "equilibrado", "moderate": "equilibrado",
    "conservative": "conservador", "aggressive": "arrojado",
    # O degrau declarado em 30/08/2026 herda a camada de proteção do conservador.
    # Fica como apelido, e não como espécie nova, para deixar explícito que ele
    # não ganhou multiplicadores próprios escolhidos depois de ver resultado: a
    # regra do degrau moveu o teto de ações, e só ele.
    "ultraconservador": "conservador",
}


def resolve_profile_spec(profile: "str | RiskProfileSpec") -> RiskProfileSpec:
    """Accept a registered profile name or an explicitly declared spec."""
    return profile if isinstance(profile, RiskProfileSpec) else risk_profile_spec(profile)


def risk_profile_spec(name: str) -> RiskProfileSpec:
    canonical = PROFILE_ALIASES.get(str(name).strip().lower(), str(name).strip().lower())
    if canonical not in PROFILE_SPECS:
        raise ValueError(f"Unsupported risk profile '{name}'.")
    return PROFILE_SPECS[canonical]


def _annualised_volatility(returns: pd.DataFrame, weights: pd.Series) -> float:
    columns = [column for column in weights.index if column in returns.columns and float(weights[column]) > 0]
    if not columns:
        return 0.0
    matrix = returns[columns].dropna(how="any")
    if len(matrix) < 20:
        raise ValueError("Risk sizing requires at least 20 complete trailing sessions")
    covariance = matrix.cov().to_numpy() * 252
    # A small diagonal shrinkage makes the estimate less hostage to one noisy
    # off-diagonal covariance while preserving the observed scale of risk.
    diagonal = np.diag(np.diag(covariance))
    covariance = .80 * covariance + .20 * diagonal + np.eye(len(columns)) * 1e-10
    vector = weights.reindex(columns).to_numpy(dtype=float)
    return float(math.sqrt(max(0.0, vector @ covariance @ vector)))


def _trailing_stress(history: pd.DataFrame, equity_weights: pd.Series) -> tuple[str, float, float]:
    weights = equity_weights[equity_weights > 0]
    if weights.empty:
        return "normal", 0.0, 0.0
    normalised = weights / weights.sum()
    sleeve = history.reindex(columns=normalised.index).dropna(how="any").tail(252)
    if len(sleeve) < 20:
        return "normal", 0.0, 0.0
    portfolio_return = sleeve.mul(normalised, axis=1).sum(axis=1)
    wealth = (1 + portfolio_return).cumprod()
    drawdown = float(wealth.iloc[-1] / wealth.cummax().iloc[-1] - 1)
    recent_volatility = float(portfolio_return.tail(20).std(ddof=1) * math.sqrt(252))
    if drawdown <= -.20 or recent_volatility >= .50:
        state = "severo"
    elif drawdown <= -.10 or recent_volatility >= .30:
        state = "alerta"
    else:
        state = "normal"
    return state, drawdown, recent_volatility


def ensure_minimum_positions(
    target: pd.Series,
    ranked_eligible: list[str],
    spec: RiskProfileSpec,
) -> pd.Series:
    """Reach the issuer minimum without increasing the equity budget."""
    result = target.astype(float).copy()
    equity_names = [ticker for ticker in result.index if ticker != "TITULO_CDI"]
    equity_budget = float(result.reindex(equity_names).fillna(0.0).sum())
    held = [ticker for ticker in equity_names if float(result.get(ticker, 0.0)) > 1e-8]
    candidates = [ticker for ticker in ranked_eligible if ticker in result.index and ticker not in held]
    if len(held) < spec.minimum_equity_positions:
        needed = spec.minimum_equity_positions - len(held)
        if len(candidates) < needed:
            raise ValueError(
                f"Risk policy requires {spec.minimum_equity_positions} eligible issuers; "
                f"only {len(held) + len(candidates)} are available."
            )
        additions = candidates[:needed]
        floor = min(spec.minimum_position_weight, equity_budget / spec.minimum_equity_positions)
        required = floor * len(additions)
        existing_total = float(result.reindex(held).fillna(0.0).sum())
        if existing_total <= required:
            # Equal weights are the deterministic fallback when the optimizer
            # concentrated so much that proportional reduction is impossible.
            names = [*held, *additions]
            result.loc[equity_names] = 0.0
            result.loc[names] = equity_budget / len(names)
        else:
            result.loc[held] = result.loc[held] * ((existing_total - required) / existing_total)
            result.loc[additions] = floor
    result.loc[equity_names] = result.loc[equity_names].clip(upper=spec.maximum_asset_weight)
    # Any amount released by the cap belongs to the defensive sleeve.  Never
    # relax a risk limit merely to force the requested equity percentage.
    result["TITULO_CDI"] = 1.0 - float(result.loc[equity_names].sum())
    return result


def apply_annual_risk_policy(
    target: pd.Series,
    trailing_returns: pd.DataFrame,
    ranked_eligible: list[str],
    profile: str | RiskProfileSpec,
    decision_date: pd.Timestamp | None = None,
) -> tuple[pd.Series, dict]:
    """Apply diversification, target volatility and observable stress sizing."""
    spec = resolve_profile_spec(profile)
    history = trailing_returns.copy().sort_index()
    if decision_date is not None and isinstance(history.index, pd.DatetimeIndex):
        if len(history) and history.index.max() >= pd.Timestamp(decision_date):
            raise ValueError("Risk policy received returns on or after the decision date")
    diversified = ensure_minimum_positions(target, ranked_eligible, spec)
    equity_names = [ticker for ticker in diversified.index if ticker != "TITULO_CDI"]
    equity = diversified.reindex(equity_names).fillna(0.0)
    base_budget = min(float(equity.sum()), spec.maximum_equity_weight)
    if base_budget <= 0:
        report = {
            **asdict(spec), "base_equity_weight": 0.0, "effective_equity_weight": 0.0,
            "estimated_volatility_before": 0.0, "estimated_volatility_after": 0.0,
            "risk_state": "normal", "trailing_drawdown": 0.0, "recent_volatility": 0.0,
        }
        return diversified, report

    equity_mix = equity / float(equity.sum())
    sleeve_volatility = _annualised_volatility(history, equity_mix)
    volatility_budget = spec.maximum_equity_weight
    if sleeve_volatility > 0:
        volatility_budget = min(volatility_budget, spec.target_volatility / sleeve_volatility)
    state, trailing_drawdown, recent_volatility = _trailing_stress(history, equity_mix)
    state_multiplier = {
        "normal": 1.0,
        "alerta": spec.alert_multiplier,
        "severo": spec.severe_multiplier,
    }[state]
    # The volatility target may reduce the sleeve, but not below the share of
    # the declared cap the profile promised to keep invested.  Stress is
    # applied afterwards and is deliberately allowed to go under the floor:
    # a floor that also blocked the crisis response would remove the only
    # layer that measurably reduced drawdown.
    volatility_limited = max(min(base_budget, volatility_budget),
                             min(base_budget, spec.minimum_equity_fraction_of_cap * spec.maximum_equity_weight))
    effective_budget = volatility_limited * state_multiplier
    # Scaling is one-way: the risk layer may reduce a selected budget but may
    # not manufacture extra equity exposure to improve a historical result.
    adjusted = diversified.copy()
    adjusted.loc[equity_names] = equity_mix * effective_budget
    adjusted["TITULO_CDI"] = 1.0 - effective_budget
    estimated_before = _annualised_volatility(history, equity_mix * base_budget)
    estimated_after = _annualised_volatility(history, equity_mix * effective_budget)
    report = {
        **asdict(spec),
        "base_equity_weight": base_budget,
        "volatility_limited_equity_weight": volatility_limited,
        "exposure_floor": spec.minimum_equity_fraction_of_cap * spec.maximum_equity_weight,
        "effective_equity_weight": effective_budget,
        "estimated_volatility_before": estimated_before,
        "estimated_volatility_after": estimated_after,
        "risk_state": state,
        "trailing_drawdown": trailing_drawdown,
        "recent_volatility": recent_volatility,
    }
    return adjusted, report
