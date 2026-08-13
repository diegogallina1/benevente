import pandas as pd

from annual_candidate_experiment import choose_from_training


def result(rows):
    return pd.DataFrame(rows, columns=["decision_year", "net_return", "cdi_net_return", "mvo_eligible_net_return", "turnover"])


def test_candidate_selection_never_uses_holdout_years():
    # The second candidate dominates in 2021--2024 but loses in all training
    # years. Selection must therefore retain the training winner.
    value = result([(2015, .15, .08, .10, .2), (2016, .15, .08, .10, .2), (2017, .15, .08, .10, .2), (2018, .15, .08, .10, .2), (2019, .15, .08, .10, .2), (2020, .15, .08, .10, .2), (2021, -.2, .05, .08, .2)])
    momentum = result([(2015, .06, .08, .10, .2), (2016, .06, .08, .10, .2), (2017, .06, .08, .10, .2), (2018, .06, .08, .10, .2), (2019, .06, .08, .10, .2), (2020, .06, .08, .10, .2), (2021, .9, .05, .08, .2)])
    selected, leaderboard = choose_from_training({"value_quality": value, "momentum_12m": momentum}, 2021)
    assert selected == "value_quality"
    assert leaderboard.iloc[0].candidate == "value_quality"


def test_candidate_selection_retains_baseline_if_no_candidate_beats_both_benchmarks_in_training():
    frame = result([(year, .05, .08, .10, .2) for year in range(2015, 2021)])
    selected, leaderboard = choose_from_training({"momentum_12m": frame, "low_volatility": frame}, 2021)
    assert selected == "value_quality"
    assert not leaderboard.eligible_for_holdout.any()
