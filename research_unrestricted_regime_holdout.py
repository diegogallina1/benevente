"""Select a regime-selection policy before the 2021 holdout."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from research_unrestricted_regime_selection import evaluate, summary

ROOT = Path(__file__).parent
INPUT = ROOT / "artifacts" / "unrestricted_signal_grid_20260813"
OUT = ROOT / "artifacts" / "unrestricted_regime_holdout_20260813"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    annual = pd.concat([pd.read_csv(path) for path in INPUT.glob("*_annual.csv")], ignore_index=True)
    policies = [(objective, window) for objective in ("return", "excess_return", "hit_rate", "information_ratio")
                for window in (None, 2, 3, 5)]
    rows = []
    details = {}
    for objective, window in policies:
        result, _ = evaluate(annual, objective, window)
        name = f"{objective}_{'expanding' if window is None else f'{window}y'}"
        train = result[result.decision_year <= 2020]
        holdout = result[result.decision_year >= 2021]
        rows.append({"policy": name, **{f"train_{k}": v for k, v in summary(train).items()},
                     **{f"holdout_{k}": v for k, v in summary(holdout).items()}})
        details[name] = result
    report = pd.DataFrame(rows)
    # This is the only policy-selection operation: it has access solely to
    # returns through 2020.  The holdout column remains untouched until after.
    report = report.sort_values(["train_excess_cdi", "train_cdi_hit_rate"], ascending=False)
    report.to_csv(OUT / "policy_selection.csv", index=False)
    chosen = report.iloc[0]
    details[str(chosen.policy)].to_csv(OUT / "chosen_policy_annual.csv", index=False)
    conclusion = {"selection_period": "2018-2020", "holdout_period": "2021-2025",
                  "chosen_policy": str(chosen.policy),
                  "train": {key.removeprefix("train_"): float(value) if isinstance(value, float) else value for key, value in chosen.items() if key.startswith("train_")},
                  "holdout": {key.removeprefix("holdout_"): float(value) if isinstance(value, float) else value for key, value in chosen.items() if key.startswith("holdout_")},
                  "passes_holdout": bool(chosen.holdout_excess_cdi > 0)}
    encoded = json.dumps(conclusion, ensure_ascii=False, indent=2, default=lambda value: value.item() if hasattr(value, "item") else str(value))
    (OUT / "conclusion.json").write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
