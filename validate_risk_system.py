"""Validate the profile risk layer without treating retrospective results as proof."""
from __future__ import annotations

from pathlib import Path
import argparse
import json

import numpy as np
import pandas as pd

from portfolio_risk import risk_profile_spec
from total_return_adapter import institutional_performance_verified


ROOT = Path(__file__).resolve().parent
BOOTSTRAP_SEED = 20_260_820
BOOTSTRAP_SAMPLES = 100_000
BLOCK_MONTE_CARLO_SAMPLES = 5_000
BLOCK_LENGTH_SESSIONS = 21


def cagr(returns: np.ndarray) -> np.ndarray:
    values = np.asarray(returns, dtype=float)
    return np.prod(1 + values, axis=-1) ** (1 / values.shape[-1]) - 1


def max_drawdown_from_daily(path: Path, column: str = "strategy") -> float:
    daily = pd.read_csv(path)
    level = pd.to_numeric(daily[column], errors="coerce").dropna()
    return float((level / level.cummax() - 1).min())


def annual_metrics(frame: pd.DataFrame, return_column: str) -> dict:
    returns = pd.to_numeric(frame[return_column], errors="coerce").dropna()
    wealth = (1 + returns).cumprod()
    return {
        "years": int(len(returns)),
        "cumulative_return": float(wealth.iloc[-1] - 1),
        "cagr": float(wealth.iloc[-1] ** (1 / len(returns)) - 1),
        "annual_volatility": float(returns.std(ddof=1)),
        "worst_year": float(returns.min()),
    }


def bootstrap_excess(frame: pd.DataFrame, comparator: str) -> dict:
    paired = frame[["net_return_after_tax", comparator]].dropna().to_numpy(dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, len(paired), size=(BOOTSTRAP_SAMPLES, len(paired)))
    strategy = cagr(paired[:, 0][indices])
    reference = cagr(paired[:, 1][indices])
    excess = strategy - reference
    return {
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "probability_positive_excess": float(np.mean(excess > 0)),
        "p2_5": float(np.quantile(excess, .025)),
        "median": float(np.quantile(excess, .5)),
        "p97_5": float(np.quantile(excess, .975)),
    }


def cost_stress(frame: pd.DataFrame) -> list[dict]:
    rows = []
    for multiplier in (1, 2, 5):
        stressed = frame.net_return - (multiplier - 1) * frame.estimated_cost_rate
        rows.append({"execution_cost_multiplier": multiplier, "cagr": float(cagr(stressed.to_numpy()))})
    return rows


def single_year_equity_shock(frame: pd.DataFrame) -> list[dict]:
    """Worst CAGR after one extra loss applied to the equity budget.

    Every possible historical decision year is shocked and the least favorable
    resulting CAGR is retained.  This is a sensitivity exercise, not a forecast
    of the probability of a crisis.
    """
    rows = []
    base = frame.net_return.to_numpy(dtype=float)
    equity = frame.target_equity_weight.to_numpy(dtype=float)
    for shock in (-.10, -.20, -.35):
        outcomes = []
        years = []
        for index, year in enumerate(frame.decision_year):
            stressed = base.copy()
            stressed[index] = max(-.999, stressed[index] + shock * equity[index])
            outcomes.append(float(cagr(stressed)))
            years.append(int(year))
        worst = int(np.argmin(outcomes))
        rows.append({
            "additional_equity_shock": shock,
            "worst_shocked_year": years[worst],
            "worst_full_period_cagr": outcomes[worst],
        })
    return rows


def prolonged_bear_scenario(frame: pd.DataFrame) -> dict:
    """Three synthetic years with equities at -15% and observed median CDI."""
    equity_weight = float(frame.target_equity_weight.median())
    cdi = float(frame.cdi_net_return.median())
    cost = float(frame.estimated_cost_rate.median())
    annual = equity_weight * -.15 + (1 - equity_weight) * cdi - cost
    return {
        "years": 3,
        "equity_return_each_year": -.15,
        "equity_weight": equity_weight,
        "cash_return_each_year": cdi,
        "annual_portfolio_return": annual,
        "cumulative_return": float((1 + annual) ** 3 - 1),
        "interpretation": "deterministic sensitivity; no probability is assigned",
    }


