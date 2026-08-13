"""Export archived, auditable research curves for the static web viewer.

The static site receives only pre-existing strategy curves.  It never invents
asset-level holdings or uses this export to make a live recommendation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HORIZONS = {"5": "5y", "10": "10y", "15": "15y"}
FILES = {
    "Benevente Quant AI": "results_benevente_quant_ai.csv",
    "MVO clássico": "results_mvo_clássico.csv",
    "CDI": "results_cdi.csv",
    "Ibovespa": "results_ibovespa.csv",
}


def main() -> None:
    exported: dict[str, dict[str, object]] = {}
    for label, folder in HORIZONS.items():
        base = ROOT / "artifacts" / "horizons" / folder
        series: dict[str, list[float]] = {}
        dates: list[str] | None = None
        for name, filename in FILES.items():
            path = base / filename
            if not path.exists():
                continue
            frame = pd.read_csv(path, parse_dates=["date"])
            if frame.empty:
                continue
            wealth = frame["wealth"].astype(float)
            # The first published rebalance is the comparison base (100).
            series[name] = [round(float(value / wealth.iloc[0] * 100), 4) for value in wealth]
            dates = [value.strftime("%Y-%m-%d") for value in frame["date"]]
        if dates is None:
            raise ValueError(f"No archived curves available for {label} years")
        exported[label] = {"dates": dates, "series": series}
    (ROOT / "web" / "horizon_curves.json").write_text(
        json.dumps(exported, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
