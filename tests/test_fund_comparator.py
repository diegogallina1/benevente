from zipfile import ZipFile

import pandas as pd
import pytest

from fund_comparator import (CvmFundDailyClient, FundQuoteSeries, compare_common_window, format_cnpj,
                             fund_values_for_nav, normalize_cnpj)
from pilot_tracker import build_performance
from production_policy import ProductionPolicy
from shadow_portfolio import ProposedOrder, activate_shadow_portfolio


def test_cnpj_normalization_and_archive_schedule():
    assert normalize_cnpj("73.232.530/0001-39") == "73232530000139"
    assert format_cnpj("73232530000139") == "73.232.530/0001-39"
    urls = CvmFundDailyClient.archive_urls(pd.Timestamp("2020-12-01"), pd.Timestamp("2021-02-01"))
    assert urls[0].endswith("HIST/inf_diario_fi_2020.zip")
    assert urls[-1].endswith("inf_diario_fi_202102.zip")
    with pytest.raises(ValueError):
        normalize_cnpj("not-a-cnpj")


def test_cvm_archive_filter_accepts_fund_and_class_schema(tmp_path):
    source = tmp_path / "inf.zip"
    csv = "CNPJ_FUNDO_CLASSE_COTA;DT_COMPTC;VL_QUOTA\n73.232.530/0001-39;2025-01-02;1,2345\n00.000.000/0000-00;2025-01-02;3,0\n"
    with ZipFile(source, "w") as archive:
        archive.writestr("inf.csv", csv)
    rows = CvmFundDailyClient._rows_for_cnpj(source, "73232530000139")
    assert len(rows) == 1
    assert rows.iloc[0].VL_QUOTA == "1,2345"


def test_active_fund_comparison_uses_only_common_window():
    dates = pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"])
    strategy = pd.DataFrame({"date": dates, "wealth": [100.0, 110.0, 105.0]})
    cdi = pd.DataFrame({"date": dates, "wealth": [100.0, 101.0, 102.0]})
    quotes = pd.Series([10.0, 10.5], index=pd.to_datetime(["2025-02-27", "2025-03-28"]))
    fund = FundQuoteSeries("73232530000139", quotes, ("https://example.test/fund.zip",))
    curves, metrics, metadata = compare_common_window({"Benevente": strategy, "CDI": cdi}, fund, "Fundo ativo")
    assert list(curves.index) == list(dates[1:])
    assert curves.iloc[0].eq(100).all()
    assert set(metrics.strategy) == {"Benevente", "CDI", "Fundo ativo"}
    assert metadata["comparison_start"] == "2025-02-28"


def test_fund_values_for_shadow_nav_uses_last_published_quota():
    fund = FundQuoteSeries("73232530000139", pd.Series(
        [10.0, 10.5], index=pd.to_datetime(["2026-01-01", "2026-02-01"])), ("https://example.test/fund.zip",))
    values = fund_values_for_nav(fund, pd.to_datetime(["2026-01-02", "2026-02-02"]), 100_000)
    assert values.iloc[0] == pytest.approx(100_000)
    assert values.iloc[1] == pytest.approx(105_000)


def test_shadow_tracking_accepts_optional_active_fund_value():
    policy = ProductionPolicy(policy_id="shadow", owner="Diego", effective_date="2026-01-02", portfolio_value_brl=100_000,
                              horizon_years=5, maximum_rebalance_cost_brl=500)
    nav = pd.DataFrame([
        {"date": "2026-01-02", "portfolio_value_brl": 100_000, "cdi_value_brl": 100_000,
         "ibovespa_value_brl": 100_000, "active_fund_value_brl": 100_000, "notes": "baseline"},
        {"date": "2026-02-02", "portfolio_value_brl": 103_000, "cdi_value_brl": 101_000,
         "ibovespa_value_brl": 102_000, "active_fund_value_brl": 104_000, "notes": "month one"},
    ])
    _, summary = build_performance(policy, nav)
    assert summary["active_fund_return"] == pytest.approx(0.04)


def test_human_approval_freezes_a_shadow_portfolio_and_binds_tracking(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy = ProductionPolicy(policy_id="shadow", owner="Diego", effective_date="2026-01-02", portfolio_value_brl=100_000,
                              horizon_years=5, maximum_rebalance_cost_brl=500,
                              acknowledged_not_investment_advice=True)
    policy_path.write_text(policy.model_dump_json(), encoding="utf-8")
    orders_path = tmp_path / "orders.csv"
    pd.DataFrame([ProposedOrder("2026-01-02", "PETR4", "BUY", 100, 30, 1, "shadow:PETR4").__dict__]).to_csv(orders_path, index=False)
    activation = activate_shadow_portfolio(policy_path, orders_path, "Comitê de investimentos", tmp_path / "activation.json",
                                           "73.232.530/0001-39", "Fundo de comparação")
    nav = pd.DataFrame([
        {"date": "2026-01-02", "portfolio_value_brl": 100_000, "cdi_value_brl": 100_000,
         "ibovespa_value_brl": 100_000, "active_fund_value_brl": 100_000, "notes": "baseline"},
        {"date": "2026-02-02", "portfolio_value_brl": 101_000, "cdi_value_brl": 100_800,
         "ibovespa_value_brl": 100_500, "active_fund_value_brl": 100_900, "notes": "first month"},
    ])
    _, summary = build_performance(policy, nav, activation)
    assert summary["status"] == "SHADOW_PORTFOLIO_ACTIVE"
    assert summary["approved_by"] == "Comitê de investimentos"
    assert summary["active_fund_cnpj"] == "73232530000139"


def test_shadow_activation_refuses_unapproved_or_wrong_date_orders(tmp_path):
    policy_path = tmp_path / "policy.json"
    policy = ProductionPolicy(policy_id="shadow", owner="Diego", effective_date="2026-01-02", portfolio_value_brl=100_000,
                              horizon_years=5, maximum_rebalance_cost_brl=500,
                              acknowledged_not_investment_advice=True)
    policy_path.write_text(policy.model_dump_json(), encoding="utf-8")
    orders_path = tmp_path / "orders.csv"
    pd.DataFrame([ProposedOrder("2026-01-03", "PETR4", "BUY", 100, 30, 1, "shadow:PETR4").__dict__]).to_csv(orders_path, index=False)
    with pytest.raises(ValueError, match="effective date"):
        activate_shadow_portfolio(policy_path, orders_path, "Comitê", tmp_path / "activation.json")