def block_monte_carlo(path: Path, seed: int, samples: int = BLOCK_MONTE_CARLO_SAMPLES) -> dict:
    """Resample paired daily paths in 21-session circular blocks.

    Blocks preserve short serial dependence and the contemporaneous relation
    between the protected book and CDI.  The exercise measures sensitivity to
    reordered observed regimes; it does not manufacture a prospective sample.
    """
    daily = pd.read_csv(path)
    pair = daily[["protected_return", "cdi_daily_return"]].apply(pd.to_numeric, errors="coerce").dropna().to_numpy()
    if len(pair) < BLOCK_LENGTH_SESSIONS:
        raise ValueError("Daily overlay is too short for the declared block bootstrap")
    rng = np.random.default_rng(seed)
    blocks = int(np.ceil(len(pair) / BLOCK_LENGTH_SESSIONS))
    offsets = np.arange(BLOCK_LENGTH_SESSIONS)
    strategy_cagr: list[np.ndarray] = []
    cdi_cagr: list[np.ndarray] = []
    drawdowns: list[np.ndarray] = []
    for start in range(0, samples, 250):
        batch = min(250, samples - start)
        origins = rng.integers(0, len(pair), size=(batch, blocks, 1))
        indices = (origins + offsets.reshape(1, 1, -1)) % len(pair)
        indices = indices.reshape(batch, -1)[:, :len(pair)]
        strategy = pair[:, 0][indices]
        cdi = pair[:, 1][indices]
        strategy_wealth = np.cumprod(1 + strategy, axis=1)
        cdi_wealth = np.cumprod(1 + cdi, axis=1)
        strategy_cagr.append(strategy_wealth[:, -1] ** (252 / len(pair)) - 1)
        cdi_cagr.append(cdi_wealth[:, -1] ** (252 / len(pair)) - 1)
        drawdowns.append(np.min(strategy_wealth / np.maximum.accumulate(strategy_wealth, axis=1) - 1, axis=1))
    strategy_values = np.concatenate(strategy_cagr)
    cdi_values = np.concatenate(cdi_cagr)
    drawdown_values = np.concatenate(drawdowns)
    quantiles = lambda values: {
        "p2_5": float(np.quantile(values, .025)),
        "median": float(np.quantile(values, .5)),
        "p97_5": float(np.quantile(values, .975)),
    }
    return {
        "samples": samples,
        "seed": seed,
        "block_length_sessions": BLOCK_LENGTH_SESSIONS,
        "strategy_cagr": quantiles(strategy_values),
        "maximum_drawdown": quantiles(drawdown_values),
        "probability_cagr_above_paired_cdi": float(np.mean(strategy_values > cdi_values)),
        "interpretation": "retrospective circular block resampling; not prospective evidence",
    }


