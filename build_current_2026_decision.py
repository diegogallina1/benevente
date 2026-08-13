"""Build a dated January-2026 research decision and partial-year monitor.

This is intentionally not an order generator.  The January screen uses only
the B3 universe, CVM filings and prices available on the decision date.  The
subsequent monitoring return is labelled price return because official B3
COTAHIST, unlike the historical Yahoo research panel, does not adjust for
cash distributions.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import pandas as pd

from annual_walk_forward import AnnualWalkForwardConfig, AnnualWalkForwardEngine, _price_column_for_ticker, _recent_market_sessions
from advisor import snapshots_from_frame
from b3_universe import parse_cotahist
from build_full_b3_cvm_fundamentals import build_full_panel
from config import SystemConfig
from optimizer import MeanVarianceOptimizer
from portfolio_recommendation import ValuePortfolioPlanner


def current_mapping(universe: pd.DataFrame, prior_mapping: pd.DataFrame) -> pd.DataFrame:
    """Carry only an already-audited B3/CVM bridge with the same ticker *and* ISIN."""
    equities = universe[universe.asset_class.eq("equity")][["ticker", "isin"]].copy()
    prior = prior_mapping[(prior_mapping.universe_year.eq(2025)) & prior_mapping.mapping_status.eq("accepted")].copy()
    carried = equities.merge(prior, on=["ticker", "isin"], how="inner", suffixes=("", "_prior"))
    carried["universe_year"] = 2026
    carried["decision_date"] = universe.decision_date.iloc[0]
    carried["mapping_status"] = "accepted"
    carried["match_method"] = "prior_accepted_b3_cvm_bridge_same_ticker_isin"
    return carried[prior_mapping.columns]


def _january_price_row(cache_dir: Path, tickers: set[str]) -> pd.DataFrame:
    quotations = parse_cotahist(cache_dir / "COTAHIST_A2026.ZIP", end_date="2026-01-31", tickers=tickers)
    january = quotations[(quotations.trade_date.dt.year == 2026) & (quotations.trade_date.dt.month == 1)]
    decision = january.trade_date.min()
    return january[january.trade_date.eq(decision)].assign(ticker=lambda frame: frame.ticker_raw + ".SA")


def _partial_prices(cache_dir: Path, tickers: set[str], start: pd.Timestamp) -> pd.DataFrame:
    quotations = parse_cotahist(cache_dir / "COTAHIST_A2026.ZIP", start_date=start, tickers=tickers)
    quotations["ticker"] = quotations.ticker_raw + ".SA"
    return quotations.pivot_table(index="trade_date", columns="ticker", values="close_price_brl", aggfunc="last").sort_index()


def build_current_decision(price_path: str | Path, universe_path: str | Path, mapping_path: str | Path,
                           cvm_cache_dir: str | Path, b3_cache_dir: str | Path, output: str | Path) -> dict:
    cvm_cache = Path(cvm_cache_dir); b3_cache = Path(b3_cache_dir); destination = Path(output); destination.mkdir(parents=True, exist_ok=True)
    universe = pd.read_csv(universe_path)
    universe["universe_year"] = 2026
    prior_mapping = pd.read_csv(mapping_path, dtype={"ticker": str, "isin": str, "cnpj_cia": str})
    mapping = current_mapping(universe, prior_mapping)
    mapping.to_csv(destination / "identifier_bridge_2026.csv", index=False)
    # The portfolio gate is deliberately restricted to liquid equities.  The
    # full B3 inventory remains visible in the product, but it would be
    # misleading to claim that an illiquid BDR, ETF or stock is comparable
    # with a liquid issuer in an annual fundamental portfolio.
    liquid_universe = universe[universe.average_daily_value_brl.ge(10_000_000)].copy()
    # The dated CVM derivation is intentionally conservative.  Processing
    # the most liquid mapped issuers first yields a reviewable decision
    # universe without turning a published research refresh into an opaque,
    # multi-hour batch job. The inventory itself is still complete.
    liquid_mapped = liquid_universe.merge(mapping[["universe_year", "ticker"]], on=["universe_year", "ticker"], how="inner")
    selection_universe = (liquid_mapped.sort_values("average_daily_value_brl", ascending=False)
                           .head(20).drop(columns=[]))
    selection_universe = universe.merge(selection_universe[["universe_year", "ticker"]], on=["universe_year", "ticker"], how="inner")
    fundamentals, coverage = build_full_panel(selection_universe, mapping, 2026, 2026, cvm_cache)
    fundamentals, coverage = build_full_panel(liquid_universe, mapping, 2026, 2026, cvm_cache)
    fundamentals.to_csv(destination / "fundamentals_2026.csv", index=False)
    coverage.to_csv(destination / "fundamental_coverage_2026.csv", index=False)
    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date").sort_index()
    decision = pd.Timestamp(universe.decision_date.iloc[0])
    snapshots = snapshots_from_frame(fundamentals)
    engine = AnnualWalkForwardEngine(prices, snapshots, SystemConfig())
    known = [item for item in snapshots if pd.Timestamp(item.available_date) <= decision]
    prior_prices = prices.loc[prices.index < decision]
    columns = {item.ticker: _price_column_for_ticker(item.ticker, prior_prices.columns) for item in known}
    sessions = _recent_market_sessions(prices, decision, 252)
    complete = [ticker for ticker, column in columns.items() if column and prior_prices.loc[sessions, column].notna().all()]
    known = [item for item in known if item.ticker in complete]
    source_columns = [columns[ticker] for ticker in complete]
    history = prior_prices.loc[sessions, [*source_columns, "TITULO_CDI"]].rename(columns={columns[ticker]: ticker for ticker in complete}).pct_change().dropna()
    protocol = AnnualWalkForwardConfig(2026, 2027, factor="value_quality", maximum_equity_weight=.55, maximum_asset_weight=.12, top_assets=4)
    planner_config = replace(SystemConfig(), rolling_window_days=252, max_asset_weight=.12)
    scores = engine.factor_scores(history, "value_quality")
    proposal = ValuePortfolioPlanner(planner_config).propose(history.tail(252), known, decision,
                                                              maximum_equity_weight=.55, maximum_asset_weight=.12,
                                                              scores_override=scores)
    eligible = set(proposal.screen.loc[proposal.screen.eligible, "ticker"])
    active = list(history.columns)
    mvo_columns = [ticker for ticker in active if ticker == "TITULO_CDI" or ticker in eligible]
    mvo = MeanVarianceOptimizer(planner_config).optimize(history.loc[:, mvo_columns].tail(252),
                                                          {ticker: 0.0 for ticker in mvo_columns}, equity_cap=.55,
                                                          signal_influence=0.0, eligible_assets=eligible).reindex(active, fill_value=0.0)
    targets = proposal.weights.reindex(active, fill_value=0.0)
    # A listed company may have more than one share class.  Treating them as
    # independent positions would disguise concentration, so retain only the
    # best-scored class per CVM issuer and cap the published candidate at four
    # issuers.  The remaining weight is the explicit CDI reserve.
    issuer_lookup = mapping[["ticker", "cnpj_cia"]].drop_duplicates("ticker")
    ranked = (proposal.screen[proposal.screen.eligible]
              .merge(issuer_lookup, on="ticker", how="left")
              .sort_values("value_quality_score", ascending=False)
              .drop_duplicates("cnpj_cia")
              .head(4))
    selected = ranked.reset_index(drop=True)
    targets = pd.Series(0.0, index=active)
    for ticker in selected.ticker:
        targets.loc[ticker] = .12
    targets.loc["TITULO_CDI"] = 1 - float(targets.drop("TITULO_CDI", errors="ignore").sum())
    # Official B3 partial-year price monitoring.  This is intentionally not compared to total-return history.
    partial = _partial_prices(b3_cache, set(selected.ticker), decision)
    available = partial.dropna(how="all")
    selected_columns = [ticker for ticker in selected.ticker if ticker in available.columns]
    partial_returns = available[selected_columns].pct_change().dropna()
    price_return = float((1 + partial_returns @ targets.reindex(selected_columns, fill_value=0.0)).prod() - 1) if not partial_returns.empty else None
    last_observation = str(available.index.max().date()) if not available.empty else None
    holdings = []
    for item in selected.itertuples(index=False):
        holdings.append({"ticker": item.ticker.removesuffix(".SA"), "weight": float(targets[item.ticker]),
                         "score": float(item.value_quality_score), "why": "Aprovado no ranking de valor e qualidade, após liquidez e critérios de segurança.",
                         "risk": "Revisar resultado, preço, liquidez e fatos relevantes antes de qualquer implementação."})
    cdi_weight = float(targets.get("TITULO_CDI", 0.0))
    result = {
        "decision_date": str(decision.date()), "status": "research_monitoring_only",
        "universe": {"all_instruments": int(len(universe)), "equities_at_decision": int(universe.asset_class.eq("equity").sum()),
                     "identifier_bridge_accepted": int(len(mapping)), "liquid_equities_examined": int(len(liquid_universe[liquid_universe.asset_class.eq("equity")])), "mapped_liquid_equities_processed": int(len(selection_universe)), "fundamental_snapshots": int(len(fundamentals)),
                     "screened_with_complete_price_history": int(len(known)), "eligible_after_screen": int(len(eligible))},
        "method": ["universo B3 datado", "ponte B3/CVM por ticker e ISIN", "ITR/DFP disponível até a decisão", "liquidez, valor, qualidade e limites de concentração"],
        "holdings": holdings, "cdi_weight": cdi_weight,
        "monitoring": {"through": last_observation, "portfolio_price_return": price_return,
                       "label": "Retorno parcial por preço B3; não inclui proventos e não é comparável ao retorno total histórico."},
        "limitations": ["Não é recomendação individual ou ordem.", "O universo completo é inventariado; nesta versão, a seleção de ações exige ponte B3/CVM e fundamentos comparáveis.", "Acompanhamento de 2026 usa preço oficial B3 sem ajuste de proventos; reconciliação é necessária antes de qualquer alegação institucional."],
    }
    (destination / "current_decision_2026.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prices", required=True); parser.add_argument("--universe", required=True)
    parser.add_argument("--mapping", required=True); parser.add_argument("--cache-dir", default="work/cvm_cache")
    parser.add_argument("--b3-cache-dir", default="work/b3_cache"); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build_current_decision(args.prices, args.universe, args.mapping, args.cache_dir, args.b3_cache_dir, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
