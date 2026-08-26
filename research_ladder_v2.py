"""The two accepted layers together: does the pair still work?

Overlay and global sleeve were each measured against the frozen ladder on its
own. Adding their gains would be inventing a number, because they act on the
same book at the same time: the overlay moves the equity sleeve to CDI when the
Ibovespa is under stress, and the global sleeve is part of that equity sleeve.

There are two ways to combine them, and the difference is a policy question, not
a detail:

``dentro``
    The overlay treats the whole book. When the Ibovespa is in stress the global
    fund is sold down with everything else. This is the registered overlay
    applied unchanged to a book that happens to hold the fund.

``fora``
    The global fund is held at a declared share of the portfolio, rebalanced
    annually, and the overlay runs only on the rest. The reasoning is that the
    fund exists precisely because it does not follow the Ibovespa -- its daily
    correlation with the domestic sleeve is 0.064 -- so cutting it on a domestic
    stress signal sells the one asset the stress does not apply to.

Both are exactly computable and both are reported. Neither is registered.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json
import math

import pandas as pd

from annual_walk_forward import BrazilianTaxModel, apply_annual_taxes
from benevente2_event_risk import reconcile_daily_returns
from profile_ladder import LADDER, protocol_for
from profile_intrayear_risk import apply_profile_overlay
from research_global_sleeve import GLOBAL_TICKER, build_global_engine

# Round declared share of the equity budget, fixed before reading the combined
# result. The sleeve study's own curve peaked between 20% and 30%; taking the
# argmax of a curve after seeing it is the error that cost 2.63 points a year
# in the configuration search.
GLOBAL_FRACTION = .20


def _daily(engine, results: pd.DataFrame) -> pd.DataFrame:
    curve = engine.daily_curve
    curve = curve[curve.decision_year.isin(results.decision_year)].copy()
    curve["date"] = pd.to_datetime(curve.date)
    curve["strategy_daily_return"] = reconcile_daily_returns(curve.strategy, curve.decision_year,
                                                             results.set_index("decision_year").net_return)
    curve["cdi_daily_return"] = reconcile_daily_returns(curve.cdi, curve.decision_year,
                                                        results.set_index("decision_year").cdi_net_return)
    return curve.reset_index(drop=True)


def _metrics(daily_returns: pd.Series, dates: pd.Series, cdi: pd.Series) -> dict:
    clean = daily_returns.fillna(0.0)
    wealth = (1 + clean).cumprod()
    years = max(int(pd.to_datetime(dates).dt.year.nunique()), 1)
    frame = pd.DataFrame({"r": clean.to_numpy(), "c": cdi.fillna(0.0).to_numpy(),
                          "y": pd.to_datetime(dates).dt.year.to_numpy()})
    annual = frame.groupby("y").apply(lambda g: pd.Series({
        "r": (1 + g.r).prod() - 1, "c": (1 + g.c).prod() - 1}), include_groups=False)
    excess = annual.r - annual.c
    return {
        "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "vol": float(clean.std(ddof=1) * math.sqrt(252)),
        "drawdown": float((wealth / wealth.cummax() - 1).min()),
        "pior_ano": float(annual.r.min()),
        "sharpe_excesso": float(excess.mean() / excess.std(ddof=1)) if excess.std(ddof=1) else float("nan"),
        "ganha_cdi": int((annual.r > annual.c).sum()),
        "anos": int(len(annual)),
    }


def _annual_rebalanced_blend(host: pd.Series, fund: pd.Series, years: pd.Series, share: float) -> pd.Series:
    """Hold ``share`` of the portfolio in the fund, rebalanced each January.

    Compounding a fixed weight daily would rebalance for free every session,
    which is the defect this project already corrected once. The weights are
    reset at each decision year and left to drift inside it.
    """
    out = []
    for _, block in pd.DataFrame({"h": host.to_numpy(), "f": fund.to_numpy(),
                                  "y": years.to_numpy()}).groupby("y", sort=False):
        host_level = (1 + block.h.fillna(0.0)).cumprod()
        fund_level = (1 + block.f.fillna(0.0)).cumprod()
        blended = (1 - share) * host_level + share * fund_level
        out.append(blended / blended.shift(1).fillna(1.0) - 1)
    return pd.concat(out).reset_index(drop=True)


def run(output: Path, start_year: int, end_year: int) -> pd.DataFrame:
    # O painel é o que a política vigente declara. A v3 troca a coluna de caixa,
    # e o Sharpe do excesso é medido contra esse caixa — publicar o número da v2
    # ao lado da escada da v3 seria comparar contra uma régua aposentada.
    from profile_ladder_v3 import V3_INPUTS
    engine, panel = build_global_engine(prices_path=V3_INPUTS["prices"],
                                        manifest_path=V3_INPUTS["total_return_manifest"])
    rows: list[dict] = []
    checks: dict[str, dict] = {}
    tax = BrazilianTaxModel()

    for profile in LADDER:
        budget = LADDER[profile]["maximum_equity_weight"]
        base_protocol = protocol_for(profile, start_year, end_year)

        # --- domestic only -------------------------------------------------
        dom_results, _, _ = engine.run(base_protocol)
        dom_results = apply_annual_taxes(dom_results, tax)
        dom = _daily(engine, dom_results)
        fund = panel[GLOBAL_TICKER].reindex(dom.date).pct_change().fillna(0.0).reset_index(drop=True)

        rows.append({"perfil": profile, "regime": "1 escada congelada",
                     **_metrics(dom.strategy_daily_return, dom.date, dom.cdi_daily_return)})

        overlaid = apply_profile_overlay(dom, dom.decision_year.map(
            dom_results.set_index("decision_year").target_equity_weight), profile)
        rows.append({"perfil": profile, "regime": "2 + overlay",
                     **_metrics(overlaid.protected_return, dom.date, dom.cdi_daily_return)})

        # --- with the declared global sleeve -------------------------------
        glob_results, _, _ = engine.run(replace(base_protocol, global_sleeve_ticker=GLOBAL_TICKER,
                                                global_sleeve_fraction=GLOBAL_FRACTION))
        glob_results = apply_annual_taxes(glob_results, tax)
        glob = _daily(engine, glob_results)
        rows.append({"perfil": profile, "regime": "3 + perna global",
                     **_metrics(glob.strategy_daily_return, glob.date, glob.cdi_daily_return)})

        # --- both, overlay covering the fund too ---------------------------
        both_in = apply_profile_overlay(glob, glob.decision_year.map(
            glob_results.set_index("decision_year").target_equity_weight), profile)
        rows.append({"perfil": profile, "regime": "4 ambos · global dentro do overlay",
                     **_metrics(both_in.protected_return, glob.date, glob.cdi_daily_return)})

        # --- both, fund held outside the overlay ---------------------------
        # Risk-matched to variant 4 on purpose. Blending a share ``s`` of the
        # fund into the full domestic portfolio dilutes its CDI residual too, so
        # a naive blend ends up holding more equity than the carve-out and wins
        # for the wrong reason. The domestic budget is solved so that total
        # equity and the fund's share both land exactly where variant 4 puts
        # them: (1-s)*w_host + s == budget, with s == budget * fraction.
        share = budget * GLOBAL_FRACTION
        host_budget = budget * (1 - GLOBAL_FRACTION) / (1 - share)
        host_results, _, _ = engine.run(replace(base_protocol, maximum_equity_weight=host_budget))
        host_results = apply_annual_taxes(host_results, tax)
        host = _daily(engine, host_results)
        host_overlaid = apply_profile_overlay(host, host.decision_year.map(
            host_results.set_index("decision_year").target_equity_weight), profile)
        blended = _annual_rebalanced_blend(host_overlaid.protected_return, fund, host.decision_year, share)
        rows.append({"perfil": profile, "regime": "5 ambos · global fora do overlay",
                     **_metrics(blended, host.date, host.cdi_daily_return)})
        # The comparison is only meaningful if both variants target the same
        # equity exposure; assert it rather than trusting the algebra.
        matched = float((1 - share) * host_results.target_equity_weight.mean() + share)
        carved = float(glob_results.target_equity_weight.mean())
        if abs(matched - carved) > 1e-6:
            raise AssertionError(f"{profile}: variantes não pareadas ({matched:.6f} vs {carved:.6f})")
        checks[profile] = {"acoes_alvo_variante_4": carved, "acoes_alvo_variante_5": matched}

    frame = pd.DataFrame(rows)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "ladder_v2_candidates.csv", index=False)
    (output / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "global_fraction_of_equity_budget": GLOBAL_FRACTION,
        "risk_matching_check": checks,
        "instrument": GLOBAL_TICKER,
        "variants": {
            "dentro": "registered overlay applied unchanged to a book holding the fund",
            "fora": "fund held at a declared share of the portfolio, rebalanced annually, overlay on the rest",
        },
        "limitations": [
            "Both layers were designed after the crises present in this sample.",
            "About a third of the fund's return in this window came from BRL depreciation, not from the "
            "American market; the sleeve is an unhedged long dollar position.",
            "Intra-year tax on gains the overlay realises is still not modelled.",
            "Neither variant is registered. Choosing between them after reading this table is a selection "
            "and must be declared as such.",
        ],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description="Overlay and global sleeve together on the frozen ladder.")
    parser.add_argument("--output", default="artifacts/ladder_v2_candidates")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    frame = run(Path(args.output), args.start_year, args.end_year)
    for profile in frame.perfil.unique():
        block = frame[frame.perfil.eq(profile)]
        print(f"\n=== {profile.upper()} ===")
        print(block.drop(columns="perfil").to_string(index=False, float_format=lambda v: f"{v:.4f}"))


if __name__ == "__main__":
    main()
