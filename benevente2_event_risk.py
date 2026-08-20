"""Compare Benevente 1 with a separately versioned intrayear risk overlay.

Benevente 1 is the published annual multifactor path. Benevente 2 keeps that
selection path and can temporarily move part of the book to CDI when market
stress observable at the previous close crosses predeclared thresholds.

The language model is not used to manufacture historical event flags. A future
news arm may supply timestamped flags, but this experiment uses only dated
Ibovespa prices so that it remains reproducible and free of look-ahead.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats


@dataclass(frozen=True)
class RiskOverlayConfig:
    alert_drawdown: float = 0.10
    severe_drawdown: float = 0.20
    alert_volatility: float = 0.30
    severe_volatility: float = 0.50
    alert_equity_cap: float = 0.55
    severe_equity_cap: float = 0.25
    recovery_days: int = 10
    cost_bps: float = 10.0
    volatility_window: int = 20
    peak_window: int = 126


CENTRAL_CONFIG = RiskOverlayConfig()


def observable_stress(market_level: pd.Series, config: RiskOverlayConfig) -> pd.DataFrame:
    """Return raw stress measured at each close and the next-session signal."""
    market_return = market_level.pct_change()
    volatility = market_return.rolling(config.volatility_window, min_periods=config.volatility_window).std() * math.sqrt(252)
    rolling_peak = market_level.rolling(config.peak_window, min_periods=config.volatility_window).max()
    drawdown = market_level / rolling_peak - 1.0
    raw = pd.Series(0, index=market_level.index, dtype=int)
    raw[(drawdown <= -config.alert_drawdown) | (volatility >= config.alert_volatility)] = 1
    raw[(drawdown <= -config.severe_drawdown) | (volatility >= config.severe_volatility)] = 2
    # A signal observed at close t may only change exposure for session t+1.
    tradable = raw.shift(1).fillna(0).astype(int)
    return pd.DataFrame({"market_drawdown": drawdown, "market_volatility": volatility,
                         "stress_at_close": raw, "tradable_stress": tradable})


def state_with_hysteresis(tradable_stress: pd.Series, recovery_days: int) -> pd.Series:
    """Enter stress immediately; recover one level after consecutive calmer days."""
    state = 0
    calmer_days = 0
    states: list[int] = []
    for raw in tradable_stress.fillna(0).astype(int):
        if raw > state:
            state = raw
            calmer_days = 0
        elif raw < state:
            calmer_days += 1
            if calmer_days >= recovery_days:
                state -= 1
                calmer_days = 0
        else:
            calmer_days = 0
        states.append(state)
    return pd.Series(states, index=tradable_stress.index, dtype=int)


def apply_overlay(frame: pd.DataFrame, target_equity: pd.Series,
                  config: RiskOverlayConfig) -> pd.DataFrame:
    """Scale Benevente 1's excess over CDI according to the risk state."""
    stress = observable_stress(frame["IBOVESPA"], config)
    state = state_with_hysteresis(stress["tradable_stress"], config.recovery_days)
    desired_equity = target_equity.astype(float).copy()
    desired_equity[state.eq(1)] = np.minimum(desired_equity[state.eq(1)], config.alert_equity_cap)
    desired_equity[state.eq(2)] = np.minimum(desired_equity[state.eq(2)], config.severe_equity_cap)
    multiplier = (desired_equity / target_equity.replace(0, np.nan)).fillna(0.0).clip(0.0, 1.0)

    benevente1_return = frame.get("benevente1_daily_return", frame["strategy"].pct_change().fillna(0.0))
    cdi_return = frame.get("cdi_daily_return", frame["cdi"].pct_change().fillna(0.0))
    overlay_reduction = target_equity - desired_equity
    overlay_turnover = overlay_reduction.diff().abs().fillna(overlay_reduction.abs())
    overlay_cost = overlay_turnover * config.cost_bps / 10_000.0
    benevente2_return = cdi_return + multiplier * (benevente1_return - cdi_return) - overlay_cost

    result = frame.copy()
    result = result.join(stress)
    result["risk_state"] = state
    result["base_equity_weight"] = target_equity
    result["benevente2_equity_weight"] = desired_equity
    result["overlay_turnover"] = overlay_turnover
    result["overlay_cost_rate"] = overlay_cost
    result["benevente1_return"] = benevente1_return
    result["benevente2_return"] = benevente2_return
    result["cdi_return"] = cdi_return
    result["benevente1"] = (1.0 + benevente1_return).cumprod()
    result["benevente2"] = (1.0 + benevente2_return).cumprod()
    result["cdi_rebased"] = (1.0 + cdi_return).cumprod()
    return result


