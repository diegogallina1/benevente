"""Demonstra o mapa: uma carteira real chega, o perfil declarado é o alvo."""
from __future__ import annotations

from pathlib import Path
import json

from portfolio_mapping import Bucket, Position, Source, map_portfolio

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "portfolio_mapping_v1"


def carteira_exemplo() -> list[Position]:
    """Carteira sintética de demonstração, com os casos que importam."""
    return [
        # já está na cesta do perfil, e no peso
        Position("CURY3", Bucket.ACAO, 44_000, 20_000, Source.B3_INVESTIDOR),
        # está na cesta, mas muito acima do peso, com ganho grande
        Position("WEGE3", Bucket.ACAO, 180_000, 40_000, Source.B3_INVESTIDOR),
        # não está na cesta e tem prejuízo — a venda gera crédito
        Position("MGLU3", Bucket.ACAO, 25_000, 90_000, Source.B3_INVESTIDOR),
        # renda fixa concentrada acima do teto do FGC
        Position("CDB Banco Beta", Bucket.RENDA_FIXA, 310_000, 300_000,
                 Source.OPEN_FINANCE, conglomerate="Beta", days_held=500, liquid=False),
        Position("Tesouro Selic", Bucket.CAIXA, 120_000, 118_000, Source.B3_INVESTIDOR),
        # ativo fora do escopo da política
        Position("Cripto", Bucket.FORA_DO_ESCOPO, 21_000, 30_000, Source.MANUAL),
    ]


def main() -> None:
    books = json.loads((ROOT / "web" / "current_decision_2026_equilibrado.json").read_text(encoding="utf-8"))
    acoes = {h["ticker"]: h["weight"] for h in books["holdings"] if h["ticker"] != "IVVB11"}
    alvo = {"positions": acoes,
            "global_sleeve": next((h["weight"] for h in books["holdings"] if h["ticker"] == "IVVB11"), 0.0),
            "cash": books["cdi_weight"]}

    mapa = map_portfolio(carteira_exemplo(), alvo)
    print(f"Carteira de R$ {mapa['total_brl']:,.0f} contra o perfil equilibrado\n")
    print(f"  já aderente ao perfil: {mapa['alignment']:.1%}")
    print(f"  giro necessário:       R$ {mapa['turnover_brl']:,.0f}")
    print(f"  custo de execução:     R$ {mapa['transition_cost_brl']:,.0f}")
    print(f"  imposto realizado:     R$ {mapa['transition_tax_brl']:,.0f}")
    print(f"  custo total da travessia: R$ {mapa['transition_total_brl']:,.0f} "
          f"({mapa['transition_cost_pct']:.2%} do patrimônio)")
    if mapa["fgc_breaches"]:
        print(f"  ALERTA FGC: {mapa['fgc_breaches']} acima de R$ 250.000 por conglomerado")
    print(f"\n{'ativo':<16}{'ação':<10}{'de':>12}{'para':>12}{'imposto':>11}  observação")
    for m in mapa["moves"]:
        nota = m["notes"][0] if m["notes"] else m["reason"]
        print(f"{m['ticker']:<16}{m['action']:<10}{m['from_brl']:>12,.0f}{m['to_brl']:>12,.0f}"
              f"{m['tax_brl']:>11,.0f}  {nota[:44]}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mapping_example.json").write_text(json.dumps({
        "status": "demonstration_only",
        "warning": "Carteira sintética escrita à mão para exercitar o módulo.",
        "target_profile": "equilibrado", "target_decision": books["decision_date"],
        "mapping": mapa,
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
