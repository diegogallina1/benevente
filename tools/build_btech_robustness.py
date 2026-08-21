"""Build the BTech data-quality and resampling robustness evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
NESTED = ROOT / "artifacts" / "configuration_search_2012" / "nested_selection_annual.csv"
COVERAGE = ROOT / "artifacts" / "b3_total_return_full_coverage_2011.csv"
OUTPUT = ROOT / "artifacts" / "btech_robustness_20260820"
BOOTSTRAP_SAMPLES = 100_000
BOOTSTRAP_SEED = 20_260_820


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cagr(returns: np.ndarray) -> np.ndarray:
    return np.prod(1.0 + returns, axis=-1) ** (1.0 / returns.shape[-1]) - 1.0


def data_quality_exposure(nested: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    basis_columns = ["ticker", "basis", "corporate_actions_applied"]
    for decision in nested.itertuples(index=False):
        holdings_path = (
            ROOT / "artifacts" / f"c12_{decision.selected_configuration}" / "annual_holdings.csv"
        )
        holdings = pd.read_csv(holdings_path)
        holdings = holdings.loc[
            (holdings["decision_year"] == int(decision.decision_year))
            & (holdings["ticker"] != "TITULO_CDI")
        ].copy()
        holdings["coverage_ticker"] = holdings["ticker"].str.replace(".SA", "", regex=False)
        merged = holdings.merge(
            coverage[basis_columns], left_on="coverage_ticker", right_on="ticker", how="left"
        )
        imputed = merged["basis"].eq("total_return_imputed_distribution")
        rows.append(
            {
                "decision_year": int(decision.decision_year),
                "selected_configuration": decision.selected_configuration,
                "equity_weight": float(holdings["weight"].sum()),
                "imputed_weight": float(merged.loc[imputed, "weight"].sum()),
                "imputed_share_of_equity": float(
                    merged.loc[imputed, "weight"].sum() / holdings["weight"].sum()
                ),
                "imputed_tickers": " | ".join(merged.loc[imputed, "ticker_x"].tolist()),
                "actions_applied_to_selected_tickers": int(
                    merged["corporate_actions_applied"].fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def paired_year_bootstrap(nested: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, len(nested), size=(BOOTSTRAP_SAMPLES, len(nested)))
    strategy = nested["net_return"].to_numpy(dtype=float)
    strategy_cagr = cagr(strategy[indices])
    labels = {
        "CDI": "cdi_net_return",
        "MVO de referência": "mvo_eligible_net_return",
        "Ibovespa": "benchmark_IBOVESPA",
        "BOVA11": "benchmark_BOVA11",
    }
    rows = []
    for label, column in labels.items():
        benchmark = nested[column].to_numpy(dtype=float)
        benchmark_cagr = cagr(benchmark[indices])
        difference = strategy_cagr - benchmark_cagr
        rows.append(
            {
                "comparator": label,
                "probability_positive_excess": float(np.mean(difference > 0.0)),
                "excess_cagr_p2_5": float(np.quantile(difference, 0.025)),
                "excess_cagr_p5": float(np.quantile(difference, 0.05)),
                "excess_cagr_median": float(np.quantile(difference, 0.50)),
                "excess_cagr_p95": float(np.quantile(difference, 0.95)),
                "excess_cagr_p97_5": float(np.quantile(difference, 0.975)),
            }
        )
    return pd.DataFrame(rows)


def imputation_stress(nested: pd.DataFrame, exposure: pd.DataFrame) -> pd.DataFrame:
    base = nested["net_return"].to_numpy(dtype=float)
    imputed_weight = exposure["imputed_weight"].to_numpy(dtype=float)
    rows = []
    for haircut in (0.10, 0.25, 0.50, 1.00):
        adjusted = np.maximum(-0.999, base - imputed_weight * haircut)
        rows.append(
            {
                "return_haircut_on_imputed_sleeve": haircut,
                "stressed_strategy_cagr": float(cagr(adjusted)),
            }
        )
    return pd.DataFrame(rows)


def imputation_break_even(nested: pd.DataFrame, exposure: pd.DataFrame) -> pd.DataFrame:
    base = nested["net_return"].to_numpy(dtype=float)
    imputed_weight = exposure["imputed_weight"].to_numpy(dtype=float)
    labels = {
        "CDI": "cdi_net_return",
        "MVO de referência": "mvo_eligible_net_return",
        "Ibovespa": "benchmark_IBOVESPA",
        "BOVA11": "benchmark_BOVA11",
    }
    rows = []
    for label, column in labels.items():
        target = float(cagr(nested[column].to_numpy(dtype=float)))
        low, high = 0.0, 2.0
        for _ in range(80):
            midpoint = (low + high) / 2.0
            adjusted = np.maximum(-0.999, base - imputed_weight * midpoint)
            if float(cagr(adjusted)) > target:
                low = midpoint
            else:
                high = midpoint
        rows.append(
            {
                "comparator": label,
                "comparator_cagr": target,
                "break_even_haircut_on_imputed_sleeve": (low + high) / 2.0,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    nested = pd.read_csv(NESTED)
    coverage = pd.read_csv(COVERAGE)
    exposure = data_quality_exposure(nested, coverage)
    bootstrap = paired_year_bootstrap(nested)
    stress = imputation_stress(nested, exposure)
    break_even = imputation_break_even(nested, exposure)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    exposure.to_csv(OUTPUT / "annual_data_quality_exposure.csv", index=False)
    bootstrap.to_csv(OUTPUT / "paired_year_bootstrap.csv", index=False)
    stress.to_csv(OUTPUT / "imputation_stress.csv", index=False)
    break_even.to_csv(OUTPUT / "imputation_break_even.csv", index=False)

    summary = {
        "status": "retrospective_sensitivity_not_prospective_validation",
        "bootstrap": {
            "method": "paired non-parametric resampling of complete calendar-year return vectors",
            "samples": BOOTSTRAP_SAMPLES,
            "seed": BOOTSTRAP_SEED,
            "years": int(len(nested)),
            "warning": "Resampling measures internal stability only; it does not create new regimes, repair source data, or constitute an out-of-sample test.",
        },
        "data_quality": {
            "selected_equity_weight_with_imputed_distribution_share": float(
                exposure["imputed_weight"].sum() / exposure["equity_weight"].sum()
            ),
            "maximum_total_portfolio_weight_on_imputed_series": float(
                exposure["imputed_weight"].max()
            ),
            "maximum_year": int(
                exposure.loc[exposure["imputed_weight"].idxmax(), "decision_year"]
            ),
            "interpretation": "The headline historical return must remain diagnostic until primary corporate-action and distribution records are reconciled.",
        },
        "inputs": {
            str(NESTED.relative_to(ROOT)): sha256(NESTED),
            str(COVERAGE.relative_to(ROOT)): sha256(COVERAGE),
        },
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
