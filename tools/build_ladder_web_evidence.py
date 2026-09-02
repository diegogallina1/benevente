"""Publish the declared ladder's evidence for the site.

The pages used to read one curve from ``annual_research.json`` because there was
one published strategy. There are now three declared policies, and each of them
exists in two forms: the annual selection on its own, which is Benevente 1, and
the same selection with the intra-year overlay, which is Benevente 2.

This builder produces both forms for all three profiles from the frozen v2
registration, so the site never states a number that the registration does not
imply. It reads the registration rather than restating its parameters, which is
what keeps the page and the policy from drifting apart.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys
import math

import pandas as pd

# Rodado como script, o Python põe tools/ no sys.path, não a raiz do
# repositório — então os módulos de pesquisa que vivem na raiz não são
# encontrados. Sob pytest isso não aparece, porque o pytest insere a raiz
# sozinho: o teste passa e o script quebra, que foi exatamente o que houve.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from annual_walk_forward import BrazilianTaxModel, apply_annual_taxes
from profile_intrayear_risk import apply_profile_overlay
from profile_ladder_v2 import (GLOBAL_FRACTION, LADDER_V2, domestic_protocol)
from profile_ladder_v3 import V3_INPUTS
from research_global_sleeve import GLOBAL_TICKER, build_global_engine
from research_ladder_v2 import _annual_rebalanced_blend, _daily

# Uma marca só. Os módulos continuam sendo Benevente 1 (seleção) e Benevente 2
# (proteção), e "Benevente Quant AI" continua sendo o nome da pesquisa. Um nome
# de produto a mais dividia a atenção sem descrever nada que os módulos já não
# descrevessem.
PUBLIC_NAME = "Benevente"
# A v3 declara Tesouro Selic como caixa. Continuar rotulando a série como "CDI"
# publicaria um número do instrumento com o nome do índice — o tipo de troca
# silenciosa que este projeto existe para impedir.
CASH_LABEL = "Tesouro Selic"
# A política vigente é a v3: mesma escada da v2 com o caixa declarado como
# instrumento comprável. A v2 fica publicada como linhagem, não como vigente.
# A v4 acrescenta o ultraconservador e não toca nos três anteriores. O arquivo da
# v3 fica como está: registro congelado não se reescreve, ele é sucedido.
REGISTRATION = ROOT / "data" / "benevente_profile_ladder_v4_registration.json"
SUPERSEDED_REGISTRATION = ROOT / "data" / "benevente_profile_ladder_v3_registration.json"
BENCHMARKS = ROOT / "data" / "benchmarks_market_2011_2025.csv"


def _metrics(returns: pd.Series, dates: pd.Series) -> dict:
    clean = returns.fillna(0.0)
    wealth = (1 + clean).cumprod()
    years = max(int(pd.to_datetime(dates).dt.year.nunique()), 1)
    return {
        "cagr": float(wealth.iloc[-1] ** (1 / years) - 1),
        "cumulative_return": float(wealth.iloc[-1] - 1),
        "annual_volatility": float(clean.std(ddof=1) * math.sqrt(252)),
        "max_drawdown": float((wealth / wealth.cummax() - 1).min()),
    }


def _reference(curve: pd.DataFrame, column: str) -> dict:
    """Benchmark metrics read from the source series, not from the engine curve.

    Two separate defects made this necessary. Filling the level's missing
    sessions with a zero return deletes the market's move *across* each gap and
    understates the benchmark, which flatters every comparison against it. And
    the engine's own rebased benchmark level drifts: over the identical 2,718
    sessions it accumulates 247.2% where the source accumulates 239.1%, an
    overstatement of roughly eight points. The drift is a separate bug that
    still affects the main chart and is recorded as such.

    Reading the dated source over exactly the sessions the run covered avoids
    both, and is the number a reader can reproduce from a published file.
    """
    dates = pd.to_datetime(curve.date)
    source = pd.read_csv(BENCHMARKS, parse_dates=["date"]).set_index("date")
    if column not in source.columns:
        return {}
    level = source[column].reindex(pd.DatetimeIndex(dates)).dropna()
    if len(level) < 2:
        return {}
    return _metrics(level.pct_change().dropna(), level.index.to_series())


def _policy_row_stats(level: pd.Series, decision: pd.Timestamp, next_decision: pd.Timestamp | None) -> dict:
    """O que a fatia declarada tinha de observável na data, e o que rendeu depois.

    O leitor perguntou, com razão, por que IVVB11 e CDI apareciam sem retorno:
    a fatia não é pontuada pelo fator, mas negocia todos os dias. O retorno de
    doze meses e a volatilidade usam apenas sessões anteriores à decisão; o
    realizado usa a mesma janela decisão-a-decisão das ações. Quando o
    instrumento ainda não tinha um ano completo de histórico (IVVB11 em 2015),
    os campos observáveis ficam nulos em vez de fingir uma janela cheia.
    """
    level = level.dropna()
    before = level[level.index <= decision]
    trailing_12m = trailing_vol = None
    if len(before) >= 200:
        window = before.iloc[-253:]
        trailing_12m = round(float(window.iloc[-1] / window.iloc[0] - 1), 4)
        trailing_vol = round(float(window.pct_change().dropna().std(ddof=1) * math.sqrt(252)), 4)
    realised = None
    after = level[level.index >= decision]
    if len(after) > 1:
        end = after[after.index <= next_decision] if next_decision is not None else after
        if len(end) > 1:
            realised = round(float(end.iloc[-1] / end.iloc[0] - 1), 4)
    return {"trailing_12m": trailing_12m, "trailing_vol": trailing_vol, "realised_next_year": realised}


def _composition(holdings: pd.DataFrame, results: pd.DataFrame, global_share: float,
                 panel: pd.DataFrame) -> list[dict]:
    """Every position of every decision, with what was known when it was taken.

    A profile is only auditable if a reader can see what it held, how much, why
    it entered and what happened afterwards. The score, the trailing return and
    the trailing volatility are the values observable at the decision date; the
    realised return is deliberately kept in a separate field, because it is the
    one number the decision could not have used.
    """
    equity = holdings[holdings.ticker.ne("TITULO_CDI")]
    targets = results.set_index("decision_year").target_equity_weight
    years = []
    for year, block in equity.groupby("decision_year"):
        rows = [{
            "ticker": str(item.ticker),
            "weight": round(float(item.weight) * (1 - global_share), 6),
            "previous_weight": round(float(item.previous_weight) * (1 - global_share), 6),
            "action": str(item.decision_action),
            "score": None if pd.isna(item.value_quality_score) else round(float(item.value_quality_score), 4),
            "trailing_12m": None if pd.isna(item.trailing_12m_return_at_decision)
                            else round(float(item.trailing_12m_return_at_decision), 4),
            "trailing_vol": None if pd.isna(item.trailing_12m_volatility_at_decision)
                            else round(float(item.trailing_12m_volatility_at_decision), 4),
            "eligible": bool(item.eligible_at_decision),
            "realised_next_year": None if pd.isna(item.realised_next_year_return)
                                  else round(float(item.realised_next_year_return), 4),
        } for item in block.itertuples()]
        domestic = sum(row["weight"] for row in rows)
        decision = pd.Timestamp(block.decision_date.iloc[0])
        following = equity[equity.decision_year.eq(year + 1)]
        next_decision = (pd.Timestamp(following.decision_date.iloc[0])
                         if len(following) else None)
        years.append({
            "decision_year": int(year),
            "decision_date": str(block.decision_date.iloc[0]),
            "global_row": _policy_row_stats(panel["IVVB11"], decision, next_decision),
            "cash_row": _policy_row_stats(panel["TITULO_CDI"], decision, next_decision),
            "positions": sorted(rows, key=lambda row: -row["weight"]),
            "domestic_equity": round(domestic, 6),
            "global_sleeve": round(global_share, 6),
            "cash": round(1 - domestic - global_share, 6),
            "declared_equity": round(float(targets.get(year, float("nan"))) * (1 - global_share) + global_share, 6),
        })
    return years


def _years_beating_cash(track: pd.Series, daily: pd.DataFrame) -> dict:
    """Calendar years in which the published series beat cash.

    Both sides are compounded over the same calendar year from the same daily
    index, so a partial first or last year is compared like with like.
    """
    frame = pd.DataFrame({
        "r": track.to_numpy(),
        "c": daily.cdi_daily_return.to_numpy(),
        "y": pd.to_datetime(daily.date).dt.year.to_numpy(),
    }).fillna(0.0)
    annual = frame.groupby("y").apply(
        lambda block: pd.Series({"r": (1 + block.r).prod() - 1, "c": (1 + block.c).prod() - 1}),
        include_groups=False)
    return {"years_beating_cdi": int((annual.r > annual.c).sum())}


# O retrospectivo cobre os quatro degraus. O acompanhamento de 2026, que vive em
# carteira2026.js, continua com três: o ultraconservador foi declarado em
# 30/08/2026 e o monitor diário nunca o seguiu. As duas listas são diferentes de
# propósito, e fundi-las publicaria um acompanhamento que não existe.
LABELS = {"ultraconservador": "Ultraconservador", "conservador": "Conservador",
          "equilibrado": "Equilibrado", "arrojado": "Arrojado"}


def _monthly_curve(daily_dates: pd.Series, tracks: dict[str, pd.Series]) -> dict:
    """Month-end levels of each declared profile, rebased to 100 together.

    Eleven January points cannot show a drawdown or when a year turned, and the
    raw daily series reads as a smear at page width; month ends are the
    readable middle. Every series is rebased on the same first date, so the
    chart compares wealth paths rather than unrelated scales.
    """
    frame = pd.DataFrame({name: series.to_numpy() for name, series in tracks.items()})
    frame.index = pd.to_datetime(daily_dates).to_numpy()
    levels = (1 + frame.fillna(0.0)).cumprod()
    month_end = levels.resample("ME").last().dropna(how="all")
    # The first point is the opening value, not the first month's close, so the
    # chart starts at 100 instead of at whatever the market did in January.
    opening = pd.DataFrame([[1.0] * len(levels.columns)], columns=levels.columns,
                           index=[levels.index[0]])
    month_end = pd.concat([opening, month_end])
    rebased = month_end / month_end.iloc[0] * 100
    return {
        "dates": [stamp.date().isoformat() for stamp in rebased.index],
        "series": {name: [round(float(value), 4) for value in rebased[name]] for name in rebased.columns},
        "evaluation_starts": rebased.index[0].date().isoformat(),
        "note": ("Perfis declarados com a camada de risco intranual. Rebaseados em 100 na mesma data. "
                 "Referências lidas da série datada de origem."),
    }


def build(start_year: int, end_year: int) -> dict:
    if not REGISTRATION.exists():
        raise SystemExit("Congele a v3 antes de publicar: profile_ladder_v3.py --register")
    registration = json.loads(REGISTRATION.read_text(encoding="utf-8"))
    # O painel da v3 difere do da v2 numa coluna só — a de caixa, que deixou de
    # ser índice e passou a ser Tesouro Selic. Ler o painel que o registro
    # declara, em vez do padrão, é o que mantém a página e a política juntas.
    engine, panel = build_global_engine(prices_path=V3_INPUTS["prices"],
                                        manifest_path=V3_INPUTS["total_return_manifest"])
    tax = BrazilianTaxModel()

    profiles: dict[str, dict] = {}
    references: dict = {}
    window = {}
    tracks: dict[str, pd.Series] = {}
    holdings_by_profile: dict[str, list] = {}
    curve_dates = None
    for profile in LADDER_V2:
        protocol = domestic_protocol(profile, start_year, end_year)
        results, _, holdings = engine.run(protocol)
        results = apply_annual_taxes(results, tax)
        daily = _daily(engine, results)
        overlaid = apply_profile_overlay(
            daily, daily.decision_year.map(results.set_index("decision_year").target_equity_weight), profile)
        fund = panel[GLOBAL_TICKER].reindex(daily.date).pct_change().fillna(0.0).reset_index(drop=True)
        share = float(LADDER_V2[profile]["maximum_equity_weight"]) * GLOBAL_FRACTION

        holdings_by_profile[profile] = _composition(holdings, results, share, panel)
        benevente1 = _annual_rebalanced_blend(daily.strategy_daily_return, fund, daily.decision_year, share)
        benevente2 = _annual_rebalanced_blend(overlaid.protected_return, fund, daily.decision_year, share)
        tracks[LABELS[profile]] = benevente2
        if curve_dates is None:
            curve_dates = daily.date
        declared = registration["profiles"][profile]
        profiles[profile] = {
            "declared": {
                "maximum_equity_weight": declared["maximum_equity_weight"],
                "top_assets": declared["top_assets"],
                "maximum_asset_weight": declared["maximum_asset_weight"],
                "global_share_of_portfolio": declared["global_share_of_portfolio"],
            },
            "benevente1": _metrics(benevente1, daily.date),
            "benevente2": _metrics(benevente2, daily.date),
            "average_positions": float(results.equity_positions.mean()),
            "average_sectors": float(results.distinct_sectors.mean()),
            "average_turnover": float(results.turnover.mean()),
            # Counted on the series the site actually publishes. Reading it from
            # the bare domestic run instead — no global sleeve, no overlay —
            # answers a question about a portfolio nobody is offered, and it
            # disagreed with the published policy by one year in every profile.
            **_years_beating_cash(benevente2, daily),
            "years": int(len(results)),
        }
        if not references:
            references = {
                CASH_LABEL: _metrics(daily.cdi_daily_return, daily.date),
                "Ibovespa": _reference(daily, "IBOVESPA"),
                "BOVA11": _reference(daily, "BOVA11"),
            }
            window = {"first_decision_year": int(results.decision_year.min()),
                      "last_decision_year": int(results.decision_year.max()),
                      "first_session": str(pd.to_datetime(daily.date).min().date()),
                      "last_session": str(pd.to_datetime(daily.date).max().date())}

    source = pd.read_csv(BENCHMARKS, parse_dates=["date"]).set_index("date")
    index = pd.DatetimeIndex(pd.to_datetime(curve_dates))
    for label, column in (("Ibovespa", "IBOVESPA"),):
        if column in source.columns:
            level = source[column].reindex(index).ffill()
            tracks[label] = level.pct_change().fillna(0.0).reset_index(drop=True)
    tracks[CASH_LABEL] = daily.cdi_daily_return.reset_index(drop=True)

    return {
        "policy": registration["policy"],
        # Nome público do modelo vigente. O registro congelado não é tocado:
        # renomear não muda política, e alterá-lo quebraria o selo que dá sentido
        # ao registro. Benevente 1 e 2 continuam sendo as versões registradas e
        # descrevem as camadas de que o Alpha é feito.
        "public_name": PUBLIC_NAME,
        "lineage": {
            "Benevente 1": "módulo de seleção: a cesta anual declarada, com a perna global",
            "Benevente 2": "módulo de proteção: reduz a exposição doméstica sob estresse observável",
            # Contado do registro, não escrito: este texto dizia "três" num
            # arquivo que listava quatro perfis logo abaixo.
            PUBLIC_NAME: (f"os dois módulos, em "
                          f"{ {3: 'três', 4: 'quatro', 5: 'cinco'}.get(len(registration['profiles']), len(registration['profiles']))} "
                          f"perfis declarados e congelados"),
        },
        "registration_sha256": registration["registration_sha256"],
        "approved_by": registration["approved_by"],
        "approved_by_display": "Diego Gallina",
        "registered_at": registration["registered_at"],
        "confirmatory_sample_starts": registration["confirmatory_sample_starts"],
        "window": window,
        "profiles": profiles,
        "references": references,
        "monthly_curve": _monthly_curve(curve_dates, tracks),
        "composition": holdings_by_profile,
        "global_sleeve": {
            "instrument": registration["global_sleeve"]["instrument"],
            "share_of_equity_budget": registration["global_sleeve"]["share_of_equity_budget"],
            "currency_warning": registration["global_sleeve"]["unhedged_currency_warning"],
        },
        "overlay_applies_to": registration["intrayear_overlay"]["applies_to"],
        "status": ("Retrospectivo. A janela foi usada para desenvolver as próprias regras; "
                   "a amostra confirmatória começa no primeiro pregão de 2027."),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the declared ladder's evidence for the site.")
    parser.add_argument("--output", default="web/ladder_v2.json")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=2026)
    args = parser.parse_args()
    payload = build(args.start_year, args.end_year)
    composition = payload.pop("composition")
    target = ROOT / args.output
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    # A composição vai num arquivo próprio: são centenas de posições e a página
    # da escada não precisa carregá-las para desenhar a tabela de topo.
    (ROOT / "web" / "composition.json").write_text(
        json.dumps({"public_name": payload["public_name"],
                    "registration_sha256": payload["registration_sha256"],
                    "window": payload["window"],
                    "profiles": composition}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"escrito {args.output} · janela {payload['window']['first_decision_year']}"
          f"–{payload['window']['last_decision_year']}")
    for name, item in payload["profiles"].items():
        b1, b2 = item["benevente1"], item["benevente2"]
        print(f"  {name:12s} B1 {b1['cagr']:6.2%} / {b1['max_drawdown']:7.2%}   "
              f"B2 {b2['cagr']:6.2%} / {b2['max_drawdown']:7.2%}")
    print(f"  {CASH_LABEL:12s} {payload['references'][CASH_LABEL]['cagr']:6.2%}"
          f" · Ibovespa {payload['references']['Ibovespa']['cagr']:6.2%}")


if __name__ == "__main__":
    main()
