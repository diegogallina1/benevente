"""A decisão de janeiro de 2026 nos três perfis declarados.

O acompanhamento corrente publicava um livro só, escolhido pela configuração
que a busca aninhada deixou viva antes de a política ser declarada. Enquanto o
explorador mostra onze anos reconstruídos nos três perfis, 2026 aparecia como
outra coisa — e o leitor não tem como saber que a diferença existe.

Este programa aplica a política congelada à data de 02/01/2026, com o universo
B3 daquela data, a ponte B3/CVM auditada e apenas os formulários ITR e DFP
recebidos pelo regulador antes dela. A triagem roda uma vez; cada perfil corta
dela o próprio número de emissores, com o próprio orçamento e o próprio teto.

Um ponto que precisa ficar explícito: reconstruir hoje uma decisão de janeiro
não introduz retrospectiva porque a política é **declarada**. Não há nada para
escolher — orçamento, número de nomes, tetos e fatores estavam congelados e
assinados antes desta execução. É a mesma razão pela qual reconstruir 2015 é
legítimo. O que seria ilegítimo é ajustar qualquer parâmetro olhando 2026, e o
registro existe exatamente para tornar isso verificável.

Uma advertência que sobrevive: o histórico anterior a 2013 não entra em nada
aqui, e o acompanhamento de 2026 usa preço de fechamento sem ajuste de
proventos, então o retorno parcial subestima as ações que pagaram dividendos.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import argparse
import json

import pandas as pd

from advisor import snapshots_from_frame
from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 _price_column_for_ticker, _recent_market_sessions)
from build_current_2026_decision import current_mapping
from build_full_b3_cvm_fundamentals import build_full_panel
from config import SystemConfig
from profile_ladder_v2 import GLOBAL_FRACTION, LADDER_V2, _issuer_cap, domestic_protocol
from research_global_sleeve import GLOBAL_TICKER

ROOT = Path(__file__).resolve().parent
DECISION_YEAR = 2026
FACTOR = "triple_factor"
LIQUIDITY_FLOOR_BRL = 10_000_000


def _screen_inputs(price_path, universe_path, mapping_path, cvm_cache, destination):
    """Universo datado, ponte auditada, fundamentos recebidos antes da decisão."""
    universe = pd.read_csv(universe_path)
    universe["universe_year"] = DECISION_YEAR
    prior = pd.read_csv(mapping_path, dtype={"ticker": str, "isin": str, "cnpj_cia": str})
    mapping = current_mapping(universe, prior)

    liquid = universe[universe.average_daily_value_brl.ge(LIQUIDITY_FLOOR_BRL)].copy()
    fundamentals, coverage = build_full_panel(liquid, mapping, DECISION_YEAR, DECISION_YEAR, Path(cvm_cache))
    destination.mkdir(parents=True, exist_ok=True)
    fundamentals.to_csv(destination / "fundamentals_2026.csv", index=False)
    coverage.to_csv(destination / "fundamental_coverage_2026.csv", index=False)
    mapping.to_csv(destination / "identifier_bridge_2026.csv", index=False)

    prices = pd.read_csv(price_path, parse_dates=["date"]).set_index("date").sort_index()
    decision = pd.Timestamp(universe.decision_date.iloc[0])
    snapshots = snapshots_from_frame(fundamentals)
    known = [item for item in snapshots if pd.Timestamp(item.available_date) <= decision]

    prior_prices = prices.loc[prices.index < decision]
    columns = {item.ticker: _price_column_for_ticker(item.ticker, prior_prices.columns) for item in known}
    sessions = _recent_market_sessions(prices, decision, 252)
    complete = [t for t, c in columns.items() if c and prior_prices.loc[sessions, c].notna().all()]
    known = [item for item in known if item.ticker in complete]
    history = (prior_prices.loc[sessions, [*(columns[t] for t in complete), "TITULO_CDI"]]
               .rename(columns={columns[t]: t for t in complete}).pct_change().dropna())
    issuer_ids = {r.ticker: str(r.cnpj_cia) for r in
                  mapping[["ticker", "cnpj_cia"]].drop_duplicates("ticker").itertuples(index=False)}
    return {"universe": universe, "liquid": liquid, "mapping": mapping, "fundamentals": fundamentals,
            "prices": prices, "decision": decision, "known": known, "history": history,
            "issuer_ids": issuer_ids, "engine": AnnualWalkForwardEngine(prices, snapshots, SystemConfig())}


def book_for_profile(profile: str, inputs: dict) -> dict:
    """O livro de um perfil: cesta doméstica, perna global e caixa."""
    declared = LADDER_V2[profile]
    budget, count = declared["maximum_equity_weight"], declared["top_assets"]
    global_share = round(budget * GLOBAL_FRACTION, 6)
    domestic = domestic_protocol(profile, DECISION_YEAR, DECISION_YEAR + 1)

    protocol = AnnualWalkForwardConfig(
        DECISION_YEAR, DECISION_YEAR + 1, factor=FACTOR,
        maximum_equity_weight=domestic.maximum_equity_weight,
        maximum_asset_weight=domestic.maximum_asset_weight,
        top_assets=count, maximum_names_per_sector=domestic.maximum_names_per_sector)

    history, active = inputs["history"], list(inputs["history"].columns)
    proposal = inputs["engine"].triple_factor_proposal(
        history.tail(252), inputs["known"], inputs["decision"], pd.Series(0.0, index=active),
        protocol, float(SystemConfig().initial_portfolio_value_brl), inputs["issuer_ids"])

    weights = proposal.weights.reindex(active, fill_value=0.0)
    held = [t for t in weights.index if t != "TITULO_CDI" and weights[t] > 1e-6]
    scores = proposal.screen.set_index("ticker").factor_score

    # Os pesos vêm do sub-livro doméstico; a perna global é carregada fora dele,
    # então tudo escala por (1 - fração global) antes de somar o fundo.
    positions = sorted(
        ({"ticker": t.removesuffix(".SA"),
          "weight": round(float(weights[t]) * (1 - global_share), 6),
          "score": round(float(scores.get(t, float("nan"))), 4)} for t in held),
        key=lambda row: -row["weight"])
    domestic_total = round(sum(p["weight"] for p in positions), 6)
    return {
        "profile": profile,
        "declared": {"maximum_equity_weight": budget, "top_assets": count,
                     "maximum_asset_weight": _issuer_cap(budget, count),
                     "global_share_of_portfolio": global_share},
        "positions": positions,
        "domestic_equity": domestic_total,
        "global_sleeve": global_share,
        "global_instrument": GLOBAL_TICKER,
        "cash": round(1 - domestic_total - global_share, 6),
        "issuers": len(positions),
    }


def build(price_path, universe_path, mapping_path, cvm_cache, output) -> dict:
    destination = Path(output)
    inputs = _screen_inputs(price_path, universe_path, mapping_path, cvm_cache, destination)
    registration = json.loads((ROOT / "data" / "benevente_profile_ladder_v3_registration.json")
                              .read_text(encoding="utf-8"))
    books = {p: book_for_profile(p, inputs) for p in LADDER_V2}
    result = {
        "decision_date": str(inputs["decision"].date()),
        "status": "reconstrucao_sob_politica_congelada",
        "policy": registration["policy"],
        "registration_sha256": registration["registration_sha256"],
        "approved_by": registration["approved_by"],
        "honesty": (
            "A política é declarada e foi congelada antes desta execução, então aplicá-la a uma data "
            "passada não escolhe nada: orçamento, número de nomes, tetos e fatores já estavam assinados. "
            "A amostra confirmatória continua começando no primeiro pregão de 2027 — este livro é "
            "reconstrução, não validação prospectiva."),
        "universe": {
            "all_instruments": int(len(inputs["universe"])),
            "equities_at_decision": int(inputs["universe"].asset_class.eq("equity").sum()),
            "identifier_bridge_accepted": int(len(inputs["mapping"])),
            "liquid_equities_examined": int(len(inputs["liquid"][inputs["liquid"].asset_class.eq("equity")])),
            "fundamental_snapshots": int(len(inputs["fundamentals"])),
            "screened_with_complete_price_history": int(len(inputs["known"])),
        },
        "books": books,
        "limitations": [
            "Não é recomendação individual nem ordem de compra.",
            "O acompanhamento usa preço de fechamento da B3 sem ajuste de proventos: o retorno parcial "
            "subestima ações que pagaram dividendos no período.",
            "A seleção exige ponte B3/CVM auditada e fundamentos comparáveis; emissores sem os dois "
            "ficam fora da triagem e isso está no arquivo de cobertura.",
        ],
    }
    (destination / "profile_books_2026.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prices", default="data/prices_b3_cotahist_2011_2026.csv")
    parser.add_argument("--universe", default="artifacts/b3_universe_january_2026.csv")
    parser.add_argument("--mapping", default="artifacts/b3_cvm_ticker_map_2026-08-12.csv")
    parser.add_argument("--cache-dir", default="work/cvm_cache")
    parser.add_argument("--output", default="artifacts/profile_books_2026")
    args = parser.parse_args()
    result = build(args.prices, args.universe, args.mapping, args.cache_dir, args.output)
    print(f"decisão de {result['decision_date']} sob {result['policy']}\n")
    for name, book in result["books"].items():
        nomes = ", ".join(p["ticker"] for p in book["positions"])
        print(f"{name:<12} ações {book['domestic_equity']:.1%} · {GLOBAL_TICKER} {book['global_sleeve']:.1%} · "
              f"caixa {book['cash']:.1%}  ({book['issuers']} emissores)")
        print(f"             {nomes}")


if __name__ == "__main__":
    main()
