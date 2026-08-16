"""Turn a corrected annual run into the numbers a paper can actually claim.

The headline the site used to carry — beats CDI and beats MVO — was produced by
counting wins against a benchmark that was a copy of the strategy, on a panel
that had dropped every delisted company, before tax, and with the rule chosen
after the holdout was read.  This builder recomputes the same question against
independent references and reports what is left.

It answers, explicitly and separately: how many calendar years the strategy beat
each reference, how many rolling windows of one, three, five and ten years it
beat each reference, what the result looks like after Brazilian tax, and whether
the project's own commercial-readiness rule is satisfied.  When the answer is
no, the output says no.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


REFERENCE_LABELS = {
    "cdi_net_return": "CDI",
    "mvo_eligible_net_return": "MVO de referência",
    "benchmark_IBOVESPA": "Ibovespa",
    "benchmark_BOVA11": "BOVA11 (ETF investível)",
}
AFTER_TAX_REFERENCES = {
    "cdi_net_return_after_tax": "CDI após IR",
    "mvo_net_return_after_tax": "MVO de referência após IR",
}


def _cagr(returns: pd.Series) -> float:
    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    return float((1 + clean).prod() ** (1 / len(clean)) - 1)


def _max_drawdown(returns: pd.Series) -> float:
    wealth = (1 + returns.dropna()).cumprod()
    if wealth.empty:
        return float("nan")
    return float((wealth / wealth.cummax() - 1).min())


def annual_scoreboard(results: pd.DataFrame, strategy_column: str) -> pd.DataFrame:
    """Year-by-year win or loss against every available reference."""
    rows: list[dict] = []
    after_tax_column = "net_return_after_tax"
    for column, label in {**REFERENCE_LABELS, **AFTER_TAX_REFERENCES}.items():
        if column not in results or results[column].isna().all():
            continue
        # An after-tax reference is only meaningful against the after-tax
        # strategy. Comparing a gross equity result with a net CDI result is
        # the arithmetic that makes any equity strategy look good.
        side = after_tax_column if column in AFTER_TAX_REFERENCES and after_tax_column in results else strategy_column
        comparison = results[[side, column]].dropna()
        if comparison.empty:
            continue
        wins = comparison[side] > comparison[column]
        rows.append({
            "reference": label, "reference_column": column, "strategy_column": side,
            "years": int(len(comparison)),
            "years_strategy_wins": int(wins.sum()),
            "win_rate": float(wins.mean()),
            "strategy_cagr": _cagr(comparison[side]),
            "reference_cagr": _cagr(comparison[column]),
            "annualised_excess": _cagr(comparison[side]) - _cagr(comparison[column]),
        })
    return pd.DataFrame(rows)


def rolling_windows(results: pd.DataFrame, strategy_column: str,
                    lengths: tuple[int, ...] = (1, 3, 5, 10)) -> pd.DataFrame:
    """Win rate over every overlapping window of each length.

    Overlapping windows are not independent observations. They are reported
    because the question asked was about one, five and ten year horizons, and
    the count of usable windows is printed beside every rate so nobody reads a
    two-window result as evidence.
    """
    rows: list[dict] = []
    for column, label in REFERENCE_LABELS.items():
        if column not in results or results[column].isna().all():
            continue
        frame = results[[strategy_column, column]].dropna().reset_index(drop=True)
        for length in lengths:
            if len(frame) < length:
                continue
            wins = 0
            windows = 0
            for start in range(len(frame) - length + 1):
                window = frame.iloc[start:start + length]
                strategy = float((1 + window[strategy_column]).prod())
                reference = float((1 + window[column]).prod())
                windows += 1
                wins += strategy > reference
            rows.append({"reference": label, "window_years": length, "windows": windows,
                         "windows_strategy_wins": wins, "win_rate": wins / windows,
                         "independent_windows": len(frame) // length})
    return pd.DataFrame(rows)


def readiness_verdict(results: pd.DataFrame, scoreboard: pd.DataFrame,
                      minimum_years: int = 10, maximum_drawdown: float = -.35) -> dict:
    """Apply this project's own published rule for a commercial alpha claim.

    The rule requires beating both CDI and the neutral quantitative comparator,
    net of modelled costs, on a frozen holdout. The word frozen is doing the
    work: a sample that informed the choice of rule cannot serve as the test.
    """
    reasons: list[str] = []
    years = int(len(results))
    if years < minimum_years:
        reasons.append(f"apenas {years} revisões anuais avaliadas")
    for label in ("CDI", "MVO de referência"):
        row = scoreboard[scoreboard.reference.eq(label)]
        if row.empty:
            reasons.append(f"sem comparação disponível contra {label}")
        elif float(row.iloc[0].annualised_excess) <= 0:
            reasons.append(f"não supera {label} no acumulado do período")
    after_tax = scoreboard[scoreboard.reference.eq("CDI após IR")]
    if not after_tax.empty and float(after_tax.iloc[0].annualised_excess) <= 0:
        reasons.append("não supera o CDI após imposto de renda")
    drawdown = _max_drawdown(results.net_return)
    if np.isfinite(drawdown) and drawdown < maximum_drawdown:
        reasons.append(f"drawdown de {drawdown:.1%} além do limite declarado")
    reasons.append(
        "a amostra 2015-2025 foi usada para escolher regra, família de fatores e restrições; "
        "por definição ela não é um holdout congelado"
    )
    return {
        "status": "research_only",
        "commercial_alpha_claim_permitted": False,
        "reasons": reasons,
        "years_evaluated": years,
        "max_drawdown": drawdown,
        "note": ("O status só pode mudar com anos avaliados depois do registro congelado. "
                 "Nenhuma reanálise do período histórico altera esta conclusão."),
    }


def build(results_path: str | Path, output_dir: str | Path, strategy_column: str = "net_return") -> dict:
    results = pd.read_csv(results_path)
    scoreboard = annual_scoreboard(results, strategy_column)
    windows = rolling_windows(results, strategy_column)
    verdict = readiness_verdict(results, scoreboard)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    scoreboard.to_csv(output / "annual_scoreboard.csv", index=False)
    windows.to_csv(output / "rolling_window_scoreboard.csv", index=False)
    summary = {
        "source": str(results_path).replace("\\", "/"),
        "strategy_column": strategy_column,
        "years": int(len(results)),
        "period": f"{int(results.decision_year.min())}-{int(results.decision_year.max())}",
        "strategy_cagr": _cagr(results[strategy_column]),
        "strategy_cagr_after_tax": _cagr(results.net_return_after_tax) if "net_return_after_tax" in results else None,
        "max_drawdown": _max_drawdown(results[strategy_column]),
        "annual_scoreboard": json.loads(scoreboard.to_json(orient="records")),
        "rolling_windows": json.loads(windows.to_json(orient="records")),
        "readiness": verdict,
    }
    (output / "audit_evidence.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise a corrected annual run against independent references.")
    parser.add_argument("--results", required=True, help="annual_results.csv from annual_walk_forward.py")
    parser.add_argument("--output", default="artifacts/audit_evidence")
    parser.add_argument("--strategy-column", default="net_return")
    args = parser.parse_args()
    summary = build(args.results, args.output, args.strategy_column)
    print(json.dumps({key: value for key, value in summary.items()
                      if key not in {"annual_scoreboard", "rolling_windows"}}, indent=2, ensure_ascii=False))
    print(pd.DataFrame(summary["annual_scoreboard"]).to_string(index=False))
    print(pd.DataFrame(summary["rolling_windows"]).to_string(index=False))


if __name__ == "__main__":
    main()
