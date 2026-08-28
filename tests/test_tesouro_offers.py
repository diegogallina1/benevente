# -*- coding: utf-8 -*-
"""A grade do Tesouro Direto trazida para a régua do catálogo.

O risco aqui não é errar a conta, é errar em silêncio: uma família nova de
papel que some sem aviso, ou um ágio lido como se fosse taxa cheia.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import sys

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "tools"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import fixed_income_catalog as cat  # noqa: E402
from build_tesouro_offers import CUSTODIA, FAMILIAS, grade  # noqa: E402

ARQUIVO = ROOT / "data" / "ofertas_tesouro.json"


def _frame(linhas: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(linhas)


def test_o_agio_do_selic_vira_multiplo_do_indice():
    """O arquivo publica Selic + 0,05%, não "100,5% da Selic". Ler o ágio como
    taxa cheia faria o Tesouro Selic aparecer rendendo 0,05% ao ano."""
    itens, _, _ = grade(_frame([{
        "Tipo Titulo": "Tesouro Selic", "Data Base": "27/08/2026",
        "Data Vencimento": "01/03/2031", "Taxa Compra Manha": 0.0937,
        "PU Compra Manha": 10000.0}]), selic_anual=0.0937)
    assert len(itens) == 1
    # ágio de 0,0937% sobre uma Selic de 9,37% é exatamente um centésimo dela.
    assert itens[0]["rate"] == pytest.approx(1.01, abs=1e-6)


def test_familia_desconhecida_e_reportada_e_nao_sumida():
    itens, _, ignorados = grade(_frame([
        {"Tipo Titulo": "Tesouro Marte 2099", "Data Base": "27/08/2026",
         "Data Vencimento": "01/01/2099", "Taxa Compra Manha": 10.0,
         "PU Compra Manha": 100.0}]), selic_anual=0.0937)
    assert itens == []
    assert ignorados == {"Tesouro Marte 2099": 1}


def test_papel_fora_de_venda_ou_vencido_nao_entra():
    itens, _, _ = grade(_frame([
        {"Tipo Titulo": "Tesouro Prefixado", "Data Base": "27/08/2026",
         "Data Vencimento": "01/01/2030", "Taxa Compra Manha": 0.0,
         "PU Compra Manha": 700.0},
        {"Tipo Titulo": "Tesouro Prefixado", "Data Base": "27/08/2026",
         "Data Vencimento": "01/01/2020", "Taxa Compra Manha": 12.0,
         "PU Compra Manha": 900.0}]), selic_anual=0.0937)
    assert itens == [], "taxa zerada é papel fora de venda; vencimento passado não é oferta"


def test_toda_familia_mapeada_usa_indice_que_o_catalogo_conhece():
    conhecidos = {i.value for i in cat.Index}
    for familia, indice in FAMILIAS.items():
        assert indice in conhecidos, familia


@pytest.mark.skipif(not ARQUIVO.exists(), reason="rode tools/build_tesouro_offers.py")
def test_o_arquivo_publicado_carrega_no_catalogo():
    """Gerar num formato que o catálogo não lê seria descobrir tarde."""
    doc = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    produtos = cat.load_catalog(ARQUIVO)
    assert produtos and len(produtos) == len(doc["products"])
    for p in produtos:
        assert p.kind == "TESOURO"
        assert p.fgc_covered is False, "título público não tem FGC, e não precisa"
        assert p.custody_fee_annual == CUSTODIA
    linhas = cat.rank(produtos, date.fromisoformat(doc["reference_date"]),
                      doc["selic_annual_used"], 0.045)
    assert all(r["net_annual"] < r["gross_annual"] for r in linhas), \
        "custódia e imposto sempre reduzem: líquido igual ao bruto denuncia conta não aplicada"
