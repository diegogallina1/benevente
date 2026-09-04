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
from brapi_total_return import _fetch_cdi
from build_full_b3_cvm_fundamentals import build_full_panel
from config import SystemConfig
from optimizer import MeanVarianceOptimizer
from portfolio_recommendation import ValuePortfolioPlanner


# The configuration the nested search left live for 2026. Kept here as named
# constants so the published book, the frozen registration and the site copy
# cannot drift apart silently.
LIVE_FACTOR = "triple_factor"
LIVE_EQUITY_CAP = .55
LIVE_ISSUER_CAP = .176
LIVE_TOP_ASSETS = 5


def current_mapping(universe: pd.DataFrame, prior_mapping: pd.DataFrame,
                    decision_year: int = 2026) -> pd.DataFrame:
    """Carry only an already-audited B3/CVM bridge with the same ticker *and* ISIN.

    O ano entra como argumento, com 2026 de padrão para não quebrar quem já
    chamava: a ponte de um ano se apoia na do anterior, e com os dois números
    escritos no corpo a função só servia para 2026. Quem decidir 2027 passa
    2027, e a herança passa a vir de 2026 sozinha.
    """
    equities = universe[universe.asset_class.eq("equity")][["ticker", "isin"]].copy()
    prior = prior_mapping[prior_mapping.mapping_status.eq("accepted")].copy()
    if "universe_year" in prior:
        prior = prior[prior.universe_year.eq(decision_year - 1)].copy()
    # The current bridge export is already dated to the decision year. It is
    # accepted only after the same-ticker and same-ISIN intersection below,
    # never by ticker name alone.
    carried = equities.merge(prior, on=["ticker", "isin"], how="inner", suffixes=("", "_prior"))
    carried["universe_year"] = decision_year
    carried["decision_date"] = universe.decision_date.iloc[0]
    carried["mapping_status"] = "accepted"
    carried["match_method"] = "prior_accepted_b3_cvm_bridge_same_ticker_isin"
    return carried[prior_mapping.columns]


def _january_price_row(cache_dir: Path, tickers: set[str], year: int = 2026) -> pd.DataFrame:
    """O primeiro pregão de janeiro do ano da decisão.

    O ano entra como argumento, com 2026 de padrão para não quebrar quem já
    chamava. Com o número escrito no corpo, o arquivo do COTAHIST e o filtro de
    data só serviam para 2026, e uma execução de 2027 leria silenciosamente o
    ano errado em vez de falhar.
    """
    quotations = parse_cotahist(cache_dir / f"COTAHIST_A{year}.ZIP",
                                end_date=f"{year}-01-31", tickers=tickers)
    january = quotations[(quotations.trade_date.dt.year == year) & (quotations.trade_date.dt.month == 1)]
    decision = january.trade_date.min()
    return january[january.trade_date.eq(decision)].assign(ticker=lambda frame: frame.ticker_raw + ".SA")


def _partial_prices(cache_dir: Path, tickers: set[str], start: pd.Timestamp,
                    year: int | None = None) -> pd.DataFrame:
    """Preços do ano da decisão a partir dela. O ano sai da própria data quando não vem dito."""
    year = year or int(pd.Timestamp(start).year)
    quotations = parse_cotahist(cache_dir / f"COTAHIST_A{year}.ZIP", start_date=start, tickers=tickers)
    quotations["ticker"] = quotations.ticker_raw + ".SA"
    return quotations.pivot_table(index="trade_date", columns="ticker", values="close_price_brl", aggfunc="last").sort_index()


