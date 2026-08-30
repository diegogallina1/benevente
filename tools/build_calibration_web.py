# -*- coding: utf-8 -*-
"""Publica a calibração do forecast para o site.

O artefato completo tem o método, as sementes e a justificativa. O site precisa
de oito linhas por perfil e três números de resumo. Este programa extrai só isso
— e um teste confere que o que está publicado é o que o artefato diz, porque
duas cópias do mesmo dado divergem em silêncio.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FONTE = ROOT / "artifacts" / "forecast_calibration_v1" / "calibration.json"
DESTINO = ROOT / "web" / "calibracao.json"

CAMPOS = ("year", "p10", "p50", "p90", "realised", "inside")


#: Abaixo deste peso em ações, o retorno do perfil é dominado pelo caixa.
DOMINADO_POR_CAIXA = 0.20


def nota_do_instrumento(perfil: str, r: dict) -> str:
    """Por que a faixa erra tanto em perfil dominado por caixa.

    A faixa é reamostrada dos retornos diários passados do próprio perfil, e
    esses retornos carregam o nível de Selic que existia então. Num perfil que é
    quase todo caixa, a incerteza que manda é a Selic futura, e reamostrar o
    passado não a captura: entre 2018 e 2025 a Selic foi de dois dígitos a 2% e
    voltou, e o realizado ficou fora da faixa dos dois lados, para baixo
    enquanto ela caía e para cima enquanto subia.

    Isso não é ruído amostral, é o instrumento fora do domínio dele. Ele foi
    construído para perfil com ação suficiente para a variância da ação dominar.
    """
    from profile_ladder_v2 import LADDER_V2
    teto = LADDER_V2.get(perfil, {}).get("maximum_equity_weight", 1.0)
    if teto > DOMINADO_POR_CAIXA:
        return ""
    return (
        f"A faixa deste perfil acertou {r['coverage']['inside']} de "
        f"{r['coverage']['total']}, muito abaixo dos 80% nominais, e isso não é "
        f"azar. Com {teto * 100:.0f}% em ações o retorno é quase todo caixa, e a "
        f"faixa é reamostrada dos retornos passados, que carregam a Selic de "
        f"então. A incerteza que manda aqui é a Selic futura, que este método não "
        f"modela. Entre 2018 e 2025 ela foi de dois dígitos a 2% e voltou, e o "
        f"realizado ficou fora da faixa dos dois lados. Para este perfil, a régua "
        f"não mede: use-a nos perfis com ação suficiente para a variância da ação "
        f"dominar."
    )


def build() -> dict:
    bruto = json.loads(FONTE.read_text(encoding="utf-8"))
    documento = {
        "status": bruto["status"],
        "question": bruto["question"],
        "limitation": bruto["limitation"],
        "block_days": bruto["method"]["block_days"],
        "point_in_time": bruto["method"]["point_in_time"],
        "profiles": {
            perfil: {
                "years": [{c: ano[c] for c in CAMPOS} for ano in r["years"]],
                "inside": r["coverage"]["inside"],
                "total": r["coverage"]["total"],
                "observed": r["coverage"]["observed"],
                "nominal": r["coverage"]["nominal"],
                "standard_error": r["coverage"]["standard_error"],
                "median_bias_pp": r["median_bias_pp"],
                # Quando a cobertura fica muito abaixo do nominal, publicar só o
                # número deixa o leitor achar que foi azar. No caso conhecido não
                # foi: o método não transfere para carteira dominada por caixa.
                "instrument_note": nota_do_instrumento(perfil, r),
            } for perfil, r in bruto["profiles"].items()
        },
    }
    DESTINO.write_text(json.dumps(documento, ensure_ascii=False, separators=(",", ":")) + "\n",
                       encoding="utf-8")
    return documento


def main() -> None:
    documento = build()
    print(f"{DESTINO.relative_to(ROOT)}: {DESTINO.stat().st_size / 1024:.1f} KB")
    for perfil, r in documento["profiles"].items():
        print(f"  {perfil:<13} {r['inside']}/{r['total']} dentro · "
              f"viés da mediana {r['median_bias_pp']:+.2f} pp")


if __name__ == "__main__":
    main()
