"""Apply transparent multipliers to recorded annual rebalance costs."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent
OUT = ROOT / "artifacts" / "cost_stress_20260813"


def cagr(values: pd.Series) -> float:
    return float((1 + values).prod()) ** (1 / len(values)) - 1


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    paths = [
        ROOT / "artifacts/low_volatility_robustness_20260813/lv_eq15_cap100_top5_train_annual.csv",
        ROOT / "artifacts/low_volatility_robustness_20260813/lv_eq15_cap100_top5_holdout_annual.csv",
    ]
    data = pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    rows: list[dict[str, object]] = []
    for multiplier in (1, 2, 4, 8):
        stressed = data.gross_return - data.estimated_cost_rate * multiplier
        for name, mask in (("2015-2020", data.decision_year <= 2020), ("2021-2025", data.decision_year >= 2021)):
            current = data.loc[mask]
            candidate = cagr(stressed[mask])
            mvo = cagr(current.mvo_eligible_net_return)
            cdi = cagr(current.cdi_net_return)
            rows.append({"cost_multiplier": multiplier, "period": name, "candidate_cagr": candidate,
                         "mvo_cagr": mvo, "cdi_cagr": cdi,
                         "excess_mvo_cagr": candidate - mvo, "excess_cdi_cagr": candidate - cdi})
    pd.DataFrame(rows).to_csv(OUT / "low_vol_eq15_cost_stress.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
