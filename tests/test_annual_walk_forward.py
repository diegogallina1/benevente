import pandas as pd
import pytest

from annual_walk_forward import (AnnualWalkForwardConfig, AnnualWalkForwardEngine,
                                 BrazilianTaxModel, apply_annual_taxes,
                                 sector_group, is_unclassified_sector, WEIGHTING_SCHEMES,
                                 RISK_PROFILE_LIMITS, protocol_for_risk_profile,
                                 run_adaptive_factor_walk_forward,
                                 select_factor_out_of_sample)
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from fundamentals import FundamentalSnapshot
from annual_decision_evidence import build_decision_evidence


def old_snapshot() -> FundamentalSnapshot:
    return FundamentalSnapshot(
        ticker="PETR4.SA", as_of_date="2018-12-31", available_date="2019-03-31", sector="Energy",
        is_financial=False, market_cap_brl=10_000_000_000, price_to_earnings=8, price_to_book=1,
        ev_to_ebit=6, free_cash_flow_yield=.08, roe=.16, roic=.15, debt_to_ebitda=1,
        interest_coverage=5, operating_margin=.2, revenue_growth_3y=.1,
        average_daily_value_brl=100_000_000, source="test PIT snapshot",
    )


def test_annual_walk_forward_freezes_then_holds_each_year_without_future_filing():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    results, transitions, holdings = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(
        AnnualWalkForwardConfig(2020, 2023)
    )
    assert results.decision_year.tolist() == [2020, 2021, 2022]
    assert (pd.to_datetime(results.decision_date) < pd.to_datetime(results.holding_end_exclusive)).all()
    assert results.known_snapshot_count.eq(1).all()
    assert not holdings.empty
    assert not transitions.empty
    assert results.net_return.notna().all()
    assert {"mvo_eligible_net_return", "cdi_net_return"}.issubset(results.columns)
    assert {"decision_action", "decision_rationale", "realised_next_year_return", "factor_signal_at_decision", "trailing_12m_return_at_decision"}.issubset(holdings.columns)
    petr4 = holdings[holdings.ticker == "PETR4.SA"]
    assert petr4.decision_rationale.str.contains("point-in-time").all()


def test_last_available_year_is_held_to_the_observed_market_cutoff():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2021-12-30", offline=True)
    results, _, _ = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(
        AnnualWalkForwardConfig(2020, 2022)
    )
    terminal = results.iloc[-1]
    assert terminal.decision_year == 2021
    assert terminal.decision_date == "2021-01-01"
    assert terminal.holding_end_exclusive == "2021-12-31"
    assert terminal.net_return == pytest.approx(terminal.net_return)


def test_annual_walk_forward_uses_only_newest_available_filing_per_ticker():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    older = old_snapshot()
    newer = old_snapshot().model_copy(update={"as_of_date": pd.Timestamp("2019-09-30"),
                                              "available_date": pd.Timestamp("2019-11-01"), "roe": .20})
    results, _, _ = AnnualWalkForwardEngine(prices, [older, newer], config).run(AnnualWalkForwardConfig(2020, 2022))
    assert results.known_snapshot_count.eq(1).all()


def test_annual_walk_forward_rejects_a_period_without_prior_fundamental_evidence():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    future = old_snapshot().model_copy(update={"available_date": pd.Timestamp("2021-12-31")})
    with pytest.raises(ValueError, match="No annual decisions"):
        AnnualWalkForwardEngine(prices, [future], config).run(AnnualWalkForwardConfig(2020, 2021))


def test_factor_selection_uses_only_years_before_the_holdout_cutoff():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    engine = AnnualWalkForwardEngine(prices, [old_snapshot()], config)
    protocol = AnnualWalkForwardConfig(2020, 2024, minimum_factor_training_years=1)
    factor, leaderboard = select_factor_out_of_sample(engine, protocol, training_end_year=2022)
    assert factor in {"value_quality", "momentum_12m", "low_volatility"}
    assert leaderboard.training_years.max() <= 2
    assert set(leaderboard.factor) == {"value_quality", "momentum_12m", "low_volatility"}


