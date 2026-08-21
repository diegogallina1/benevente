import numpy as np
import pandas as pd

from validate_risk_system import block_monte_carlo


def test_block_monte_carlo_is_reproducible_and_bounded(tmp_path) -> None:
    path = tmp_path / "daily.csv"
    pd.DataFrame({
        "protected_return": np.tile([.001, -.0005, .0008], 30),
        "cdi_daily_return": np.full(90, .0002),
    }).to_csv(path, index=False)
    first = block_monte_carlo(path, seed=123, samples=200)
    second = block_monte_carlo(path, seed=123, samples=200)
    assert first == second
    assert 0 <= first["probability_cagr_above_paired_cdi"] <= 1
    assert first["maximum_drawdown"]["p2_5"] <= first["maximum_drawdown"]["p97_5"]
