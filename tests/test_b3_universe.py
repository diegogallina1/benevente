import pandas as pd

from b3_universe import build_universe_snapshot, classify_instrument


def test_classification_keeps_asset_classes_explicit():
    assert classify_instrument("ON", "010") == "equity"
    assert classify_instrument("CI FII", "010") == "fii"
    assert classify_instrument("DRN", "010") == "bdr"
    assert classify_instrument("ON NM", "010", "RAIA DROGASIL") == "equity"
    assert classify_instrument("CI", "010") == "etf"
    assert classify_instrument("ON", "070") == "other"


def test_snapshot_uses_only_sessions_at_or_before_decision_and_retains_non_equities():
    quotes = pd.DataFrame([
        {"trade_date": "2026-01-02", "ticker_raw": "AAAA3", "market_type": "010", "specification": "ON", "issuer_name": "AAA", "isin": "BRAAAA", "close_price_brl": 10, "traded_value_brl": 100, "trade_count": 1, "quantity": 10},
        {"trade_date": "2026-01-02", "ticker_raw": "BBBB11", "market_type": "010", "specification": "CI", "issuer_name": "FII BBB", "isin": "BRBBBB", "close_price_brl": 10, "traded_value_brl": 100, "trade_count": 1, "quantity": 10},
        {"trade_date": "2026-01-03", "ticker_raw": "AAAA3", "market_type": "010", "specification": "ON", "issuer_name": "AAA", "isin": "BRAAAA", "close_price_brl": 11, "traded_value_brl": 300, "trade_count": 2, "quantity": 20},
    ])
    quotes.trade_date = pd.to_datetime(quotes.trade_date)
    universe = build_universe_snapshot(quotes, "2026-01-02", liquidity_days=2)
    assert universe.ticker.tolist() == ["AAAA3.SA", "BBBB11.SA"]
    assert set(universe.asset_class) == {"equity", "fii"}
    assert universe.observed_at.eq("2026-01-02").all()
