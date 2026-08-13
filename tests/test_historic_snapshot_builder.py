import pandas as pd
import pytest

from cvm_fundamentals import BRAZIL_ISSUERS
from fundamentals import FundamentalSnapshot
from historic_snapshot_builder import build_historical_snapshots


class FakeItrClient:
    def live_snapshots(self, itr_year, decision_date, market_data, issuers=None):
        rows = []
        for issuer in (issuers or BRAZIL_ISSUERS):
            market = market_data[issuer.ticker]
            rows.append(FundamentalSnapshot(
                ticker=issuer.ticker, as_of_date=pd.Timestamp("2011-09-30"), available_date=pd.Timestamp("2011-11-10"),
                sector=issuer.sector, is_financial=issuer.is_financial, market_cap_brl=market.market_cap_brl,
                price_to_earnings=8, price_to_book=1, ev_to_ebit=6, free_cash_flow_yield=.08,
                roe=.16, roic=.15, debt_to_ebitda=1, interest_coverage=5, operating_margin=.2,
                revenue_growth_3y=.1, average_daily_value_brl=market.average_daily_value_brl,
                source=f"fake ITR {itr_year}",
            ))
        return rows


def market_panel():
    return pd.DataFrame([{
        "decision_date": "2012-01-01", "ticker": issuer.ticker, "observed_at": "2011-12-30",
        "market_cap_brl": 10_000_000_000, "average_daily_value_brl": 100_000_000,
        "close_price_brl": 20, "lot_size": 1, "source": "dated test market export",
    } for issuer in BRAZIL_ISSUERS])


def test_builder_rejects_january_2011_without_external_pre_2011_archive():
    with pytest.raises(ValueError, match="begins in 2012"):
        build_historical_snapshots(market_panel(), 2011, 2012, client=FakeItrClient())


def test_builder_uses_only_market_rows_available_at_the_january_decision():
    result = build_historical_snapshots(market_panel(), 2012, 2012, client=FakeItrClient())
    assert len(result) == len(BRAZIL_ISSUERS)
    assert result.decision_date.eq("2012-01-01").all()
    assert result.market_cap_brl.eq(10_000_000_000).all()
    assert result.attrs["coverage"].status.eq("accepted").all()