def test_adaptive_factor_walk_forward_selects_before_each_unseen_year():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    protocol = AnnualWalkForwardConfig(2020, 2024, minimum_factor_training_years=1)
    results, transitions, holdings, choices = run_adaptive_factor_walk_forward(
        AnnualWalkForwardEngine(prices, [old_snapshot()], config), protocol
    )
    assert results.decision_year.tolist() == [2021, 2022, 2023]
    assert choices.decision_year.tolist() == [2021, 2022, 2023]
    assert choices.selection_end_year_exclusive.tolist() == [2021, 2022, 2023]
    assert not transitions.empty
    assert not holdings.empty
    assert results.opening_wealth_brl.iloc[1] == pytest.approx(results.closing_wealth_brl.iloc[0])


def test_future_prices_do_not_change_an_earlier_january_portfolio():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    protocol = AnnualWalkForwardConfig(2020, 2023)
    engine = AnnualWalkForwardEngine(prices, [old_snapshot()], config)
    original, _, original_holdings = engine.run(protocol)
    altered = prices.copy()
    altered.loc[altered.index >= pd.Timestamp("2021-01-01"), "PETR4.SA"] *= 4
    changed, _, changed_holdings = AnnualWalkForwardEngine(altered, [old_snapshot()], config).run(protocol)
    first_original = original_holdings[original_holdings.decision_year == 2020][["ticker", "weight"]].reset_index(drop=True)
    first_changed = changed_holdings[changed_holdings.decision_year == 2020][["ticker", "weight"]].reset_index(drop=True)
    pd.testing.assert_frame_equal(first_original, first_changed)
    assert original.loc[original.decision_year == 2020, "net_return"].item() == changed.loc[changed.decision_year == 2020, "net_return"].item()


def test_decision_evidence_blocks_a_snapshot_missing_from_the_dated_b3_universe():
    config = SystemConfig()
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    universe = pd.DataFrame([{"decision_date": "2020-01-01", "universe_year": 2020,
                              "ticker": "VALE3.SA", "asset_class": "equity"}])
    mapping = pd.DataFrame([{"universe_year": 2020, "ticker": "VALE3.SA", "mapping_status": "accepted"}])
    evidence, _ = build_decision_evidence(universe, mapping)
    with pytest.raises(ValueError, match="No annual decisions"):
        AnnualWalkForwardEngine(prices, [old_snapshot()], config, evidence).run(AnnualWalkForwardConfig(2020, 2021))


def test_turnover_uses_drifted_weights_after_the_holding_year():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2024-01-10", offline=True)
    base, _, _ = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2023))
    changed_prices = prices.copy()
    changed_prices.loc[(changed_prices.index >= "2020-01-02") & (changed_prices.index < "2021-01-01"), "PETR4.SA"] *= 2
    changed, _, _ = AnnualWalkForwardEngine(changed_prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2023))
    assert base.loc[base.decision_year == 2021, "turnover"].item() != changed.loc[changed.decision_year == 2021, "turnover"].item()


def test_triple_factor_keeps_primary_quality_asset_when_secondary_solvency_is_unavailable():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    snapshot = old_snapshot().model_copy(update={"debt_to_ebitda": None, "interest_coverage": None})
    engine = AnnualWalkForwardEngine(prices, [snapshot], config)
    protocol = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", maximum_equity_weight=.55,
                                       maximum_asset_weight=.12, top_assets=4)
    results, _, holdings = engine.run(protocol)
    assert results.factor.eq("triple_factor").all()
    assert results.target_equity_weight.eq(.12).all()
    assert holdings.loc[holdings.ticker.eq("PETR4.SA"), "eligible_at_decision"].all()