def validate_profile(profile: str, root: Path, baseline_root: Path, source_verified: bool) -> tuple[dict, pd.DataFrame]:
    frame = pd.read_csv(root / "annual_results.csv")
    baseline = pd.read_csv(baseline_root / "annual_results.csv")
    spec = risk_profile_spec(profile)
    holdout = frame[frame.decision_year >= 2019].copy()
    overlay_path = root.parent / f"{profile}_intrayear" / "summary.json"
    intrayear = json.loads(overlay_path.read_text(encoding="utf-8")) if overlay_path.exists() else None
    overlay_daily = root.parent / f"{profile}_intrayear" / "daily_overlay.csv"
    result = {
        "profile": profile,
        "method_status": "retrospective_policy_experiment_not_prospective_validation",
        "full_period": annual_metrics(frame, "net_return"),
        "full_period_after_tax": annual_metrics(frame, "net_return_after_tax"),
        "holdout_2019_2025_after_tax": annual_metrics(holdout, "net_return_after_tax"),
        "comparators_after_tax": {
            "CDI": annual_metrics(frame, "cdi_net_return_after_tax"),
            "MVO": annual_metrics(frame, "mvo_net_return_after_tax"),
        },
        "daily_max_drawdown": max_drawdown_from_daily(root / "daily_curve.csv"),
        "fixed_cap_baseline": {
            "cagr": annual_metrics(baseline, "net_return")["cagr"],
            "daily_max_drawdown": max_drawdown_from_daily(baseline_root / "daily_curve.csv"),
        },
        "minimum_positions_observed": int(
            pd.read_csv(root / "annual_holdings.csv")
            .query("ticker != 'TITULO_CDI'").groupby("decision_year").ticker.nunique().min()
        ),
        "bootstrap": {
            "CDI": bootstrap_excess(frame, "cdi_net_return_after_tax"),
            "MVO": bootstrap_excess(frame, "mvo_net_return_after_tax"),
        },
        "cost_stress": cost_stress(frame),
        "single_year_equity_shock": single_year_equity_shock(frame),
        "prolonged_bear": prolonged_bear_scenario(frame),
        "fixed_intrayear_overlay": intrayear,
        "block_monte_carlo": block_monte_carlo(
            overlay_daily, BOOTSTRAP_SEED + {"conservador": 1, "equilibrado": 2, "arrojado": 3}[profile]
        ) if overlay_daily.exists() else None,
    }
    protected_drawdown = (
        intrayear.get("full_period", {}).get("protected", {}).get("max_drawdown")
        if intrayear
        else None
    )
    result["drawdown_assessment"] = {
        "annual_selection_only": result["daily_max_drawdown"],
        "with_fixed_intrayear_overlay": protected_drawdown,
        "profile_tolerance": -spec.maximum_drawdown_tolerance,
    }
    result["gates"] = {
        "primary_total_return_verified": source_verified,
        "minimum_five_issuers": result["minimum_positions_observed"] >= 5,
        "drawdown_within_profile_tolerance": (
            protected_drawdown is not None
            and protected_drawdown >= -spec.maximum_drawdown_tolerance
        ),
        "full_period_after_tax_above_cdi": result["full_period_after_tax"]["cagr"] > result["comparators_after_tax"]["CDI"]["cagr"],
        "full_period_after_tax_above_mvo": result["full_period_after_tax"]["cagr"] > result["comparators_after_tax"]["MVO"]["cagr"],
        "prospective_observations_sufficient": False,
        "intrayear_tax_model_complete": False,
    }
    result["approval"] = "blocked" if not all(result["gates"].values()) else "eligible_for_human_review"
    annual_export = frame[[
        "decision_year", "net_return", "net_return_after_tax", "target_equity_weight",
        "risk_state_at_decision", "estimated_volatility_after_risk", "cdi_net_return",
        "cdi_net_return_after_tax", "mvo_eligible_net_return", "mvo_net_return_after_tax",
        "benchmark_IBOVESPA", "benchmark_BOVA11",
    ]].copy()
    annual_export.insert(0, "profile", profile)
    return result, annual_export


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the Benevente profile risk layer.")
    parser.add_argument("--profiles-root", default="artifacts/risk_profiles_v1")
    parser.add_argument("--source-manifest", default="data/prices_b3_total_return_full_2011_2025_manifest.json")
    parser.add_argument("--output", default="artifacts/risk_system_validation_20260820")
    args = parser.parse_args()
    root = Path(args.profiles_root)
    source_manifest = json.loads(Path(args.source_manifest).read_text(encoding="utf-8"))
    source_verified = institutional_performance_verified(source_manifest)
    results = []
    annual = []
    for profile in ("conservador", "equilibrado", "arrojado"):
        result, records = validate_profile(
            profile, root / profile, root / f"{profile}_fixed_cap_baseline", source_verified
        )
        results.append(result)
        annual.append(records)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "as_of": "2026-08-20",
        "status": "retrospective_research_only",
        "source_manifest": str(args.source_manifest).replace("\\", "/"),
        "institutional_total_return_verified": source_verified,
        "profiles": results,
        "global_limitations": [
            "The risk policy was designed after the historical period was visible.",
            "The 2019-2025 slice is a frozen calculation window, not a genuinely prospective sample.",
            "The current total-return panel is not institutionally verified against complete primary event records.",
            "The fixed intrayear overlay includes turnover cost but does not yet model Brazilian tax lots and tax payments.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    pd.concat(annual, ignore_index=True).to_csv(output / "annual_profile_comparison.csv", index=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
