"""Does the sizing rule matter, and does it matter more for a wide basket?

Selection and sizing are separate questions. Every configuration ever searched
in this repository sized its book one way: proportional to factor confidence.
That is a choice, never a tested one, and it is the choice most likely to hurt
a wide basket, because confidence weighting puts the largest position in the
name the factor likes most regardless of how much that name moves.

This is a diagnostic over a declared grid, not a search for a winner. It
reports the marginal effect of the sizing rule holding selection fixed; the
scheme is only worth adopting if the effect is consistent across the grid
rather than largest in one cell.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

import pandas as pd

from annual_walk_forward import (AnnualWalkForwardConfig, BrazilianTaxModel, WEIGHTING_SCHEMES,
                                 apply_annual_taxes)
from profile_ladder import LADDER, MAXIMUM_NAMES_PER_SECTOR, build_engine, protocol_for
from research_configuration_search import ISSUER_CAP_SLACK, MAXIMUM_ISSUER_CAP

# The basket sizes the sizing rule is tested across, at the published budget.
BASKET_SIZES = (5, 8, 12, 16, 20)
BASKET_BUDGET = .55


def _metrics(results: pd.DataFrame) -> dict:
    net = results.net_return
    wealth = (1 + net).cumprod()
    excess = (net - results.cdi_net_return).dropna()
    return {
        "anos": len(net),
        "cagr": float(wealth.iloc[-1] ** (1 / len(net)) - 1),
        "cagr_pos_ir": float((1 + results.net_return_after_tax).prod() ** (1 / len(net)) - 1),
        "vol": float(net.std(ddof=1)),
        "pior_ano": float(net.min()),
        "sharpe_excesso": float(excess.mean() / excess.std(ddof=1)),
        "ganha_cdi": int((net > results.cdi_net_return).sum()),
        "giro_medio": float(results.turnover.mean()),
    }


def _drawdown(engine, results: pd.DataFrame) -> float:
    daily = engine.daily_curve
    if daily.empty:
        return float("nan")
    curve = daily[daily.decision_year.isin(results.decision_year)]
    column = next((name for name in ("strategy", "estrategia") if name in curve.columns), None)
    if column is None:
        return float("nan")
    level = curve[column]
    return float((level / level.cummax() - 1).min())


def run(output: Path, start_year: int, end_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    engine = build_engine()
    ladder_rows, basket_rows = [], []

    for profile in LADDER:
        base = protocol_for(profile, start_year, end_year)
        for scheme in WEIGHTING_SCHEMES:
            results, _, _ = engine.run(replace(base, weighting=scheme))
            results = apply_annual_taxes(results, BrazilianTaxModel())
            ladder_rows.append({"perfil": profile, "peso": scheme, "posicoes": base.top_assets,
                                "acoes": base.maximum_equity_weight,
                                **_metrics(results), "dd_diario": _drawdown(engine, results)})

    for count in BASKET_SIZES:
        cap = round(min(MAXIMUM_ISSUER_CAP, BASKET_BUDGET / count * ISSUER_CAP_SLACK), 6)
        base = AnnualWalkForwardConfig(start_year, end_year, factor="triple_factor", top_assets=count,
                                       maximum_equity_weight=BASKET_BUDGET, maximum_asset_weight=cap,
                                       maximum_names_per_sector=MAXIMUM_NAMES_PER_SECTOR)
        for scheme in WEIGHTING_SCHEMES:
            results, _, _ = engine.run(replace(base, weighting=scheme))
            results = apply_annual_taxes(results, BrazilianTaxModel())
            basket_rows.append({"posicoes": count, "peso": scheme,
                                **_metrics(results), "dd_diario": _drawdown(engine, results)})

    ladder = pd.DataFrame(ladder_rows)
    basket = pd.DataFrame(basket_rows)
    output.mkdir(parents=True, exist_ok=True)
    ladder.to_csv(output / "ladder_by_weighting.csv", index=False)
    basket.to_csv(output / "basket_size_by_weighting.csv", index=False)

    published = basket[basket.peso.eq("score")].set_index("posicoes")
    marginal = []
    for scheme in WEIGHTING_SCHEMES:
        if scheme == "score":
            continue
        variant = basket[basket.peso.eq(scheme)].set_index("posicoes")
        for count in BASKET_SIZES:
            marginal.append({"peso": scheme, "posicoes": count,
                             "d_cagr": variant.loc[count, "cagr"] - published.loc[count, "cagr"],
                             "d_sharpe": variant.loc[count, "sharpe_excesso"] - published.loc[count, "sharpe_excesso"],
                             "d_pior_ano": variant.loc[count, "pior_ano"] - published.loc[count, "pior_ano"],
                             "d_dd": variant.loc[count, "dd_diario"] - published.loc[count, "dd_diario"]})
    marginal_frame = pd.DataFrame(marginal)
    marginal_frame.to_csv(output / "marginal_effect_vs_score.csv", index=False)
    (output / "summary.json").write_text(json.dumps({
        "status": "diagnostic_not_selection",
        "window": f"{start_year + 1}-{end_year - 1}",
        "schemes": list(WEIGHTING_SCHEMES),
        "basket_sizes": list(BASKET_SIZES),
        "basket_budget": BASKET_BUDGET,
        "note": ("Selection is held fixed. Any scheme adopted from here multiplies the candidate space by four "
                 "and must be re-registered with the updated trial count."),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return ladder, basket


def main() -> None:
    parser = argparse.ArgumentParser(description="Marginal effect of the sizing rule, selection held fixed.")
    parser.add_argument("--output", default="artifacts/weighting_scheme_v1")
    parser.add_argument("--start-year", type=int, default=2012)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    ladder, basket = run(Path(args.output), args.start_year, args.end_year)
    fmt = lambda value: f"{value:.4f}"
    print("=== ESCADA DE PERFIL POR ESQUEMA DE PESO ===")
    print(ladder.to_string(index=False, float_format=fmt))
    print("\n=== TAMANHO DE CESTA POR ESQUEMA DE PESO (55% em acoes) ===")
    print(basket.to_string(index=False, float_format=fmt))


if __name__ == "__main__":
    main()