def test_triple_factor_never_exceeds_equity_or_issuer_policy_cap():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    snapshots = [old_snapshot(), old_snapshot().model_copy(update={"ticker": "VALE3.SA"})]
    engine = AnnualWalkForwardEngine(prices, snapshots, config)
    protocol = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", maximum_equity_weight=.60,
                                       maximum_asset_weight=.15, top_assets=4)
    results, _, holdings = engine.run(protocol)
    assert results.target_equity_weight.le(.30 + 1e-8).all()
    equity_holdings = holdings[holdings.ticker.ne("TITULO_CDI")]
    assert equity_holdings.weight.le(.15 + 1e-8).all()


def test_named_risk_profile_sets_guardrails_and_minimum_diversification():
    base = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", top_assets=4)
    protocol = protocol_for_risk_profile(base, "conservador")
    assert protocol.risk_profile == "conservador"
    assert protocol.maximum_equity_weight == RISK_PROFILE_LIMITS["conservador"]["maximum_equity_weight"]
    assert protocol.maximum_asset_weight == RISK_PROFILE_LIMITS["conservador"]["maximum_asset_weight"]
    assert protocol.factor == "triple_factor"
    assert protocol.top_assets == 5
    assert protocol.minimum_equity_positions == 5
    assert protocol.apply_profile_risk_layer


def test_cli_requires_a_hashed_manifest_for_total_return_inputs(monkeypatch):
    import annual_walk_forward
    monkeypatch.setattr("sys.argv", ["annual_walk_forward.py", "--prices", "prices.csv", "--fundamentals", "fundamentals.csv",
                                      "--start-year", "2020", "--end-year", "2022", "--price-basis", "total_return"])
    with pytest.raises(SystemExit, match="2"):
        annual_walk_forward.main()


def test_price_column_resolution_accepts_cvm_suffix_and_canonical_b3_code():
    from annual_walk_forward import _price_column_for_ticker
    columns = pd.Index(["PETR4", "TITULO_CDI"])
    assert _price_column_for_ticker("PETR4.SA", columns) == "PETR4"
    assert _price_column_for_ticker("PETR4", columns) == "PETR4"


def test_walk_forward_matches_cvm_snapshot_ticker_to_canonical_b3_price_column():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    prices = prices.rename(columns={"PETR4.SA": "PETR4"})
    results, _, holdings = AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(
        AnnualWalkForwardConfig(2020, 2022)
    )
    assert not results.empty
    assert holdings.ticker.eq("PETR4.SA").any()


def test_recent_market_sessions_ignores_sparse_holiday_rows_without_filling_prices():
    from annual_walk_forward import _recent_market_sessions
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = pd.DataFrame({"AAA3": [1, 2, None, 3, 4], "BBB3": [1, 2, None, 3, 4],
                           "CCC3": [1, 2, 1, 3, 4], "TITULO_CDI": [1, 1, 1, 1, 1]}, index=dates)
    sessions = _recent_market_sessions(prices, pd.Timestamp("2020-01-06"), minimum_history_days=3)
    assert pd.Timestamp("2020-01-03") not in sessions
    assert sessions.tolist() == [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02"),
                                 pd.Timestamp("2020-01-04"), pd.Timestamp("2020-01-05")]


def test_mvo_comparator_receives_only_assets_that_pass_the_same_screen(monkeypatch):
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2022-01-10", offline=True)
    seen: list[set[str]] = []
    import annual_walk_forward
    original = annual_walk_forward.MeanVarianceOptimizer.optimize
    def capture(self, historical_returns, *args, **kwargs):
        seen.append(set(historical_returns.columns))
        return original(self, historical_returns, *args, **kwargs)
    monkeypatch.setattr(annual_walk_forward.MeanVarianceOptimizer, "optimize", capture)
    AnnualWalkForwardEngine(prices, [old_snapshot()], config).run(AnnualWalkForwardConfig(2020, 2022))
    assert seen and all(columns == {"PETR4.SA", "TITULO_CDI"} for columns in seen)


