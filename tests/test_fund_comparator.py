from zipfile import ZipFile

import pandas as pd
import pytest

from fund_comparator import CvmFundDailyClient, FundQuoteSeries, compare_common_window, format_cnpj, normalize_cnpj
from pilot_tracker import build_performance
from production_policy import ProductionPolicy


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
