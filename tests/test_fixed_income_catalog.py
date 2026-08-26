"""O catálogo precisa acertar a lei antes de acertar o ranking.

Ordenar renda fixa pela taxa anunciada é o erro que o módulo existe para
impedir: isenção e tabela regressiva invertem a ordem conforme o prazo. E
"respeitar o FGC" só é verdade se o teto por conglomerado for aplicado mesmo
quando o produto do emissor estourado é o melhor da lista.
"""
from datetime import date

import pytest

from fixed_income_catalog import (FGC_PER_CONGLOMERATE_BRL, FgcLedger, Index, Product,
                                  allocate, income_tax_rate, iof_factor, net_annual_yield, rank)

HOJE = date(2026, 1, 2)
CDI = 0.10


def cdb(name, rate, meses, conglomerate="Banco A", **kw):
    return Product(name=name, kind="CDB", issuer=conglomerate, conglomerate=conglomerate,
                   index=Index.CDI, rate=rate,
                   maturity=date(2026 + (meses // 12), 1 + (meses % 12), 2), **kw)


def lci(name, rate, meses, conglomerate="Banco B", **kw):
    return Product(name=name, kind="LCI", issuer=conglomerate, conglomerate=conglomerate,
                   index=Index.CDI, rate=rate,
                   maturity=date(2026 + (meses // 12), 1 + (meses % 12), 2), **kw)


def test_tabela_regressiva_e_iof_seguem_a_lei() -> None:
    assert income_tax_rate(100) == 0.225
    assert income_tax_rate(200) == 0.20
    assert income_tax_rate(400) == 0.175
    assert income_tax_rate(1000) == 0.15
    assert iof_factor(30) == 0.0
    assert iof_factor(29) == pytest.approx(0.0333, abs=1e-3)
    assert iof_factor(1) == pytest.approx(0.9667, abs=1e-3)


def test_isencao_inverte_a_ordem_que_a_taxa_anunciada_sugere() -> None:
    """Uma LCI a 92% do CDI bate um CDB a 110% no prazo curto.

    É o caso que motiva o módulo: pela taxa anunciada o CDB ganha por dezoito
    pontos; depois do imposto de 22,5% do primeiro semestre, perde.
    """
    ordenado = rank([cdb("CDB 110%", 1.10, 5), lci("LCI 92%", 0.92, 5)], HOJE, CDI)
    assert ordenado[0]["product"] == "LCI 92%"
    assert ordenado[0]["tax_rate"] == 0.0
    assert ordenado[1]["tax_rate"] == 0.225


def test_prazo_longo_devolve_a_vantagem_ao_cdb() -> None:
    ordenado = rank([cdb("CDB 110%", 1.10, 30), lci("LCI 92%", 0.92, 30)], HOJE, CDI)
    assert ordenado[0]["product"] == "CDB 110%"
    assert ordenado[0]["tax_rate"] == 0.15


def test_teto_do_fgc_corta_o_melhor_produto_e_desce_para_o_proximo() -> None:
    melhor = cdb("CDB A 120%", 1.20, 24, conglomerate="Banco A")
    segundo = cdb("CDB C 112%", 1.12, 24, conglomerate="Banco C")
    plano = allocate([melhor, segundo], 400_000, HOJE, CDI)
    alocado = {a["product"]: a["amount_brl"] for a in plano["allocations"]}
    assert alocado["CDB A 120%"] == FGC_PER_CONGLOMERATE_BRL
    assert alocado["CDB C 112%"] == 150_000
    assert plano["unallocated_brl"] == 0


def test_dois_produtos_do_mesmo_conglomerado_dividem_um_teto_so() -> None:
    plano = allocate([cdb("CDB A1", 1.20, 24, conglomerate="Banco A"),
                      cdb("CDB A2", 1.15, 24, conglomerate="Banco A")],
                     400_000, HOJE, CDI)
    assert sum(a["amount_brl"] for a in plano["allocations"]) == FGC_PER_CONGLOMERATE_BRL
    assert plano["unallocated_brl"] == 150_000
    assert any("FGC" in r["reason"] for r in plano["rejected"])


def test_produto_sem_cobertura_so_entra_se_o_risco_for_declarado() -> None:
    cri = Product(name="CRI X", kind="CRI", issuer="Securitizadora", conglomerate="Securitizadora",
                  index=Index.CDI, rate=1.30, maturity=date(2029, 1, 2))
    sem = allocate([cri], 100_000, HOJE, CDI)
    assert sem["allocated_brl"] == 0
    assert "FGC" in sem["rejected"][0]["reason"]

    com = allocate([cri], 100_000, HOJE, CDI, allow_uncovered=True)
    assert com["allocated_brl"] == 100_000
    assert com["allocations"][0]["fgc_covered"] is False
    assert com["allocations"][0]["regime"].startswith("valor mobiliário")


def test_reserva_de_liquidez_protege_a_camada_intranual() -> None:
    """Caixa preso em papel de dois anos não recebe nem devolve exposição."""
    travado = cdb("CDB 2 anos 120%", 1.20, 24, conglomerate="Banco A")
    liquido = cdb("CDB liquidez diária 101%", 1.01, 24, conglomerate="Banco D", daily_liquidity=True)
    plano = allocate([travado, liquido], 200_000, HOJE, CDI, liquid_floor_brl=80_000)
    alocado = {a["product"]: a["amount_brl"] for a in plano["allocations"]}
    assert alocado["CDB 2 anos 120%"] == 120_000
    assert alocado["CDB liquidez diária 101%"] == 80_000


def test_o_livro_do_fgc_acumula_entre_chamadas() -> None:
    livro = FgcLedger()
    produtos = [cdb("CDB A", 1.20, 24, conglomerate="Banco A")]
    allocate(produtos, 200_000, HOJE, CDI, ledger=livro)
    assert livro.headroom("Banco A") == 50_000
    segundo = allocate(produtos, 200_000, HOJE, CDI, ledger=livro)
    assert segundo["allocated_brl"] == 50_000
    assert livro.headroom("Banco A") == 0


def test_tesouro_selic_paga_custodia_e_isso_aparece_no_liquido() -> None:
    com = Product(name="Tesouro Selic 2029", kind="TESOURO", issuer="Tesouro Nacional",
                  conglomerate="Tesouro Nacional", index=Index.SELIC, rate=1.0,
                  maturity=date(2029, 3, 1), custody_fee_annual=0.0020)
    sem = Product(name="Tesouro sem custódia", kind="TESOURO", issuer="Tesouro Nacional",
                  conglomerate="Tesouro Nacional", index=Index.SELIC, rate=1.0,
                  maturity=date(2029, 3, 1))
    a = net_annual_yield(com, HOJE, CDI, 0.045)["net_annual"]
    b = net_annual_yield(sem, HOJE, CDI, 0.045)["net_annual"]
    assert b > a
    assert (b - a) == pytest.approx(0.0020 * (1 - 0.15), abs=3e-4)