def _sector_snapshots() -> list[FundamentalSnapshot]:
    """Six issuers in one sector and two, deliberately weaker, outside it.

    The two outsiders are ranked last by construction, so without a limit the
    book is a single-sector book and the test is measuring the limit rather
    than an accident of the synthetic price path.
    """
    concentrated = {"PETR4.SA": "Petróleo e Gás", "VALE3.SA": "Emp. Adm. Part. - Petróleo e Gás",
                    "ITUB4.SA": "Petróleo e Gás", "BBDC4.SA": "Petróleo e Gás",
                    "WEGE3.SA": "Petróleo e Gás", "RENT3.SA": "Emp. Adm. Part. - Petróleo e Gás"}
    outsiders = {"ABEV3.SA": "Bancos", "BBAS3.SA": "Energia Elétrica"}
    snapshots = [old_snapshot().model_copy(update={"ticker": ticker, "sector": sector})
                 for ticker, sector in concentrated.items()]
    snapshots += [old_snapshot().model_copy(update={"ticker": ticker, "sector": sector,
                                                    "roic": .09, "price_to_earnings": 40})
                  for ticker, sector in outsiders.items()]
    return snapshots


def test_holding_company_label_shares_a_concentration_bucket_with_its_operating_sector():
    assert sector_group("Emp. Adm. Part. - Energia Elétrica", "X") == sector_group("Energia Elétrica", "Y")
    assert sector_group("Emp. Adm. Part. - Const. Civil, Mat. Const. e Decoração", "X") ==         sector_group("Construção Civil, Mat. Constr. e Decoração", "Y")
    assert sector_group("Emp. Adm. Part. - Máqs., Equip., Veíc. e Peças", "X") ==         sector_group("Máquinas, Equipamentos, Veículos e Peças", "Y")
    assert sector_group("Bancos", "X") != sector_group("Energia Elétrica", "Y")


def test_unclassified_issuer_never_shares_a_bucket_with_another_unclassified_issuer():
    first = sector_group("Emp. Adm. Part. - Sem Setor Principal", "AAAA3")
    second = sector_group(None, "BBBB3")
    assert first != second
    assert is_unclassified_sector(first) and is_unclassified_sector(second)


def test_sector_cap_drops_only_the_rank_inferior_name_of_a_full_sector():
    ranked = pd.DataFrame({"ticker": list("ABCDEF"),
                           "sector_group": ["oil", "oil", "oil", "bank", "bank", "power"]})
    capped = AnnualWalkForwardEngine._sector_capped(ranked, 2)
    assert capped.ticker.tolist() == ["A", "B", "D", "E", "F"]
    assert AnnualWalkForwardEngine._sector_capped(ranked, None).ticker.tolist() == list("ABCDEF")


def test_sector_limit_replaces_rank_inferior_names_from_a_full_sector():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    engine = AnnualWalkForwardEngine(prices, _sector_snapshots(), config)
    base = dict(factor="triple_factor", maximum_equity_weight=.90, maximum_asset_weight=.20, top_assets=4)
    unlimited, _, _ = engine.run(AnnualWalkForwardConfig(2020, 2023, **base))
    limited, _, _ = engine.run(AnnualWalkForwardConfig(2020, 2023, maximum_names_per_sector=2, **base))
    assert unlimited.largest_sector_positions.eq(4).all()
    assert unlimited.distinct_sectors.eq(1).all()
    assert limited.largest_sector_positions.le(2).all()
    assert limited.distinct_sectors.eq(3).all()
    # The limit removes an exposure, it does not shrink the book: the freed slot
    # goes to the best-ranked name of a sector that still has room.
    assert limited.equity_positions.equals(unlimited.equity_positions)


def test_position_count_tracks_the_eligible_universe_between_floor_and_ceiling():
    protocol = AnnualWalkForwardConfig(2020, 2023, top_assets=20, top_assets_minimum=5,
                                       top_assets_universe_fraction=.15)
    assert protocol.positions_for_universe(27) == 5      # floor binds on a narrow universe
    assert protocol.positions_for_universe(60) == 9
    assert protocol.positions_for_universe(91) == 14
    assert protocol.positions_for_universe(400) == 20    # ceiling binds


