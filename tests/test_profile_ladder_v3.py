"""A v3 troca o caixa e nada mais — e o registro precisa provar isso.

Uma versão nova é onde o viés entra sem ser visto: mexe-se em três coisas, mede-se
o conjunto e atribui-se o ganho à que se preferia. Os testes abaixo prendem o
escopo da mudança, a ausência de estatística de desempenho no registro e a regra
da contagem prospectiva, que é a única que ainda não custou nada e por isso
precisa estar escrita antes de custar.
"""
import json

import pytest

from profile_ladder_v2 import LADDER_V2
from profile_ladder_v3 import LADDER_V3, POLICY, SUPERSEDES, V3_INPUTS, register


@pytest.fixture(scope="module")
def payload(tmp_path_factory):
    return register(tmp_path_factory.mktemp("v3") / "v3.json", approved_by="Diego Gallina")


def test_a_escada_e_a_mesma_da_v2(payload) -> None:
    """Se os perfis mudassem junto, nada do resultado seria atribuível ao caixa."""
    assert LADDER_V3 == LADDER_V2
    for profile in ("conservador", "equilibrado", "arrojado"):
        declarado = payload["profiles"][profile]
        assert declarado["maximum_equity_weight"] == LADDER_V2[profile]["maximum_equity_weight"]
        assert declarado["top_assets"] == LADDER_V2[profile]["top_assets"]


def test_o_registro_nao_carrega_estatistica_de_desempenho(payload) -> None:
    texto = json.dumps(payload, ensure_ascii=False).lower()
    for proibido in ("observed_cagr", "realised_return", "backtest_return", "performance_result",
                     "12,51", "15,51", "19,87"):
        assert proibido not in texto
    assert payload["status"] == "registered_not_prospectively_validated"
    assert payload["selection_method"] == "declared, not searched"


def test_o_registro_declara_o_que_mudou_e_que_o_resultado_piorou(payload) -> None:
    mudanca = payload["change_from_previous"]
    assert mudanca["what_changed"] == "apenas o instrumento de caixa"
    assert "cai" in mudanca["measured_consequence"]
    assert "plana até 2012" in mudanca["defect_repaired"]
    assert payload["supersedes"] == SUPERSEDES
    assert payload["policy"] == POLICY


def test_a_contagem_prospectiva_nao_recomeca_e_o_motivo_esta_escrito(payload) -> None:
    assert payload["confirmatory_sample_starts"] == "first B3 trading session of 2027"
    rationale = payload["confirmatory_count_rationale"]
    assert "nenhuma observação prospectiva foi consumida" in rationale
    assert "zerar a contagem" in rationale


def test_o_caixa_declarado_e_um_instrumento_com_fonte_e_custo(payload) -> None:
    caixa = payload["cash_sleeve"]
    assert "Tesouro Selic" in caixa["instrument"]
    assert caixa["source"].startswith("https://www.tesourotransparente.gov.br/")
    assert caixa["custody_fee_annual_by_period"]["2022+"] == 0.0020
    assert caixa["exemption_first_10k_applied"] is False
    # O produto bancário foi considerado e recusado por falta de série; o motivo
    # fica no registro para que a recusa não precise ser relembrada.
    assert "118%" in caixa["why_not_a_bank_product"]


def test_a_camada_de_protecao_exige_caixa_liquido(payload) -> None:
    """Caixa preso não recebe nem devolve exposição dentro do ano."""
    assert "D+0" in payload["intrayear_overlay"]["liquidity_requirement"]


def test_todo_insumo_e_todo_codigo_declarado_tem_hash(payload) -> None:
    assert set(payload["inputs"]) == set(V3_INPUTS)
    assert all(len(d) == 64 for d in payload["inputs"].values())
    assert "tesouro_selic_series.py" in payload["code"]
    assert all(len(d) == 64 for d in payload["code"].values())


def test_o_painel_da_v3_difere_do_da_v2_apenas_no_caixa(payload) -> None:
    assert V3_INPUTS["prices"].name == "prices_b3_real_cash_2011_2025.csv"
    manifest = json.loads(V3_INPUTS["total_return_manifest"].read_text(encoding="utf-8"))
    assert manifest["cash_column"] == "TITULO_CDI"
    assert "Tesouro Selic" in manifest["cash_instrument"]
    janela = manifest["cash_cagr_evaluated_window_2015_2025"]
    assert janela["real_instrument"] < janela["index_100pct_cdi"]


def test_o_criterio_de_falseamento_mede_contra_o_proprio_caixa(payload) -> None:
    criterio = payload["success_criterion"]
    assert criterio["must_beat_cash_instrument_after_tax"] is True
    assert "its own declared cash instrument" in criterio["falsification"]
