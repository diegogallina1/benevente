"""Viability probe for the fixed-income engine's central idea.

Two claims were made in the product note and neither had been verified against
real data. This probe tests both, and nothing else -- it is not the engine.

**Claim 1: everything can be reduced to one comparison axis.**
A CDB at 112% of CDI and an LCI at 94% of CDI are not comparable as quoted: one
pays income tax and the other does not. The claim was that both can be reduced
to "% of CDI equivalent, net, over this client's horizon". That requires solving
for the ``x`` at which a taxed product paying ``x`` percent of CDI leaves the
same money on the table as the exempt one.

**Claim 2: the CDI projection that solving needs does not require a forecast.**
This is the circularity that kills naive comparators: to price a fixed-rate bond
against CDI you need future CDI, which nobody knows. The way out is the same one
the equity side already uses -- do not forecast, read what the curve prices. The
Tesouro Prefixado rate for a maturity *is* the market's implied average CDI to
that date, so it becomes the projection, and the client's decision becomes an
explicit bet against it rather than a hidden assumption.

Source: the Tesouro Transparente open dataset, public and unauthenticated.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import io
import json
import urllib.request

import pandas as pd

from annual_walk_forward import BrazilianTaxModel

TESOURO_CSV = ("https://www.tesourotransparente.gov.br/ckan/dataset/"
               "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
               "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")


def load_tesouro(cache: Path) -> pd.DataFrame:
    if not cache.exists():
        request = urllib.request.Request(TESOURO_CSV, headers={"User-Agent": "benevente-research/1.0"})
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(urllib.request.urlopen(request, timeout=300).read())
    frame = pd.read_csv(io.BytesIO(cache.read_bytes()), sep=";", decimal=",", encoding="latin-1")
    frame.columns = ["tipo", "vencimento", "data", "taxa_compra", "taxa_venda", "pu_compra", "pu_venda", "pu_base"]
    for column in ("vencimento", "data"):
        frame[column] = pd.to_datetime(frame[column], format="%d/%m/%Y")
    return frame


def curve_on(frame: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """The tradable curve of one session: one rate per title still alive."""
    day = frame[frame.data.eq(as_of) & frame.vencimento.gt(as_of)].copy()
    day["anos"] = (day.vencimento - as_of).dt.days / 365.25
    # The buy rate is what the investor actually receives.
    return day[["tipo", "vencimento", "anos", "taxa_compra"]].sort_values(["tipo", "vencimento"])


def implied_inflation(curve: pd.DataFrame, tolerance_years: float = .75) -> pd.DataFrame:
    """Break-even inflation: the number the IPCA+ decision is a bet against."""
    fixed = curve[curve.tipo.str.contains("Prefixado")]
    real = curve[curve.tipo.str.contains("IPCA")]
    rows = []
    for item in real.itertuples():
        near = fixed[(fixed.anos - item.anos).abs() <= tolerance_years]
        if near.empty:
            continue
        match = near.iloc[(near.anos - item.anos).abs().argsort().iloc[0]]
        rows.append({
            "vencimento": item.vencimento.date().isoformat(),
            "anos": round(item.anos, 2),
            "taxa_real": item.taxa_compra,
            "prefixado_pareado": match.taxa_compra,
            "inflacao_implicita": round(((1 + match.taxa_compra / 100) / (1 + item.taxa_compra / 100) - 1) * 100, 3),
        })
    return pd.DataFrame(rows)


def net_accumulation(annual_rate: float, years: float, exempt: bool, tax: BrazilianTaxModel) -> float:
    """Accumulation net of the regressive income-tax table, or exempt."""
    gross = (1 + annual_rate) ** years
    if exempt:
        return gross
    rate = BrazilianTaxModel.fixed_income_rate_for(years * 365.25)
    return 1 + (gross - 1) * (1 - rate)


def cdi_equivalent(annual_rate: float, years: float, exempt: bool, projected_cdi: float,
                   tax: BrazilianTaxModel) -> float:
    """Percent of CDI a taxed product would have to pay to match this one.

    Solved rather than approximated, because the tax applies to the gain and not
    to the rate: the shortcut ``rate / cdi`` is wrong for an exempt product by
    exactly the amount that makes exempt products look worse than they are.
    """
    target = net_accumulation(annual_rate, years, exempt, tax)
    low, high = 0.0, 5.0
    for _ in range(80):
        middle = (low + high) / 2
        if net_accumulation(projected_cdi * middle, years, False, tax) < target:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def run(output: Path, cache: Path, horizon_years: float) -> dict:
    frame = load_tesouro(cache)
    as_of = frame.data.max()
    curve = curve_on(frame, as_of)

    # The market's own projection for the horizon: the fixed-rate bond that
    # matures nearest to it. No forecast is made or needed.
    fixed = curve[curve.tipo.str.contains("Prefixado")]
    if fixed.empty:
        raise SystemExit("No fixed-rate bond on the last session; cannot derive an implied CDI.")
    anchor = fixed.iloc[(fixed.anos - horizon_years).abs().argsort().iloc[0]]
    projected_cdi = anchor.taxa_compra / 100

    tax = BrazilianTaxModel()
    # Quotes a client would actually be shown. The bank ones are illustrative
    # because there is no public source for them -- that is the whole point of
    # the catalogue problem flagged in the product note.
    catalogue = [
        {"produto": f"Tesouro Prefixado {anchor.vencimento.year}", "tipo": "prefixado",
         "taxa": anchor.taxa_compra / 100, "isento": False, "fonte": "Tesouro Transparente"},
        {"produto": "CDB 112% do CDI", "tipo": "pos", "taxa": projected_cdi * 1.12,
         "isento": False, "fonte": "ilustrativo"},
        {"produto": "LCI 94% do CDI (isenta)", "tipo": "pos", "taxa": projected_cdi * .94,
         "isento": True, "fonte": "ilustrativo"},
        {"produto": "CDB 100% do CDI", "tipo": "pos", "taxa": projected_cdi,
         "isento": False, "fonte": "referência"},
    ]
    for item in catalogue:
        item["cdi_equivalente"] = round(cdi_equivalent(item["taxa"], horizon_years, item["isento"],
                                                       projected_cdi, tax) * 100, 2)
        item["taxa_bruta_aa"] = round(item["taxa"] * 100, 2)
        item.pop("taxa")

    ranking = pd.DataFrame(catalogue).sort_values("cdi_equivalente", ascending=False)
    breakeven = implied_inflation(curve)

    output.mkdir(parents=True, exist_ok=True)
    ranking.to_csv(output / "cdi_equivalent_ranking.csv", index=False)
    breakeven.to_csv(output / "implied_inflation.csv", index=False)
    summary = {
        "status": "viability_probe_not_an_engine",
        "source": "Tesouro Transparente, public and unauthenticated",
        "as_of": as_of.date().isoformat(),
        "titles_on_curve": int(len(curve)),
        "horizon_years": horizon_years,
        "implied_cdi_from_curve": round(projected_cdi * 100, 3),
        "implied_cdi_anchor": anchor.vencimento.date().isoformat(),
        "note": ("The implied CDI is read from the fixed-rate bond nearest the horizon. It is not a "
                 "forecast: it is the average CDI at which the fixed-rate bond breaks even, which is "
                 "the bet the client takes or declines."),
        "limitations": [
            "Bank quotes above are illustrative. CDB, LCI and LCA rates have no public source and "
            "depend on a commercial arrangement with the broker.",
            "Credit risk is not priced here; FGC coverage and issuer limits are separate constraints.",
            "The fixed-rate bond carries a term premium, so reading it as a pure CDI expectation "
            "overstates the implied CDI by that premium.",
            "Custody and platform fees are not deducted in this probe.",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"summary": summary, "ranking": ranking, "breakeven": breakeven, "curve": curve}


def main() -> None:
    parser = argparse.ArgumentParser(description="Viability probe for the fixed-income comparison axis.")
    parser.add_argument("--output", default="artifacts/fixed_income_probe")
    parser.add_argument("--cache", default="data/tesouro_direto_precos_taxas.csv")
    parser.add_argument("--horizon-years", type=float, default=3.0)
    args = parser.parse_args()
    result = run(Path(args.output), Path(args.cache), args.horizon_years)
    summary = result["summary"]
    print(f"Curva de {summary['as_of']} · {summary['titles_on_curve']} títulos vivos")
    print(f"CDI implícito para {args.horizon_years:g} anos: {summary['implied_cdi_from_curve']:.2f}% "
          f"(âncora {summary['implied_cdi_anchor']})\n")
    print("=== EIXO ÚNICO: % DO CDI LÍQUIDO EQUIVALENTE ===")
    print(result["ranking"].to_string(index=False))
    print("\n=== INFLAÇÃO IMPLÍCITA POR PRAZO ===")
    print(result["breakeven"].to_string(index=False))


if __name__ == "__main__":
    main()