def metrics(returns: pd.Series, cdi_return: pd.Series, dates: pd.Series) -> dict[str, float]:
    returns = returns.fillna(0.0)
    wealth = (1.0 + returns).cumprod()
    # The canonical evidence is organised in annual decision periods. Counting
    # those periods reproduces its CAGR exactly and avoids a one-day calendar
    # difference changing the headline.
    years = max(int(dates.dt.year.nunique()), 1)
    excess = returns - cdi_return.fillna(0.0)
    excess_std = float(excess.std(ddof=1))
    return {
        "cumulative_return": float(wealth.iloc[-1] - 1.0),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "annual_volatility": float(returns.std(ddof=1) * math.sqrt(252)),
        "sharpe_excess_cdi": float(excess.mean() / excess_std * math.sqrt(252)) if excess_std else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
    }


def annual_returns(result: pd.DataFrame) -> pd.DataFrame:
    columns = {
        "benevente1_return": "Benevente 1",
        "benevente2_return": "Benevente 2",
        "cdi_return": "CDI",
    }
    rows = []
    for year, group in result.groupby(result["date"].dt.year):
        row = {"year": int(year)}
        for column, label in columns.items():
            row[label] = float((1.0 + group[column]).prod() - 1.0)
        for source, label in (("mvo_daily_return", "MVO"), ("ibovespa_daily_return", "Ibovespa")):
            if source in group:
                row[label] = float((1.0 + group[source]).prod() - 1.0)
            else:
                level = "mvo" if label == "MVO" else "IBOVESPA"
                row[label] = float(group[level].iloc[-1] / group[level].iloc[0] - 1.0)
        row["days_alert"] = int(group.risk_state.eq(1).sum())
        row["days_severe"] = int(group.risk_state.eq(2).sum())
        row["overlay_turnover"] = float(group.overlay_turnover.sum())
        rows.append(row)
    return pd.DataFrame(rows)


def configuration_grid() -> list[RiskOverlayConfig]:
    configs = []
    for alert_dd, alert_vol, alert_cap, severe_cap, recovery in itertools.product(
        (0.08, 0.10, 0.12, 0.15), (0.25, 0.30, 0.35, 0.40),
        (0.50, 0.55, 0.65), (0.20, 0.25, 0.35), (5, 10, 20),
    ):
        configs.append(RiskOverlayConfig(
            alert_drawdown=alert_dd,
            severe_drawdown=alert_dd + 0.10,
            alert_volatility=alert_vol,
            severe_volatility=alert_vol + 0.20,
            alert_equity_cap=alert_cap,
            severe_equity_cap=severe_cap,
            recovery_days=recovery,
        ))
    return configs


def config_from_row(row: pd.Series) -> RiskOverlayConfig:
    values = {key: row[key] for key in asdict(CENTRAL_CONFIG)}
    for key in ("recovery_days", "volatility_window", "peak_window"):
        values[key] = int(values[key])
    for key in set(values) - {"recovery_days", "volatility_window", "peak_window"}:
        values[key] = float(values[key])
    return RiskOverlayConfig(**values)


def reconcile_daily_returns(level: pd.Series, decision_year: pd.Series,
                            annual_target: pd.Series) -> pd.Series:
    """Place the annual endpoint difference on the first session of each year.

    The daily curve preserves the intrayear path while the annual ledger is the
    authority for costs and endpoints. Reconciliation is accounting only and is
    never used by the stress signal.
    """
    result = level.pct_change().fillna(0.0)
    for year, indexes in decision_year.groupby(decision_year).groups.items():
        if year not in annual_target.index:
            continue
        actual_factor = float((1.0 + result.loc[indexes]).prod())
        target_factor = 1.0 + float(annual_target.loc[year])
        correction = target_factor / actual_factor
        first = indexes[0]
        result.loc[first] = (1.0 + result.loc[first]) * correction - 1.0
    return result


