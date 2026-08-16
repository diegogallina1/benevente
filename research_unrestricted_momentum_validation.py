"""Independent stress checks for the pre-existing unrestricted momentum rule."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

from research_unrestricted_signal_grid import evaluate, metrics
from total_return_adapter import load_total_return_export

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "unrestricted_momentum_validation_20260813"
RULE = ("momentum", 252, 2.0, 1.0)


def cagr(values: pd.Series) -> float:
    return float((1 + values).prod()) ** (1 / len(values)) - 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data, _ = load_total_return_export(ROOT / "data/prices_yahoo_adjusted_total_return_2013_2025.csv", ROOT / "data/yahoo_adjusted_total_return_2013_2025_manifest.json")
    annual = evaluate(data.set_index("date"), "momentum_12m_squared_inverse_volatility", *RULE)
    annual.to_csv(OUT / "annual.csv", index=False)
    rows = []
    for label, start, end in (("2015-2017", 2015, 2017), ("2018-2020", 2018, 2020),
                              ("2021-2023", 2021, 2023), ("2024-2025", 2024, 2025)):
        subset = annual[(annual.year >= start) & (annual.year <= end)]
        row = {"period": label, **metrics(subset)}
        for multiplier in (1, 2, 4, 8):
            stressed = subset.gross_return - .0015 * multiplier * subset.turnover
            row[f"cagr_cost_x{multiplier}"] = cagr(stressed)
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "windows_and_costs.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