def test_unset_selectivity_and_sector_limit_reproduce_the_published_rule():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    engine = AnnualWalkForwardEngine(prices, _sector_snapshots(), config)
    protocol = AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", top_assets=4)
    assert protocol.positions_for_universe(500) == 4
    published, _, _ = engine.run(protocol)
    explicit, _, _ = engine.run(AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", top_assets=4,
                                                        maximum_names_per_sector=None))
    pd.testing.assert_frame_equal(published, explicit)


def test_selectivity_fraction_rejects_a_floor_above_its_ceiling():
    with pytest.raises(ValueError, match="top_assets_minimum"):
        AnnualWalkForwardConfig(2020, 2023, top_assets=5, top_assets_minimum=8,
                                top_assets_universe_fraction=.15)
    with pytest.raises(ValueError, match="top_assets_universe_fraction"):
        AnnualWalkForwardConfig(2020, 2023, top_assets_universe_fraction=0.0)


def _weights(scheme, scores, vols, equity=0.60, cap=0.30):
    return AnnualWalkForwardEngine._confidence_weights(
        pd.Series(scores), equity, cap, volatilities=pd.Series(vols), scheme=scheme)


def test_score_weighting_is_the_default_and_is_unchanged_by_volatility():
    scores = {"A": 2.0, "B": 1.0, "C": 0.0}
    calm = _weights("score", scores, {"A": .10, "B": .50, "C": .90})
    wild = _weights("score", scores, {"A": .90, "B": .50, "C": .10})
    pd.testing.assert_series_equal(calm, wild)
    assert AnnualWalkForwardConfig(2020, 2023).weighting == "score"
    assert calm.A > calm.B > calm.C


def test_equal_weighting_ignores_both_score_and_volatility():
    equal = _weights("equal", {"A": 2.0, "B": 1.0, "C": 0.0}, {"A": .10, "B": .50, "C": .90})
    assert equal.round(10).nunique() == 1
    assert equal.sum() == pytest.approx(.60)


def test_inverse_volatility_sizes_down_the_noisier_name_despite_a_worse_score():
    # The cap is left slack on purpose: with two names inside a tight cap the
    # cap, not the scheme, would decide the book and the test would pass for
    # the wrong reason.
    inverse = _weights("inverse_volatility", {"A": 0.0, "B": 2.0}, {"A": .10, "B": .40}, cap=.55)
    assert inverse.A > inverse.B, "the calm name must carry more of the sleeve"
    assert inverse.A / inverse.B == pytest.approx(4.0)


def test_blend_sits_between_the_two_pure_rules():
    scores, vols = {"A": 0.0, "B": 2.0}, {"A": .10, "B": .40}
    pure_score = _weights("score", scores, vols, cap=.55)
    pure_risk = _weights("inverse_volatility", scores, vols, cap=.55)
    blend = _weights("inverse_volatility_score", scores, vols, cap=.55)
    assert pure_score.A < blend.A < pure_risk.A


def test_a_near_zero_volatility_name_cannot_swallow_the_sleeve():
    inverse = _weights("inverse_volatility", {"A": 1.0, "B": 1.0, "C": 1.0},
                       {"A": 1e-9, "B": .20, "C": .20}, equity=.60, cap=.30)
    assert inverse.A <= .30 + 1e-9
    # With the floor at 5% annualised, A is at most four times B, not a billion.
    assert inverse.A / inverse.B < 5


def test_missing_volatility_is_treated_as_the_noisiest_name():
    inverse = _weights("inverse_volatility", {"A": 1.0, "B": 1.0, "C": 1.0},
                       {"A": float("nan"), "B": .10, "C": .40}, cap=.55)
    assert inverse.A < inverse.B
    assert inverse.A == pytest.approx(inverse.C), "an absent volatility inherits the noisiest observed one"


