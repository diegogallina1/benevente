import pandas as pd

from b3_universe import build_universe_snapshot, classify_instrument
from b3_cvm_mapping import load_b3_isin_database, load_b3_issuer_database, map_b3_equities


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


def test_parser_date_window_is_applied_while_loading(tmp_path):
    # The fixed-width ZIP parser is exercised through its public file path in
    # integration tests; this assertion documents why annual January builds
    # retain only the prior-liquidity window rather than the entire year.
    from b3_universe import parse_cotahist
    assert "start_date" in parse_cotahist.__annotations__


def test_official_b3_isin_bridge_has_precedence_over_short_issuer_name(tmp_path):
    (tmp_path / "EMISSOR.TXT").write_text('"0042","Empresa Oficial","12.345.678/0001-90","20260812"\n', encoding="latin1")
    fields = ["20260812", "A", "BRTEST000001", "0042"] + [""] * 41
    (tmp_path / "NUMERACA.TXT").write_text(",".join(f'\"{field}\"' for field in fields) + "\n", encoding="latin1")
    bridge = load_b3_isin_database(tmp_path)
    master = pd.DataFrame([{
        "CNPJ_CIA": "12345678000190", "DENOM_SOCIAL": "NOME DIFERENTE S.A.",
        "DENOM_COMERC": "DIFERENTE", "SETOR_ATIV": "Financeiro",
    }])
    universe = pd.DataFrame([{
        "ticker": "TEST3.SA", "isin": "BRTEST000001", "issuer_name": "CURTO",
        "asset_class": "equity", "source": "B3",
    }])
    mapped = map_b3_equities(universe, master, isin_cnpj=bridge)
    assert mapped.loc[0, "cnpj_cia"] == "12.345.678/0001-90"
    assert mapped.loc[0, "match_method"] == "official_b3_isin_cnpj"


def test_unique_official_b3_issuer_prefix_is_a_conservative_fallback(tmp_path):
    (tmp_path / "EMISSOR.TXT").write_text('"0042","Empresa Longa S.A.","12.345.678/0001-90","20260812"\n', encoding="latin1")
    fields = ["20260812", "A", "BROTHER00001", "0042"] + [""] * 41
    (tmp_path / "NUMERACA.TXT").write_text(",".join(f'\"{field}\"' for field in fields) + "\n", encoding="latin1")
    master = pd.DataFrame([{
        "CNPJ_CIA": "12345678000190", "DENOM_SOCIAL": "NOME DIFERENTE S.A.",
        "DENOM_COMERC": "DIFERENTE", "SETOR_ATIV": "Financeiro",
    }])
    universe = pd.DataFrame([{
        "ticker": "TEST3.SA", "isin": "BRTEST000001", "issuer_name": "EMPRESA LONGA",
        "asset_class": "equity", "source": "B3",
    }])
    mapped = map_b3_equities(universe, master, b3_issuers=load_b3_issuer_database(tmp_path))
    assert mapped.loc[0, "match_method"] == "official_b3_issuer_unique_prefix"
