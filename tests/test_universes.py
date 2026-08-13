import pandas as pd
import pytest

from universes import load_universe_snapshot


def test_universe_snapshot_is_dated_at_or_before_decision_date(tmp_path):
    path = tmp_path / "universe.csv"
    pd.DataFrame([
        {"ticker": "PETR4.SA", "asset_class": "equity", "observed_at": "2026-08-10", "source": "B3 export", "active": "true"},
        {"ticker": "OLD3.SA", "asset_class": "equity", "observed_at": "2026-08-10", "source": "B3 export", "active": "false"},
    ]).to_csv(path, index=False)
    universe = load_universe_snapshot(path, pd.Timestamp("2026-08-12"))
    assert universe.ticker.tolist() == ["PETR4.SA"]


def test_universe_snapshot_rejects_future_observation(tmp_path):
    path = tmp_path / "future.csv"
    pd.DataFrame([
        {"ticker": "PETR4.SA", "asset_class": "equity", "observed_at": "2026-08-13", "source": "B3 export", "active": "true"},
    ]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="after the decision date"):
        load_universe_snapshot(path, pd.Timestamp("2026-08-12"))