def test_every_scheme_respects_the_issuer_cap():
    for scheme in WEIGHTING_SCHEMES:
        weights = _weights(scheme, {"A": 5.0, "B": 1.0, "C": 0.0},
                           {"A": .05, "B": .40, "C": .60}, equity=.60, cap=.25)
        assert weights.max() <= .25 + 1e-9, scheme
        assert weights.sum() == pytest.approx(.60), scheme


def test_unsupported_weighting_scheme_is_rejected_at_construction():
    with pytest.raises(ValueError, match="weighting scheme"):
        AnnualWalkForwardConfig(2020, 2023, weighting="risk_parity")


def test_weighting_changes_the_book_but_not_which_names_are_held():
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    engine = AnnualWalkForwardEngine(prices, _sector_snapshots(), config)
    base = dict(factor="triple_factor", maximum_equity_weight=.90, maximum_asset_weight=.30, top_assets=4)
    held = {}
    for scheme in ("score", "equal", "inverse_volatility"):
        _, _, holdings = engine.run(AnnualWalkForwardConfig(2020, 2023, weighting=scheme, **base))
        equity = holdings[holdings.ticker.ne("TITULO_CDI")]
        held[scheme] = set(zip(equity.decision_year, equity.ticker))
    assert held["score"] == held["equal"] == held["inverse_volatility"], "sizing must not change selection"


def _prices_with_global(listed_from: str | None = None) -> pd.DataFrame:
    """Offline panel plus a synthetic B3-listed global ETF column."""
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    prices = PointInTimeDataLoader(config).fetch_prices("2018-01-01", "2023-01-10", offline=True)
    prices = prices.copy()
    # A deterministic, gently rising series that is not a copy of any local name.
    prices["IVVB11"] = 100 * (1 + pd.Series(range(len(prices)), index=prices.index) * .0004)
    if listed_from is not None:
        prices.loc[prices.index < pd.Timestamp(listed_from), "IVVB11"] = float("nan")
    return prices


def _run_global(prices, fraction, snapshots=None, **kwargs):
    config = SystemConfig(initial_portfolio_value_brl=100_000)
    engine = AnnualWalkForwardEngine(prices, snapshots or [old_snapshot()], config)
    protocol = AnnualWalkForwardConfig(
        2020, 2023, factor="triple_factor", maximum_equity_weight=.60, maximum_asset_weight=.30,
        top_assets=4, global_sleeve_ticker="IVVB11" if fraction else None,
        global_sleeve_fraction=fraction, **kwargs)
    return engine.run(protocol)


def test_global_sleeve_is_carved_out_of_the_equity_budget_not_added_to_it():
    # Enough eligible names that the budget is reachable; with a single name
    # the issuer cap decides the sleeve and the carve-out is untestable.
    names = _sector_snapshots()
    domestic, _, domestic_holdings = _run_global(_prices_with_global(), 0.0, snapshots=names)
    global_run, _, holdings = _run_global(_prices_with_global(), .25, snapshots=names)
    assert domestic.target_equity_weight.round(6).eq(.60).all()
    assert global_run.target_equity_weight.round(6).eq(.60).all(), "the budget must not grow"
    sleeve = holdings[holdings.ticker.eq("IVVB11")]
    assert not sleeve.empty, "the declared sleeve must actually be held"
    assert sleeve.weight.round(6).eq(round(.60 * .25, 6)).all()
    # The domestic names give up exactly what the sleeve takes.
    local = holdings[~holdings.ticker.isin(["IVVB11", "TITULO_CDI"])].groupby("decision_year").weight.sum()
    was = domestic_holdings[domestic_holdings.ticker.ne("TITULO_CDI")].groupby("decision_year").weight.sum()
    assert local.round(6).eq(round(.60 * .75, 6)).all()
    assert was.round(6).eq(.60).all()


