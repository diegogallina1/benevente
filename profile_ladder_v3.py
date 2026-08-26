"""Política v3: a escada da v2 com um caixa que existe.

A v2 declarou três perfis e congelou tudo o que os define — orçamento de renda
variável, número de emissores, teto setorial, fração global e a camada de
proteção. Um único componente ficou sendo um índice em vez de um instrumento: o
caixa, declarado como 100% do CDI capitalizado diariamente. O CDI não tem
custódia, não tem spread de compra e venda e não tem rolagem. Ninguém o compra.

A v3 muda exatamente uma coisa: o caixa passa a ser Tesouro Selic, reconstruído
da fonte primária e líquido de custódia e de giro. Nenhum parâmetro de seleção,
de risco ou de alocação muda. Isso é deliberado — uma versão que mexesse em
várias coisas ao mesmo tempo não permitiria atribuir nada ao que mudou.

Duas consequências ficam registradas porque seria mais confortável não registrar:

* O retorno de cada perfil **cai** entre 0,07 e 0,17 ponto ao ano, porque o
  instrumento rende menos que o índice. Os números da v2 eram levemente
  otimistas nessa parcela.
* A contagem prospectiva **não recomeça**. A amostra confirmatória da v2 começa
  no primeiro pregão de 2027 e nenhuma observação prospectiva foi consumida até
  aqui: em agosto de 2026 não existe um único dia de amostra confirmatória
  gasto. Se existisse, trocar de política obrigaria a zerar a contagem, e a data
  de início da v3 seria outra. Fica escrito para que a regra valha da próxima
  vez, quando for cara.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import argparse
import hashlib
import json

from profile_ladder import CODE_INPUTS, MAXIMUM_NAMES_PER_SECTOR, FACTOR
from profile_ladder_v2 import (CONFIRMATORY_FROM_YEAR, GLOBAL_FRACTION, LADDER_V2, _issuer_cap,
                               domestic_protocol, file_sha256, resolve_approver)
from profile_intrayear_risk import FIXED_OVERLAY
from research_global_sleeve import GLOBAL_INPUTS, GLOBAL_TICKER

ROOT = Path(__file__).resolve().parent
POLICY = "benevente_profile_ladder_v3"
SUPERSEDES = "benevente_profile_ladder_v2"
LADDER_V3 = LADDER_V2

#: Insumos da v3: os mesmos da v2, com o painel de caixa real no lugar do painel
#: cujo caixa era índice — e com a série do Tesouro Selic que o produz.
V3_INPUTS = {
    **GLOBAL_INPUTS,
    "prices": ROOT / "data" / "prices_b3_real_cash_2011_2025.csv",
    "total_return_manifest": ROOT / "data" / "prices_b3_real_cash_2011_2025_manifest.json",
    "cash_series": ROOT / "data" / "tesouro_selic_cash_index.csv",
    "cash_series_manifest": ROOT / "data" / "tesouro_selic_cash_index_manifest.json",
}
V3_CODE = [*CODE_INPUTS, ROOT / "profile_ladder_v2.py", ROOT / "profile_ladder_v3.py",
           ROOT / "tesouro_selic_series.py"]


def register(output: Path, approved_by: str | None = None) -> dict:
    approver, approval_source = resolve_approver(approved_by)
    payload = {
        "policy": POLICY,
        "approved_by": approver,
        "approval_source": approval_source,
        "supersedes": SUPERSEDES,
        "status": "registered_not_prospectively_validated",
        "registered_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "confirmatory_sample_starts": f"first B3 trading session of {CONFIRMATORY_FROM_YEAR}",
        "confirmatory_count_rationale": (
            "A contagem não recomeça porque nenhuma observação prospectiva foi consumida: a amostra "
            "confirmatória da v2 começa no primeiro pregão de 2027 e esta versão é registrada em 2026. "
            "Se algum dia da amostra já tivesse sido gasto, trocar de política obrigaria a zerar a "
            "contagem e a v3 começaria depois. A regra é essa e está escrita antes de custar caro."
        ),
        "selection_method": "declared, not searched",
        "signal_family": FACTOR,
        "review_frequency": "annual",
        "maximum_names_per_sector": MAXIMUM_NAMES_PER_SECTOR,
        "change_from_previous": {
            "what_changed": "apenas o instrumento de caixa",
            "from": "índice: 100% do CDI capitalizado diariamente, série 12 do Banco Central",
            "to": ("instrumento: Tesouro Selic do arquivo diário do Tesouro Transparente, líquido da "
                   "custódia da B3 na tabela histórica (0,30% a.a. até 2018, 0,25% até 2021, 0,20% "
                   "depois) e do spread de compra e venda cobrado em cada rolagem"),
            "what_did_not_change": ("orçamento de renda variável, número de emissores, teto por emissor, "
                                    "teto setorial, família de fatores, cadência anual, fração global e "
                                    "todos os parâmetros da camada de proteção"),
            "measured_consequence": ("o retorno de cada perfil cai entre 0,07 e 0,17 ponto ao ano; o "
                                     "excesso sobre o caixa sobe entre 0,08 e 0,18, porque a régua é "
                                     "100% caixa e a carteira não é"),
            "defect_repaired": ("a coluna de caixa do painel anterior é plana até 2012 — sem dado. A "
                                "escada avalia a partir de 2015 e não era afetada; a busca aninhada "
                                "arquivada, sim. A série do Tesouro Selic é real desde 2010."),
        },
        "cash_sleeve": {
            "instrument": "Tesouro Selic (LFT) via Tesouro Direto",
            "source": "https://www.tesourotransparente.gov.br/ckan/dataset/taxas-dos-titulos-ofertados-pelo-tesouro-direto",
            "holding_rule": "vencimento mais curto com pelo menos 180 dias restantes, rolado ao cair abaixo disso",
            "custody_fee_annual_by_period": {"até 2018": 0.0030, "2019-2021": 0.0025, "2022+": 0.0020},
            "exemption_first_10k_applied": False,
            "why_not_a_bank_product": (
                "Um CDB a 118% do CDI entrega perto de 101% dele depois da tabela regressiva, e depende "
                "de emissor, de faixa e de grade que nenhuma fonte pública arquiva. Declarar como caixa "
                "um produto cuja série histórica não existe seria inventar história. O catálogo de renda "
                "fixa com rendimento líquido e limite do FGC é ferramenta de alocação do escritório, "
                "não insumo desta política."
            ),
        },
        "global_sleeve": {
            "instrument": GLOBAL_TICKER,
            "share_of_equity_budget": GLOBAL_FRACTION,
            "status": "declared exposure, never selected; no CVM filing and no fundamental screen",
            "unhedged_currency_warning": (
                "About a third of this instrument's return over 2015-2025 came from BRL depreciation, "
                "not from the American market. It is an unhedged long dollar position and must be "
                "described as one."
            ),
        },
        "intrayear_overlay": {
            "config": {k: getattr(FIXED_OVERLAY, k) for k in
                       ("alert_drawdown", "severe_drawdown", "alert_volatility", "severe_volatility",
                        "recovery_days", "cost_bps", "volatility_window", "peak_window")},
            "applies_to": "domestic sleeve only",
            "why": ("The fund is held because it does not follow the Ibovespa. Cutting it on a domestic "
                    "stress signal sells the one asset the signal does not apply to."),
            "liquidity_requirement": (
                "A camada move exposição para o caixa dentro do ano, então o caixa precisa liquidar em "
                "D+0. O Tesouro Selic atende; um papel de prazo travado, não. É uma restrição da "
                "política, não uma preferência de alocação."
            ),
        },
        "trials_disclosure": (
            "Nenhuma busca foi feita para esta versão. O instrumento de caixa não foi escolhido entre "
            "candidatos por desempenho: foi escolhido por ser comprável e por ter série primária "
            "publicada. A troca foi medida depois de decidida, e o resultado é pior em retorno."
        ),
        "profiles": {
            profile: {
                "maximum_equity_weight": item["maximum_equity_weight"],
                "top_assets": item["top_assets"],
                "maximum_asset_weight": _issuer_cap(item["maximum_equity_weight"], item["top_assets"]),
                "domestic_budget_solved": round(domestic_protocol(profile, 2015, 2026).maximum_equity_weight, 6),
                "global_share_of_portfolio": round(item["maximum_equity_weight"] * GLOBAL_FRACTION, 6),
                "rationale": item["rationale"],
            }
            for profile, item in LADDER_V3.items()
        },
        "inputs": {name: file_sha256(path) for name, path in V3_INPUTS.items()},
        "code": {path.name: file_sha256(path) for path in V3_CODE},
        "success_criterion": {
            "minimum_years": 3,
            "must_beat_cash_instrument_after_tax": True,
            "must_beat_investable_market_etf": True,
            "profile_ordering_must_hold": "conservador <= equilibrado <= arrojado in realised risk and return",
            "falsification": (
                "A profile that fails to clear its own declared cash instrument after tax over the full "
                "prospective window, or a ladder whose realised risk ordering inverts, refutes the policy."
            ),
        },
        "non_negotiable_gates": {
            "no_parameter_change_after_sample_start": True,
            "in_sample_window_is_exploratory": "2015-2025",
            "equity_tax_apurado_por_lote": True,
            "intrayear_tax_reconciled_with_broker_note": False,
        },
    }
    payload["registration_sha256"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--register", action="store_true", help="congela a política e escreve o registro")
    parser.add_argument("--approved-by", default=None)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "data" / "benevente_profile_ladder_v3_registration.json")
    args = parser.parse_args()
    if not args.register:
        raise SystemExit("Nada a fazer sem --register: registrar uma política é um ato deliberado.")
    payload = register(args.output, args.approved_by)
    print(f"{payload['policy']} registrada por {payload['approved_by']} em {payload['registered_at']}")
    print(f"substitui {payload['supersedes']} · sha256 {payload['registration_sha256']}")
    print(f"amostra confirmatória: {payload['confirmatory_sample_starts']}")


if __name__ == "__main__":
    main()
