import pandas as pd

from config import SystemConfig
from signals import DeterministicSignalEngine


def test_deterministic_signal_engine_is_bounded_and_keeps_cdi_as_residual_signal():
    returns = pd.DataFrame({
        "PETR4.SA": [.01, -.02, .03, .01] * 70,
        "TITULO_CDI": [.001] * 280,
    })
    engine = DeterministicSignalEngine(SystemConfig())
    scores = engine.trailing_risk_adjusted_scores(returns)
    assert scores["TITULO_CDI"] == 1.0
    assert -1.0 <= scores["PETR4.SA"] <= 1.0


def test_deterministic_macro_budget_has_explicit_rate_rules():
    engine = DeterministicSignalEngine(SystemConfig())
    assert engine.macro_budget(.13, .04).equity_allocation_cap == .40
    assert engine.macro_budget(.08, .04).equity_allocation_cap == .80