def test_the_factor_screen_never_reaches_the_declared_sleeve():
    _, _, holdings = _run_global(_prices_with_global(), .25, snapshots=_sector_snapshots())
    sleeve = holdings[holdings.ticker.eq("IVVB11")]
    # It is held, but it never passes an eligibility screen it has no filing for.
    assert not sleeve.eligible_at_decision.fillna(False).any()


def test_a_year_before_the_fund_listed_runs_entirely_domestic():
    # Listing mid-2019: the January 2020 decision has no complete trailing
    # year for the fund, so that year is domestic; later decisions do.
    late, _, holdings = _run_global(_prices_with_global(listed_from="2019-06-01"), .25,
                                    snapshots=_sector_snapshots())
    held = holdings[holdings.ticker.eq("IVVB11")]
    assert 2020 not in set(held.decision_year), "no sleeve without a complete pre-decision lookback"
    assert {2021, 2022} <= set(held.decision_year), "and the sleeve once the history exists"


def test_zero_fraction_reproduces_the_domestic_rule():
    with_column, _, _ = _run_global(_prices_with_global(), 0.0)
    # The extra price column must not change a single number on its own.
    without_column = AnnualWalkForwardEngine(
        PointInTimeDataLoader(SystemConfig(initial_portfolio_value_brl=100_000))
        .fetch_prices("2018-01-01", "2023-01-10", offline=True),
        [old_snapshot()], SystemConfig(initial_portfolio_value_brl=100_000),
    ).run(AnnualWalkForwardConfig(2020, 2023, factor="triple_factor", maximum_equity_weight=.60,
                                  maximum_asset_weight=.30, top_assets=4))[0]
    pd.testing.assert_series_equal(with_column.net_return, without_column.net_return, check_names=False)


def test_a_sleeve_fraction_without_an_instrument_is_rejected():
    with pytest.raises(ValueError, match="global_sleeve_ticker"):
        AnnualWalkForwardConfig(2020, 2023, global_sleeve_fraction=.20)
    with pytest.raises(ValueError, match="global_sleeve_fraction"):
        AnnualWalkForwardConfig(2020, 2023, global_sleeve_ticker="IVVB11", global_sleeve_fraction=1.5)


def test_monthly_exemption_is_a_cliff_not_a_deduction():
    tax = BrazilianTaxModel()
    limit = tax.monthly_sale_exemption_brl
    assert tax.equity_rate_for_sale(limit - 1) == 0.0
    assert tax.equity_rate_for_sale(limit) == 0.0, "at the limit the sale is still exempt"
    # One real over the limit taxes the whole gain, not the excess.
    assert tax.equity_rate_for_sale(limit + 1) == tax.equity_rate
    assert tax.equity_rate_for_sale(limit * 100) == tax.equity_rate


def _tax_frame(wealth: float) -> pd.DataFrame:
    return pd.DataFrame({
        "equity_gain_rate": [.20, .20], "cash_weight": [.45, .45],
        "turnover": [1.0, 1.0], "net_return": [.20, .20],
        "cdi_net_return": [.10, .10], "opening_wealth_brl": [wealth, wealth],
    })


def test_exemption_is_off_by_default_so_published_series_are_unchanged():
    frame = _tax_frame(50_000)
    published = apply_annual_taxes(frame, BrazilianTaxModel())
    explicit = apply_annual_taxes(frame, BrazilianTaxModel(), apply_monthly_exemption=False)
    pd.testing.assert_frame_equal(published, explicit)
    assert "equity_rate_applied" not in published.columns


def test_a_small_book_selling_under_the_limit_pays_no_equity_tax():
    # 30k of wealth, 55% in equities, half the book sold: well under the limit.
    small = apply_annual_taxes(_tax_frame(30_000), BrazilianTaxModel(), apply_monthly_exemption=True)
    large = apply_annual_taxes(_tax_frame(5_000_000), BrazilianTaxModel(), apply_monthly_exemption=True)
    assert small.equity_rate_applied.eq(0.0).all()
    assert large.equity_rate_applied.eq(.15).all()
    assert (small.net_return_after_tax > large.net_return_after_tax).all()
