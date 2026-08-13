import pandas as pd

from fundamentals import FundamentalSnapshot
from live_issuer_map import load_live_issuer_map
from refresh_recent_itr import refresh_recent_itr


def write_market(path):
    pd.DataFrame([
        {"ticker": "ALPH3.SA", "observed_at": "2026-08-12", "market_cap_brl": 1e9,
         "average_daily_value_brl": 1e7, "close_price_brl": 10, "lot_size": 1, "source": "B3 dated export"},
        {"ticker": "BETA3.SA", "observed_at": "2026-08-12", "market_cap_brl": 1e9,
         "average_daily_value_brl": 1e7, "close_price_brl": 10, "lot_size": 1, "source": "B3 dated export"},
    ]).to_csv(path, index=False)


def write_map(path):
    pd.DataFrame([
        {"ticker": "ALPH3.SA", "cnpj_cia": "11.111.111/0001-11", "cvm_sector": "Indústria",
         "mapping_status": "accepted", "observed_at": "2026-08-12", "source": "B3 ISIN official bridge"},
        {"ticker": "BETA3.SA", "cnpj_cia": "22.222.222/0001-22", "cvm_sector": "Financeiro",
         "mapping_status": "review_required", "observed_at": "2026-08-12", "source": "B3 ISIN official bridge"},
    ]).to_csv(path, index=False)


def test_live_issuer_map_accepts_only_dated_approved_b3_cvm_rows(tmp_path):
    path = tmp_path / "map.csv"; write_map(path)
    result = load_live_issuer_map(path, {"ALPH3.SA", "BETA3.SA", "MISS3.SA"}, pd.Timestamp("2026-08-12"))
    assert [issuer.ticker for issuer in result.issuers] == ["ALPH3.SA"]
    assert set(result.coverage[result.coverage.status.eq("blocked")].ticker) == {"BETA3.SA", "MISS3.SA"}


class FakeItrClient:
    def live_snapshots(self, itr_year, decision_date, market_data, issuers):
        issuer = issuers[0]
        if issuer.ticker == "BETA3.SA":
            raise RuntimeError("no eligible ITR")
        return [FundamentalSnapshot(
            ticker=issuer.ticker, as_of_date=pd.Timestamp("2026-06-30"), available_date=pd.Timestamp("2026-08-01"),
            sector=issuer.sector, is_financial=issuer.is_financial, market_cap_brl=1e9, price_to_earnings=10,
            price_to_book=1, ev_to_ebit=8, free_cash_flow_yield=.05, roe=.15, roic=.12,
            debt_to_ebitda=None, interest_coverage=None, operating_margin=.1, revenue_growth_3y=None,
            average_daily_value_brl=1e7, source="CVM fixture",
        )]


def test_recent_itr_refresh_writes_coverage_without_all_or_nothing_failure(tmp_path):
    market = tmp_path / "market.csv"; write_market(market)
    issuer_map = tmp_path / "map.csv"
    write_map(issuer_map)
    # Promote BETA into the map so its simulated ITR failure is independently recorded.
    frame = pd.read_csv(issuer_map); frame.loc[frame.ticker.eq("BETA3.SA"), "mapping_status"] = "accepted"; frame.to_csv(issuer_map, index=False)
    rows, coverage, manifest = refresh_recent_itr(2026, pd.Timestamp("2026-08-12"), market, issuer_map, client=FakeItrClient())
    assert rows.ticker.tolist() == ["ALPH3.SA"]
    assert coverage.set_index("ticker").loc["BETA3.SA", "reason"] == "no eligible ITR"
    assert manifest["accepted_snapshots"] == 1
    assert manifest["status"] == "ready"
