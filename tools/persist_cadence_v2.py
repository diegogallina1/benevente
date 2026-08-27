"""Persist the per-profile cadence study under the frozen v2 ladder.

The figures on the offices page — quarterly reselection costs 2.90 points a
year on the five-name profile and is indistinguishable from zero on the
twelve-name one — were produced by an inline probe and quoted from the
transcript. A published number whose only source is a conversation is not
auditable, which is the one property this project cannot waive. This runs the
same computation and writes it where a reader can diff it.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import sys

import pandas as pd

# Rodado como script, o Python põe tools/ no sys.path, não a raiz do
# repositório — então os módulos de pesquisa que vivem na raiz não são
# encontrados. Sob pytest isso não aparece, porque o pytest insere a raiz
# sozinho: o teste passa e o script quebra, que foi exatamente o que houve.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from annual_walk_forward import BrazilianTaxModel
from profile_ladder_v2 import LADDER_V2, domestic_protocol
from research_global_sleeve import build_global_engine
from research_cadence_and_exemption import CADENCES, period_taxes, _calendar_years, _cagr

OUT = ROOT / "artifacts" / "cadence_v2_profiles"


def main() -> None:
    engine, _ = build_global_engine()
    tax = BrazilianTaxModel()
    rows = []
    for profile in LADDER_V2:
        base = domestic_protocol(profile, 2015, 2026)
        annual_cagr = None
        for name, months in CADENCES.items():
            results, _, _ = engine.run(replace(base, rebalance_months=months))
            taxed = period_taxes(results, tax, use_exemption=False)
            net = _calendar_years(taxed, "net_return")
            cagr = _cagr(net)
            if annual_cagr is None:
                annual_cagr = cagr
            rows.append({
                "perfil": profile, "cadencia": name, "meses": months,
                "top_assets": base.top_assets,
                "cagr_liquido": round(cagr, 6),
                "vs_anual_pp": round((cagr - annual_cagr) * 100, 4),
                "anos": int(len(net)),
            })
    frame = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT / "cadence_by_profile.csv", index=False)
    (OUT / "summary.json").write_text(json.dumps({
        "status": "retrospective_research_only",
        "note": ("Domestic book of each declared profile, cadence varied, everything else fixed. "
                 "No difference is individually significant at eleven paired years; what holds is "
                 "the monotone pattern in both directions."),
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(frame.to_string(index=False))


if __name__ == "__main__":
    main()
