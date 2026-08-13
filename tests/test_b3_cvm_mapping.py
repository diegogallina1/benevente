import pandas as pd

from b3_cvm_mapping import accepted_issuers, load_cvm_company_master, map_b3_equities, normalise_name


def master(tmp_path):
    path = tmp_path / "cad.csv"
    pd.DataFrame([
        {"CNPJ_CIA": "11.111.111/0001-11", "DENOM_SOCIAL": "Companhia Alpha S.A.", "DENOM_COMERC": "ALPHA", "SETOR_ATIV": "Financeiro"},
        {"CNPJ_CIA": "22.222.222/0001-22", "DENOM_SOCIAL": "Companhia Alfa Energia S.A.", "DENOM_COMERC": "ALFA ENERGIA", "SETOR_ATIV": "Energia"},
    ]).to_csv(path, sep=";", index=False, encoding="latin1")
    return load_cvm_company_master(path)


def universe():
    return pd.DataFrame([
        {"ticker": "ALPH3.SA", "issuer_name": "ALPHA", "asset_class": "equity", "source": "dated B3"},
        {"ticker": "ALFA3.SA", "issuer_name": "ALFA", "asset_class": "equity", "source": "dated B3"},
        {"ticker": "ETF11.SA", "issuer_name": "ETF", "asset_class": "etf", "source": "dated B3"},
    ])


def test_mapping_accepts_exact_names_and_leaves_ambiguous_names_for_review(tmp_path):
    mapping = map_b3_equities(universe(), master(tmp_path))
    alpha = mapping.set_index("ticker").loc["ALPH3.SA"]
    ambiguous = mapping.set_index("ticker").loc["ALFA3.SA"]
    assert alpha.mapping_status == "accepted"
    assert alpha.cnpj_cia == "11.111.111/0001-11"
    assert ambiguous.mapping_status == "review_required"
    assert accepted_issuers(mapping).ticker.tolist() == ["ALPH3.SA"]


def test_accepted_mapping_allows_two_share_classes_for_one_reporting_company(tmp_path):
    rows = universe().iloc[[0]].copy()
    rows.loc[1] = {"ticker": "ALPH4.SA", "issuer_name": "ALPHA", "asset_class": "equity", "source": "dated B3"}
    accepted = accepted_issuers(map_b3_equities(rows, master(tmp_path)))
    assert accepted.cnpj_cia.nunique() == 1
    assert set(accepted.ticker) == {"ALPH3.SA", "ALPH4.SA"}


def test_normalisation_handles_accents_and_punctuation():
    assert normalise_name("Companhia Açúcar S.A.") == "COMPANHIAACUCARSA"