def monitoring_by_profile(prices: pd.DataFrame, decision: pd.Timestamp, raw_path: Path,
                          target_weights: pd.Series | None = None) -> dict:
    """Calculate the ongoing return for every published policy.

    Equity sleeves use B3 closing prices, without cash distributions.  The
    defensive sleeve uses the official CDI daily series.  Both sleeves start
    on the decision date and are combined with their *initial* policy weights,
    so the monitor never borrows the Equilibrado result for another profile.
    """
    complete = prices.dropna(axis=1, how="any")
    if complete.empty or len(complete) < 2:
        return {"through": None, "profiles": {}, "label": "Dados de preço insuficientes para o acompanhamento."}
    # Weight each holding by the weight actually published, not by an equal
    # split. The book is score-tilted inside the issuer cap, so an equal-weight
    # monitor would report a portfolio nobody holds.
    weights = (target_weights.reindex(complete.columns).fillna(0.0) if target_weights is not None
               else pd.Series(1.0 / len(complete.columns), index=complete.columns))
    equity_weight_total = float(weights.sum())
    normalised = weights / equity_weight_total if equity_weight_total > 0 else weights
    growth = complete.iloc[-1] / complete.iloc[0]
    equity_return = float((growth * normalised).sum() - 1)
    through = pd.Timestamp(complete.index.max()).normalize()
    cdi_levels = _fetch_cdi(decision, through, raw_path)
    cdi_levels = cdi_levels.reindex(complete.index).ffill().bfill()
    if cdi_levels.isna().any() or len(cdi_levels) < 2:
        raise ValueError("Série CDI incompleta no período de acompanhamento")
    cdi_return = float(cdi_levels.iloc[-1] / cdi_levels.iloc[0] - 1)
    # One published policy. The three-profile ladder was withdrawn because the
    # issuer cap interacted with the equity budget and inverted it: the
    # conservative book kept its conviction tilt while the aggressive one had
    # every name pinned at the cap and became equal weight.
    policies = {"benevente": {"equity_cap": LIVE_EQUITY_CAP, "issuer_cap": LIVE_ISSUER_CAP}}
    profiles = {}
    for name, policy in policies.items():
        equity_weight = equity_weight_total if target_weights is not None else min(
            policy["equity_cap"], len(complete.columns) * policy["issuer_cap"])
        cdi_weight = 1 - equity_weight
        profiles[name] = {
            "equity_weight": equity_weight,
            "cdi_weight": cdi_weight,
            "equity_price_return": equity_return,
            "cdi_return": cdi_return,
            "portfolio_partial_return": equity_weight * equity_return + cdi_weight * cdi_return,
        }
    return {
        "through": str(through.date()),
        "profiles": profiles,
        "label": "Resultado parcial: preços de fechamento B3 nas ações e CDI diário do BCB. Ações ainda não incluem proventos.",
    }


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
    # An earlier version built a twenty-name shortlist and then immediately
    # rebuilt the full liquid panel over it, so the shortlist was dead work and
    # the published metadata reported a universe the run had not used.
    selection_universe = liquid_universe.merge(mapping[["universe_year", "ticker"]],
                                               on=["universe_year", "ticker"], how="inner")
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
    # The live configuration frozen by the nested search: the triple-factor
    # rule over five issuers, 55% equity, and an issuer cap with enough slack
    # that it never binds mechanically. An earlier version declared this
    # protocol and then scored with value/quality and a 12% cap, so the
    # published 2026 book did not match the rule the site was publishing.
    protocol = AnnualWalkForwardConfig(2026, 2027, factor=LIVE_FACTOR, maximum_equity_weight=LIVE_EQUITY_CAP,
                                       maximum_asset_weight=LIVE_ISSUER_CAP, top_assets=LIVE_TOP_ASSETS)
    planner_config = replace(SystemConfig(), rolling_window_days=252, max_asset_weight=LIVE_ISSUER_CAP)
    active = list(history.columns)
    issuer_lookup = mapping[["ticker", "cnpj_cia"]].drop_duplicates("ticker")
    issuer_ids = {row.ticker: str(row.cnpj_cia) for row in issuer_lookup.itertuples(index=False)}
    proposal = engine.triple_factor_proposal(history.tail(252), known, decision,
                                             pd.Series(0.0, index=active), protocol,
                                             float(SystemConfig().initial_portfolio_value_brl), issuer_ids)
    eligible = set(proposal.screen.loc[proposal.screen.eligible, "ticker"])
    mvo_columns = [ticker for ticker in active if ticker == "TITULO_CDI" or ticker in eligible]
    mvo = MeanVarianceOptimizer(planner_config).optimize(history.loc[:, mvo_columns].tail(252),
                                                          {ticker: 0.0 for ticker in mvo_columns}, equity_cap=LIVE_EQUITY_CAP,
                                                          signal_influence=0.0, eligible_assets=eligible).reindex(active, fill_value=0.0)
    targets = proposal.weights.reindex(active, fill_value=0.0)
    held = [ticker for ticker in targets.index if ticker != "TITULO_CDI" and targets[ticker] > 1e-6]
    selected = (proposal.screen[proposal.screen.ticker.isin(held)]
                .merge(issuer_lookup, on="ticker", how="left")
                .sort_values("factor_score", ascending=False)
                .reset_index(drop=True))
    # Official B3 partial-year monitoring. Equity performance remains
    # price-only until corporate events are reconciled, while the CDI sleeve
    # is calculated from the official daily BCB series.
    partial = _partial_prices(b3_cache, set(selected.ticker), decision)
    available = partial.dropna(axis=1, how="all")
    monitoring = monitoring_by_profile(available, decision, destination / "bcb_sgs_12_cdi_2026.json",
                                       targets.reindex(available.columns).fillna(0.0))
    holdings = []
    for item in selected.itertuples(index=False):
        holdings.append({"ticker": item.ticker.removesuffix(".SA"), "weight": float(targets[item.ticker]),
                         "score": float(item.factor_score), "why": "Aprovado na triagem datada e classificado por qualidade, earnings yield e momento de 12 meses.",
                         "risk": "Revisar resultado, preço, liquidez e fatos relevantes antes de qualquer implementação."})
    cdi_weight = float(targets.get("TITULO_CDI", 0.0))
    result = {
        "decision_date": str(decision.date()), "status": "research_monitoring_only",
        "universe": {"all_instruments": int(len(universe)), "equities_at_decision": int(universe.asset_class.eq("equity").sum()),
                     "identifier_bridge_accepted": int(len(mapping)), "liquid_equities_examined": int(len(liquid_universe[liquid_universe.asset_class.eq("equity")])), "mapped_liquid_equities_processed": int(len(selection_universe)), "fundamental_snapshots": int(len(fundamentals)),
                     "screened_with_complete_price_history": int(len(known)), "eligible_after_screen": int(len(eligible))},
        "method": ["universo B3 datado", "ponte B3/CVM por ticker e ISIN", "ITR/DFP disponível até a decisão", "liquidez, valor, qualidade e limites de concentração"],
        "holdings": holdings, "cdi_weight": cdi_weight,
        "monitoring": monitoring,
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