def run_experiment(curve_path: Path, annual_path: Path, output: Path) -> dict:
    curve = pd.read_csv(curve_path, parse_dates=["date"]).sort_values("date")
    curve = curve[curve["phase"].eq("evaluated")].reset_index(drop=True)
    annual = pd.read_csv(annual_path)
    equity_by_year = annual.set_index("decision_year")["target_equity_weight"]
    annual_by_year = annual.set_index("decision_year")
    curve["benevente1_daily_return"] = reconcile_daily_returns(
        curve.strategy, curve.decision_year, annual_by_year.net_return
    )
    curve["cdi_daily_return"] = reconcile_daily_returns(
        curve.cdi, curve.decision_year, annual_by_year.cdi_net_return
    )
    curve["mvo_daily_return"] = reconcile_daily_returns(
        curve.mvo, curve.decision_year, annual_by_year.mvo_eligible_net_return
    )
    curve["ibovespa_daily_return"] = reconcile_daily_returns(
        curve.IBOVESPA, curve.decision_year, annual_by_year.benchmark_IBOVESPA
    )
    target_equity = curve["decision_year"].map(equity_by_year)
    if target_equity.isna().any():
        raise ValueError("Every daily observation must map to a declared annual equity target.")

    central = apply_overlay(curve, target_equity, CENTRAL_CONFIG)
    central_annual = annual_returns(central)
    full_metrics = {
        "Benevente 1": metrics(central.benevente1_return, central.cdi_return, central.date),
        "Benevente 2": metrics(central.benevente2_return, central.cdi_return, central.date),
        "CDI": metrics(central.cdi_return, central.cdi_return, central.date),
    }
    for name, return_column in (("MVO", "mvo_daily_return"), ("Ibovespa", "ibovespa_daily_return")):
        series_return = central[return_column]
        full_metrics[name] = metrics(series_return, central.cdi_return, central.date)
    full_metrics["Benevente 2"]["overlay_turnover"] = float(central.overlay_turnover.sum())
    full_metrics["Benevente 2"]["overlay_cost_rate_sum"] = float(central.overlay_cost_rate.sum())

    holdout = central[central.date.dt.year >= 2019].copy()
    holdout_metrics = {
        "Benevente 1": metrics(holdout.benevente1_return, holdout.cdi_return, holdout.date),
        "Benevente 2": metrics(holdout.benevente2_return, holdout.cdi_return, holdout.date),
    }
    paired = central_annual[central_annual.year >= 2019]
    paired_test = stats.ttest_rel(paired["Benevente 2"], paired["Benevente 1"])

    grid_rows = []
    for config in configuration_grid():
        trial = apply_overlay(curve, target_equity, config)
        trial_train = trial[trial.date.dt.year <= 2018]
        trial_holdout = trial[trial.date.dt.year >= 2019]
        train_metrics = metrics(trial_train.benevente2_return, trial_train.cdi_return, trial_train.date)
        trial_metrics = metrics(trial_holdout.benevente2_return, trial_holdout.cdi_return, trial_holdout.date)
        grid_rows.append({
            **asdict(config),
            "train_cagr": train_metrics["cagr"],
            "train_max_drawdown": train_metrics["max_drawdown"],
            "train_score": train_metrics["cagr"] + 0.25 * train_metrics["max_drawdown"],
            **{f"holdout_{key}": value for key, value in trial_metrics.items()},
            "holdout_overlay_turnover": float(trial_holdout.overlay_turnover.sum()),
        })
    grid = pd.DataFrame(grid_rows)
    selected_row = grid.sort_values(
        ["train_score", "train_cagr", "holdout_overlay_turnover"], ascending=[False, False, True]
    ).iloc[0]
    config_fields = set(asdict(CENTRAL_CONFIG))
    selected_config = config_from_row(selected_row)
    selected_trial = apply_overlay(curve, target_equity, selected_config)
    selected_holdout = selected_trial[selected_trial.date.dt.year >= 2019]
    selected_metrics = metrics(selected_holdout.benevente2_return, selected_holdout.cdi_return, selected_holdout.date)
    selected_full_metrics = metrics(selected_trial.benevente2_return, selected_trial.cdi_return, selected_trial.date)
    selected_annual = annual_returns(selected_trial)
    selected_paired = selected_annual[selected_annual.year >= 2019]
    selected_paired_test = stats.ttest_rel(selected_paired["Benevente 2"], selected_paired["Benevente 1"])
    crisis = selected_trial[selected_trial.date.dt.year.eq(2020)]
    crisis_active = crisis[crisis.risk_state.gt(0)]
    crisis_annual = selected_annual[selected_annual.year.eq(2020)].iloc[0]
    crisis_drawdowns = {}
    for label, column in (("Benevente 1", "benevente1_return"),
                          ("Benevente 2", "benevente2_return"),
                          ("Ibovespa", "ibovespa_daily_return")):
        wealth = (1.0 + crisis[column]).cumprod()
        crisis_drawdowns[label] = float((wealth / wealth.cummax() - 1.0).min())
    hindsight_row = grid.sort_values(
        ["holdout_cagr", "holdout_max_drawdown"], ascending=[False, False]
    ).iloc[0]

    summary = {
        "status": "retrospective_experiment_not_published",
        "version_contract": {
            "Benevente 1": "Seleção multifatorial anual publicada, sem camada intranual.",
            "Benevente 2": "Mesma seleção anual, com redução de risco baseada em Ibovespa observável no fechamento anterior.",
        },
        "central_configuration_fixed_before_run": asdict(CENTRAL_CONFIG),
        "period": [str(curve.date.min().date()), str(curve.date.max().date())],
        "holdout_label": "2019–2025 é apenas uma separação temporal retrospectiva; não é validação prospectiva.",
        "full_period_metrics": full_metrics,
        "holdout_2019_2025_metrics": holdout_metrics,
        "training_only_selection": {
            "training_window": "2015–2018",
            "selection_score": "CAGR + 0,25 × drawdown máximo (drawdown é negativo)",
            "configuration": asdict(selected_config),
            "full_period_metrics": selected_full_metrics,
            "holdout_2019_2025_metrics": selected_metrics,
            "paired_annual_test_2019_2025": {
                "years": int(len(selected_paired)),
                "mean_difference": float((selected_paired["Benevente 2"] - selected_paired["Benevente 1"]).mean()),
                "t_statistic": float(selected_paired_test.statistic),
                "p_value": float(selected_paired_test.pvalue),
            },
            "warning": "Quatro anos de treino são insuficientes para uma escolha estável.",
        },
        "covid_2020_trace_for_training_selected_candidate": {
            "first_alert_session": str(crisis_active.date.iloc[0].date()) if not crisis_active.empty else None,
            "first_severe_session": str(crisis.loc[crisis.risk_state.eq(2), "date"].iloc[0].date()) if crisis.risk_state.eq(2).any() else None,
            "minimum_equity_weight": float(crisis.benevente2_equity_weight.min()),
            "annual_returns": {
                "Benevente 1": float(crisis_annual["Benevente 1"]),
                "Benevente 2": float(crisis_annual["Benevente 2"]),
                "Ibovespa": float(crisis_annual["Ibovespa"]),
            },
            "maximum_drawdowns": crisis_drawdowns,
            "interpretation": "A camada não antecipou a pandemia; reagiu ao estresse de mercado conhecido no fechamento anterior.",
        },
        "paired_annual_test_2019_2025": {
            "years": int(len(paired)), "mean_difference": float((paired["Benevente 2"] - paired["Benevente 1"]).mean()),
            "t_statistic": float(paired_test.statistic), "p_value": float(paired_test.pvalue),
        },
        "sensitivity_grid": {
            "configurations": int(len(grid)),
            "share_improving_cagr_vs_benevente1_holdout": float((grid.holdout_cagr > holdout_metrics["Benevente 1"]["cagr"]).mean()),
            "share_improving_drawdown_vs_benevente1_holdout": float((grid.holdout_max_drawdown > holdout_metrics["Benevente 1"]["max_drawdown"]).mean()),
            "share_improving_both": float(((grid.holdout_cagr > holdout_metrics["Benevente 1"]["cagr"]) & (grid.holdout_max_drawdown > holdout_metrics["Benevente 1"]["max_drawdown"])).mean()),
            "median_cagr": float(grid.holdout_cagr.median()),
            "median_max_drawdown": float(grid.holdout_max_drawdown.median()),
            "hindsight_best_cagr": {
                "configuration": asdict(config_from_row(hindsight_row)),
                "cagr": float(hindsight_row.holdout_cagr),
                "max_drawdown": float(hindsight_row.holdout_max_drawdown),
                "warning": "Diagnóstico retrospectivo; não é a configuração candidata.",
            },
        },
        "limitations": [
            "A família de proteção foi concebida depois da Covid e carrega viés retrospectivo conceitual.",
            "Não há arquivo histórico de notícias com horário de publicação; a LLM não participa deste teste.",
            "Custos da camada são aproximação em pontos-base; imposto intranual ainda não foi modelado.",
            "Somente sete anos entram na separação 2019–2025; o teste pareado tem baixa potência.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    central.to_csv(output / "daily_comparison.csv", index=False)
    central_annual.to_csv(output / "annual_comparison.csv", index=False)
    selected_trial.to_csv(output / "candidate_daily_comparison.csv", index=False)
    selected_annual.to_csv(output / "candidate_annual_comparison.csv", index=False)
    grid.to_csv(output / "sensitivity_grid.csv", index=False)
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the unpublished Benevente 1 versus Benevente 2 experiment.")
    parser.add_argument("--curve", default="artifacts/published_nested/daily_curve.csv")
    parser.add_argument("--annual", default="artifacts/published_nested/annual_results.csv")
    parser.add_argument("--output", default="artifacts/benevente2_event_risk")
    args = parser.parse_args()
    result = run_experiment(Path(args.curve), Path(args.annual), Path(args.output))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
