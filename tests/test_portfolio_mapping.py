"""O mapa erra caro se errar o imposto, e erra a favor de quem vende.

Superestimar o imposto da travessia faz o escritório deixar o cliente numa
carteira pior; subestimar faz ele mover e descobrir a conta depois. Os testes
prendem a mecânica da apuração, que é onde a primeira versão errou: cobrava
alíquota cheia de um ganho enquanto um prejuízo maior era realizado na mesma
apuração.
"""
import pytest

from portfolio_mapping import Bucket, Position, Source, map_portfolio

ALVO = {"positions": {"AAAA3": 0.30, "BBBB3": 0.14}, "global_sleeve": 0.11, "cash": 0.45}


def pos(ticker, bucket, valor, custo, **kw):
    return Position(ticker, bucket, valor, custo, Source.MANUAL, **kw)


def test_prejuizo_abate_ganho_da_mesma_cesta() -> None:
    """O caso que a primeira versão errava, e o que ele custa."""
    carteira = [pos("CCCC3", Bucket.ACAO, 180_000, 40_000),   # ganho de 140k
                pos("DDDD3", Bucket.ACAO, 25_000, 90_000)]    # prejuízo de 65k
    mapa = map_portfolio(carteira, ALVO)
    assert mapa["tax_by_bucket"]["renda_variavel"]["realised_gain_brl"] == pytest.approx(75_000)
    assert mapa["transition_tax_brl"] == pytest.approx(75_000 * 0.15)


def test_prejuizo_de_outra_cesta_nao_abate() -> None:
    """Cripto tem regime próprio; deixá-la abater ação subestimaria a conta."""
    carteira = [pos("CCCC3", Bucket.ACAO, 180_000, 40_000),
                pos("Cripto", Bucket.FORA_DO_ESCOPO, 21_000, 30_000)]
    mapa = map_portfolio(carteira, ALVO)
    assert mapa["tax_by_bucket"]["renda_variavel"]["realised_gain_brl"] == pytest.approx(140_000)
    assert mapa["transition_tax_brl"] == pytest.approx(140_000 * 0.15)


def test_o_que_ja_esta_no_peso_nao_e_movido() -> None:
    carteira = [pos("AAAA3", Bucket.ACAO, 30_000, 10_000),
                pos("Caixa", Bucket.CAIXA, 70_000, 70_000)]
    mapa = map_portfolio(carteira, ALVO)
    manter = [m for m in mapa["moves"] if m["ticker"] == "AAAA3"][0]
    assert manter["action"] == "manter"
    assert manter["tax_brl"] == 0
    assert mapa["alignment"] > 0.9


def test_a_origem_de_cada_posicao_viaja_ate_o_mapa() -> None:
    """Um mapa que não sabe se o dado veio de extrato ou de digitação não é auditável."""
    carteira = [Position("AAAA3", Bucket.ACAO, 50_000, 30_000, Source.B3_INVESTIDOR),
                Position("CDB", Bucket.RENDA_FIXA, 50_000, 48_000, Source.OPEN_FINANCE,
                         conglomerate="Beta")]
    mapa = map_portfolio(carteira, ALVO)
    assert "extrato da Área do Investidor da B3" in mapa["sources"]
    assert "Open Finance (compartilhamento de investimentos)" in mapa["sources"]


def test_o_teto_do_fgc_e_verificado_na_carteira_que_chega() -> None:
    carteira = [Position("CDB Beta", Bucket.RENDA_FIXA, 310_000, 300_000, Source.OPEN_FINANCE,
                         conglomerate="Beta"),
                pos("AAAA3", Bucket.ACAO, 90_000, 80_000)]
    mapa = map_portfolio(carteira, ALVO)
    assert mapa["fgc_breaches"]["Beta"] == pytest.approx(310_000)


def test_o_mapa_nao_projeta_retorno() -> None:
    """A travessia é precificada; o 'quanto tempo se paga' exigiria projeção."""
    mapa = map_portfolio([pos("AAAA3", Bucket.ACAO, 100_000, 60_000)], ALVO)
    texto = str(mapa).lower()
    for proibido in ("payback", "retorno_esperado", "expected_return", "breakeven"):
        assert proibido not in texto
    assert "projetar retorno futuro" in mapa["honesty"]
