"""Demonstra o catálogo: a ordem que a taxa anunciada sugere e a que a lei impõe.

Roda a grade de exemplo, mostra o ranking por rendimento líquido ao lado da
taxa anunciada, e aloca um caixa respeitando o teto do FGC e a reserva de
liquidez que a camada de proteção exige. Tudo o que sai daqui é aritmética
declarada sobre uma grade datada — não há previsão em lugar nenhum.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json

from fixed_income_catalog import allocate, load_catalog, rank

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / "data" / "catalogo_renda_fixa_exemplo.json"
OUT = ROOT / "artifacts" / "fixed_income_v1"


def main() -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    reference = date.fromisoformat(payload["referencia"])
    cdi = float(payload["cdi_anual_premissa"])
    products = load_catalog(CATALOG)

    ordered = rank(products, reference, cdi)
    print(f"Grade de {reference} · CDI premissa {cdi*100:.2f}% a.a. · {len(products)} produtos\n")
    print("A coluna '% CDI bruto' compara o líquido do produto com o índice CDI cheio,")
    print("que é o comparador do site — e que nenhum investidor recebe, porque o índice")
    print("não paga imposto. É a leitura que mostra quanto da taxa anunciada sobrevive.\n")
    print(f"{'produto':<36}{'anunciado':>11}{'líquido':>10}{'% CDI bruto':>13}{'IR':>7}  cobertura")
    for row in ordered:
        anunciado = f"{row['gross_annual']*100:.2f}%"
        print(f"{row['product']:<36}{anunciado:>11}{row['net_annual']*100:>9.2f}%"
              f"{row['net_over_cdi']*100:>12.1f}%{row['tax_rate']*100:>6.1f}%  "
              f"{'FGC' if row['fgc_covered'] else row['regime'].split()[0]}")

    plano = allocate(products, 600_000, reference, cdi, liquid_floor_brl=150_000)
    print(f"\nAlocação de R$ {plano['amount_brl']:,.0f} com reserva líquida de "
          f"R$ {plano['liquid_reserve_requested_brl']:,.0f}:")
    for a in plano["allocations"]:
        print(f"  R$ {a['amount_brl']:>10,.0f}  {a['product']:<36} {a['conglomerate']:<18}"
              f"{a['net_annual']*100:>6.2f}% líq.")
    for r in plano["rejected"]:
        print(f"  {'—':>13}  {r['product']:<36} recusado: {r['reason']}")
    print(f"\n  carteira de caixa: {plano['blended_net_annual']*100:.2f}% líquido "
          f"({plano['blended_over_cdi']*100:.1f}% do CDI) · não alocado R$ {plano['unallocated_brl']:,.0f}")
    print(f"  FGC por conglomerado: {plano['fgc']['per_conglomerate']}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "ranking_and_allocation.json").write_text(json.dumps({
        "status": "demonstration_only",
        "warning": payload["_aviso"],
        "reference": str(reference),
        "cdi_annual_assumption": cdi,
        "ranking": ordered,
        "allocation": plano,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
