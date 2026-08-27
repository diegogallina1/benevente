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

ROOT = Path(__file__).resolve().parents[1]
FONTE = ROOT / "artifacts" / "forecast_calibration_v1" / "calibration.json"
DESTINO = ROOT / "web" / "calibracao.json"

CAMPOS = ("year", "p10", "p50", "p90", "realised", "inside")


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
