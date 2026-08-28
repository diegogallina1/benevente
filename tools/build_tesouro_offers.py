# -*- coding: utf-8 -*-
"""A grade do Tesouro Direto de hoje, na régua do catálogo.

O catálogo de renda fixa diz, na própria documentação, que a grade é do
escritório porque "as taxas mudam por dia, por faixa e por segmento, e nenhuma
fonte pública as arquiva". Isso vale para captação bancária: CDB, LCI e LCA são
por distribuidor e ficam atrás de login. Não vale para título público, que o
Tesouro Transparente publica todo dia útil, aberto, com preço e taxa por papel.

Este programa preenche essa metade. Ele lê o mesmo arquivo diário que
``tesouro_selic_series`` já usa para reconstruir o caixa, pega a data mais
recente, e escreve os papéis disponíveis no formato que o catálogo lê. A partir
daí a comparação é a mesma para todos: rendimento líquido anualizado depois de
imposto, IOF e custódia.

Três conversões que precisam estar declaradas, porque o arquivo não vem pronto:

* **Tesouro Selic** é publicado como ágio ou deságio sobre a Selic, e o catálogo
  espera um múltiplo do índice. A conversão é ``1 + spread / selic``, que é
  exata quando a Selic realizada é a usada na comparação e aproximada quando
  não é. O erro é de segunda ordem e some na terceira casa.
* **Prefixado** vem como taxa ao ano e entra direto.
* **IPCA+** vem como o cupom real, que é exatamente o que o catálogo chama de
  ``rate`` para esse índice.

A custódia da B3 entra em 0,20% ao ano. A isenção dos primeiros dez mil reais
não é aplicada, pela mesma razão que ``tesouro_selic_series`` não aplica: ela
depende do saldo de quem investe, e o catálogo compara papéis, não pessoas.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tesouro_selic_series import download  # noqa: E402

DESTINO = ROOT / "data" / "ofertas_tesouro.json"
#: Custódia da B3 sobre título público, tabela vigente.
CUSTODIA = 0.0020
#: O Tesouro vende frações a partir de 1% do papel.
FRACAO_MINIMA = 0.01

#: Como cada família do arquivo vira índice do catálogo. Fora daqui o programa
#: não adivinha: papel desconhecido é ignorado e contado no relatório, para que
#: uma família nova apareça como número em vez de sumir em silêncio. O IGPM+ fica
#: de fora de propósito, porque o catálogo não tem esse índice e converter para
#: IPCA seria trocar um número medido por um palpite.
FAMILIAS = {
    "Tesouro Selic": "Selic",
    "Tesouro Prefixado": "prefixado",
    "Tesouro Prefixado com Juros Semestrais": "prefixado",
    "Tesouro IPCA+": "IPCA+",
    "Tesouro IPCA+ com Juros Semestrais": "IPCA+",
    "Tesouro Educa+": "IPCA+",
    "Tesouro RendA+": "IPCA+",
    "Tesouro Renda+ Aposentadoria Extra": "IPCA+",
}


def grade(frame: pd.DataFrame, selic_anual: float) -> tuple[list[dict], str, dict]:
    """Os papéis à venda na data mais recente do arquivo."""
    f = frame.rename(columns=lambda c: c.strip())
    f["Data Base"] = pd.to_datetime(f["Data Base"], dayfirst=True)
    f["Data Vencimento"] = pd.to_datetime(f["Data Vencimento"], dayfirst=True)
    dia = f["Data Base"].max()
    hoje = f[f["Data Base"] == dia].copy()

    # Taxa de compra zerada significa papel fora de venda naquele dia. Ele
    # continua sendo negociado na recompra, mas não é oferta.
    hoje = hoje[hoje["Taxa Compra Manha"].fillna(0) > 0]
    hoje = hoje[hoje["Data Vencimento"] > dia]

    itens, ignorados = [], {}
    for _, linha in hoje.sort_values("Data Vencimento").iterrows():
        familia = str(linha["Tipo Titulo"]).strip()
        indice = FAMILIAS.get(familia)
        if indice is None:
            ignorados[familia] = ignorados.get(familia, 0) + 1
            continue
        taxa = float(linha["Taxa Compra Manha"]) / 100.0
        if indice == "Selic":
            # Ágio ou deságio sobre a Selic, trazido para múltiplo do índice.
            rate = 1.0 + taxa / selic_anual
        else:
            rate = taxa
        pu = float(linha["PU Compra Manha"])
        itens.append({
            "name": f"{familia} {linha['Data Vencimento'].year}",
            "kind": "TESOURO",
            "issuer": "Tesouro Nacional",
            "conglomerate": "Tesouro Nacional",
            "index": indice,
            "rate": round(rate, 6),
            "maturity": linha["Data Vencimento"].date().isoformat(),
            "minimum_brl": round(pu * FRACAO_MINIMA, 2),
            "daily_liquidity": True,   # recompra diária garantida pelo Tesouro
            "custody_fee_annual": CUSTODIA,
        })
    return itens, dia.date().isoformat(), ignorados


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--atualizar", action="store_true",
                   help="baixa o arquivo do Tesouro Transparente de novo")
    p.add_argument("--selic", type=float, default=0.0937,
                   help="Selic anual usada para converter o ágio do Tesouro Selic")
    args = p.parse_args()

    bruto = download(force=args.atualizar)
    itens, dia, ignorados = grade(bruto, args.selic)
    DESTINO.write_text(json.dumps(
        {"source": "Tesouro Transparente, preços e taxas do Tesouro Direto",
         "reference_date": dia, "selic_annual_used": args.selic,
         "custody_fee_annual": CUSTODIA, "products": itens},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{DESTINO.relative_to(ROOT)}: {len(itens)} papéis à venda em {dia}")
    for fam, n in sorted(ignorados.items()):
        print(f"  família não mapeada, ignorada: {fam} ({n})")


if __name__ == "__main__":
    main()
