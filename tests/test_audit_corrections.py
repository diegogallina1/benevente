"""Regression tests for the corrections raised by the methodology audit."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from annual_walk_forward import (
    BrazilianTaxModel,
    apply_annual_taxes,
    realised_returns_with_delisting,
    unconstrained_long_only_mvo,
    _execution_cost_brl,
)
from build_b3_total_return_panel import (
    adjust_for_corporate_actions,
    confirm_provider_events,
    detect_corporate_actions,
)
from cvm_itr import _accumulated_only
from multiple_testing import deflated_sharpe, probability_of_backtest_overfitting


def _sessions(count: int, start: str = "2020-01-02") -> pd.DatetimeIndex:
    return pd.bdate_range(start, periods=count)


def test_delisted_position_is_liquidated_into_cash_not_frozen_at_zero():
    index = _sessions(6)
    prices = pd.DataFrame({
        "ALIVE": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
        "DELISTED": [10.0, 9.0, 8.0, np.nan, np.nan, np.nan],
        "TITULO_CDI": [100.0, 100.1, 100.2, 100.3, 100.4, 100.5],
    }, index=index)
    returns = realised_returns_with_delisting(prices)
    cash = returns["TITULO_CDI"]
    # Before the delisting the name keeps its own return.
    assert returns.loc[index[1], "DELISTED"] == pytest.approx(-0.1)
    # Afterwards the proceeds earn the defensive sleeve, not a zero return.
    assert returns.loc[index[3:], "DELISTED"].tolist() == pytest.approx(cash.loc[index[3:]].tolist())
    assert (returns.loc[index[3:], "DELISTED"] > 0).all()


def test_delisting_no_longer_truncates_the_holding_year_for_every_asset():
    index = _sessions(6)
    prices = pd.DataFrame({
        "ALIVE": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0],
        "DELISTED": [10.0, 9.0, np.nan, np.nan, np.nan, np.nan],
        "TITULO_CDI": [100.0, 100.1, 100.2, 100.3, 100.4, 100.5],
    }, index=index)
    returns = realised_returns_with_delisting(prices)
    # The old `dropna()` kept a single row here and silently deleted the rest
    # of the holding period for the whole book.
    assert len(returns) == len(index) - 1
    assert returns["ALIVE"].add(1).prod() == pytest.approx(1.5)


def test_neutral_mvo_comparator_is_not_the_candidate_rule():
    generator = np.random.default_rng(7)
    index = _sessions(260)
    history = pd.DataFrame({
        "AAAA": generator.normal(.0012, .012, len(index)),
        "BBBB": generator.normal(.0004, .020, len(index)),
        "CCCC": generator.normal(.0008, .009, len(index)),
        "TITULO_CDI": np.full(len(index), .0004),
    }, index=index)
    neutral = unconstrained_long_only_mvo(history)
    assert neutral.sum() == pytest.approx(1.0)
    assert (neutral >= -1e-9).all()
    # The five-issuer expected-return rule that the mvo_neutral candidate used
    # would put everything in the single highest trailing mean.
    candidate_pick = history.mean().idxmax()
    assert neutral[candidate_pick] < 1.0 - 1e-6


def test_execution_cost_grows_when_the_same_trade_hits_a_thinner_book():
    target = pd.Series({"AAAA": .5, "TITULO_CDI": .5})
    previous = pd.Series({"AAAA": .0, "TITULO_CDI": 1.0})
    liquid = _execution_cost_brl(target, previous, 1_000_000, {"AAAA": 50_000_000})
    thin = _execution_cost_brl(target, previous, 1_000_000, {"AAAA": 500_000})
    assert thin > liquid > 0


def test_tax_is_charged_on_the_share_the_next_review_actually_realises():
    results = pd.DataFrame({
        "decision_year": [2020, 2021],
        "net_return": [.30, .10],
        "equity_gain_rate": [.30, .10],
        "cash_weight": [.0, .0],
        "turnover": [1.0, 2.0],
        "cdi_net_return": [.05, .05],
        "mvo_eligible_net_return": [.20, .10],
        "mvo_equity_gain_rate": [.20, .10],
        "mvo_cash_weight": [.0, .0],
        "mvo_turnover": [1.0, 2.0],
    })
    taxed = apply_annual_taxes(results, BrazilianTaxModel())
    # The 2021 review turns the whole book over, so all of 2020's gain is realised.
    assert taxed.realised_share_for_tax.iloc[0] == pytest.approx(1.0)
    assert taxed.net_return_after_tax.iloc[0] == pytest.approx(.30 - .15 * .30)
    # The final year is charged as a full liquidation rather than deferred.
    assert taxed.realised_share_for_tax.iloc[-1] == pytest.approx(1.0)
    assert (taxed.net_return_after_tax <= taxed.net_return).all()
    assert taxed.cdi_net_return_after_tax.iloc[0] == pytest.approx(.05 * (1 - .175))


def test_a_crash_is_not_mistaken_for_a_split():
    index = _sessions(20)
    prices = pd.Series(100.0, index=index)
    # Halves for one session, then recovers: a squeeze, not a rescaling.
    prices.iloc[10] = 50.0
    assert detect_corporate_actions(prices).empty


def test_a_persistent_rescaling_is_detected_and_back_adjusted():
    index = _sessions(20)
    prices = pd.Series([100.0] * 10 + [50.0] * 10, index=index)
    actions = detect_corporate_actions(prices)
    assert len(actions) == 1
    assert actions.iloc[0].applied_factor == pytest.approx(2.0)
    adjusted = adjust_for_corporate_actions(prices, actions)
    assert adjusted.pct_change().abs().max() < 1e-9


def test_provider_split_event_without_a_price_move_is_rejected():
    index = _sessions(20)
    prices = pd.Series(np.linspace(17.0, 17.5, 20), index=index)
    events = pd.DataFrame({"date": [index[10]], "value": [5.0]})
    # A ticker conversion is filed as a split but the B3 series restarts on the
    # post-event base; applying the factor would corrupt a clean history.
    assert confirm_provider_events(prices, events).empty


def test_quarterly_row_is_dropped_so_the_ttm_bridge_uses_accumulated_periods():
    frame = pd.DataFrame({
        "CD_CONTA": ["3.05", "3.05"],
        "ORDEM_EXERC": ["ÚLTIMO", "ÚLTIMO"],
        "DT_INI_EXERC": ["2018-01-01", "2018-07-01"],
        "VL_CONTA": [31_878_591.0, 13_017_029.0],
    })
    kept = _accumulated_only(frame)
    assert len(kept) == 1
    assert kept.iloc[0].VL_CONTA == pytest.approx(31_878_591.0)


def test_deflated_sharpe_falls_as_the_number_of_trials_grows():
    generator = np.random.default_rng(11)
    returns = pd.Series(generator.normal(.12, .13, 15))
    few = deflated_sharpe(returns, generator.normal(.3, .4, 5))
    many = deflated_sharpe(returns, generator.normal(.3, .4, 400))
    assert many.expected_maximum_sharpe_under_null > few.expected_maximum_sharpe_under_null
    assert many.deflated_sharpe_probability < few.deflated_sharpe_probability


def test_overfitting_probability_is_high_when_trials_are_pure_noise():
    generator = np.random.default_rng(3)
    trials = pd.DataFrame(generator.normal(0, .1, (48, 24)))
    report = probability_of_backtest_overfitting(trials, subsets=8)
    assert report["splits_evaluated"] == report["expected_splits"]
    assert report["probability_of_backtest_overfitting"] > .3
