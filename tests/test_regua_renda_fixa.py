# -*- coding: utf-8 -*-
"""A régua do navegador e a régua em Python respondem a mesma coisa.

A pessoa digita a oferta que viu na corretora e espera o número na hora, o que
obriga a conta a rodar no navegador. Duas implementações da mesma regra tributária
divergem no dia em que uma tabela muda, e a que ninguém olha é a que fica para
trás. As tabelas já viajam de ``fixed_income_catalog`` para o app em vez de serem
reescritas; o que este arquivo cobre é a aritmética, que é reescrita.

O teste roda o JavaScript de verdade, o mesmo texto que entra na página, e não
uma cópia dele. Se o node não estiver instalado, ele falha em vez de passar
calado: um teste de equivalência que se desliga sozinho é pior que nenhum,
porque dá a impressão de que alguém está olhando.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import json
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from build_mapa_prototype import REGUA_RF_JS  # noqa: E402
from fixed_income_catalog import (Index, Product, motor_para_navegador,  # noqa: E402
                                  net_annual_yield)

REFERENCIA = date(2026, 8, 27)
CDI = 0.0937
IPCA = 0.045

#: Casos escolhidos nas quebras da regra, não em números redondos: cada faixa da
#: tabela regressiva, os dois lados do trigésimo dia onde o IOF some, o isento
#: contra o tributado, e as quatro formas de taxa.
CASOS = [
    ("CDB", Index.CDI, 1.10, 30), ("CDB", Index.CDI, 1.10, 29),
    ("CDB", Index.CDI, 1.02, 180), ("CDB", Index.CDI, 1.02, 181),
    ("CDB", Index.CDI, 1.18, 360), ("CDB", Index.CDI, 1.18, 361),
    ("CDB", Index.CDI, 0.98, 720), ("CDB", Index.CDI, 0.98, 721),
    ("CDB", Index.CDI_MAIS, 0.012, 1095), ("CDB", Index.CDI_MAIS, 0.025, 400),
    ("LCI", Index.CDI, 0.92, 400), ("LCI", Index.CDI, 0.92, 1095),
    ("LCA", Index.CDI, 0.88, 200), ("LCA", Index.PREFIXADO, 0.132, 800),
    ("LC", Index.PREFIXADO, 0.145, 1000), ("RDB", Index.IPCA, 0.068, 1500),
    ("CDB", Index.IPCA, 0.055, 2000), ("CDB", Index.PREFIXADO, 0.139, 90),
]
#: O nome curto do índice, do jeito que a tela oferece.
NA_TELA = {Index.CDI: "cdi", Index.CDI_MAIS: "cdi_mais",
           Index.PREFIXADO: "pre", Index.IPCA: "ipca", Index.SELIC: "selic"}


def _em_python() -> list[dict]:
    saida = []
    for tipo, indice, taxa, dias in CASOS:
        produto = Product(f"{tipo} {taxa} {dias}d", tipo, "Banco Exemplo", "Exemplo",
                          indice, taxa, REFERENCIA + timedelta(days=dias))
        r = net_annual_yield(produto, REFERENCIA, CDI, IPCA)
        saida.append({"dias": r["days"], "bruto": r["gross_annual"], "ir": r["tax_rate"],
                      "iof": r["iof_share"], "liquido": r["net_annual"]})
    return saida


def _no_navegador(tmp_path: Path) -> list[dict]:
    entrada = [{"tipo": tipo, "indice": NA_TELA[indice], "taxa": taxa,
                "vencimento": str(REFERENCIA + timedelta(days=dias))}
               for tipo, indice, taxa, dias in CASOS]
    programa = "\n".join([
        "const DADOS = " + json.dumps(
            {"renda_fixa": {"motor": motor_para_navegador(), "cdi_anual": CDI,
                            "ipca_anual": IPCA}}, ensure_ascii=False) + ";",
        REGUA_RF_JS,
        "const casos = " + json.dumps(entrada, ensure_ascii=False) + ";",
        f'const saida = casos.map(c => liquidoAoAno(c, "{REFERENCIA}"));',
        "console.log(JSON.stringify(saida));",
    ])
    arquivo = tmp_path / "regua.mjs"
    arquivo.write_text(programa, encoding="utf-8")
    node = shutil.which("node")
    assert node, "node é necessário para conferir a régua do navegador"
    saida = subprocess.run([node, str(arquivo)], capture_output=True, text=True,
                           encoding="utf-8", check=True)
    return json.loads(saida.stdout)


def test_as_duas_reguas_dao_o_mesmo_numero(tmp_path) -> None:
    esperado, obtido = _em_python(), _no_navegador(tmp_path)
    assert len(esperado) == len(obtido) == len(CASOS)
    for caso, py, js in zip(CASOS, esperado, obtido):
        assert js is not None, caso
        assert js["dias"] == py["dias"], caso
        # O Python arredonda no sexto decimal ao publicar, então a tolerância é
        # a do arredondamento e não uma folga escolhida para o teste passar.
        assert js["liquido"] == pytest.approx(py["liquido"], abs=1e-6), caso
        assert js["bruto"] == pytest.approx(py["bruto"], abs=1e-6), caso
        assert js["ir"] == pytest.approx(py["ir"], abs=1e-9), caso
        assert js["iof"] == pytest.approx(py["iof"], abs=1e-4), caso


def _equivalente(dias: int, isenta: float = 0.92) -> float:
    """Qual percentual do CDI um CDB precisa pagar para empatar com a LCI."""
    venc = REFERENCIA + timedelta(days=dias)
    alvo = net_annual_yield(Product("LCI", "LCI", "B", "B", Index.CDI, isenta, venc),
                            REFERENCIA, CDI, IPCA)["net_annual"]
    baixo, alto = 0.5, 2.0
    for _ in range(80):
        meio = (baixo + alto) / 2
        liquido = net_annual_yield(Product("CDB", "CDB", "B", "B", Index.CDI, meio, venc),
                                   REFERENCIA, CDI, IPCA)["net_annual"]
        baixo, alto = (meio, alto) if liquido < alvo else (baixo, meio)
    return meio


def test_o_ponto_de_equivalencia_depende_do_prazo_e_nao_e_a_razao_simples() -> None:
    """A conta de padaria dá 0,92 / 0,85 = 108,24%. Ela erra, e para cima.

    A razão simples supõe que o imposto morde a taxa anual. Ele morde o
    rendimento acumulado, e quanto mais longo o papel, menos isso pesa por ano.
    O resultado é que o CDB precisa pagar menos do que a razão sugere, e a
    diferença cresce com o prazo: quem usa o número único recusa oferta boa.
    """
    razao_simples = 0.92 / (1 - 0.15)
    assert round(razao_simples, 4) == 1.0824

    por_prazo = {dias: _equivalente(dias) for dias in (721, 1095, 1825)}
    for dias, taxa in por_prazo.items():
        assert taxa < razao_simples, (dias, taxa)
    # Monótono: quanto mais longo, menor a taxa que empata.
    assert por_prazo[721] > por_prazo[1095] > por_prazo[1825]
    assert 1.070 < por_prazo[721] < 1.080
    assert 1.050 < por_prazo[1825] < 1.060


def test_dentro_de_cada_faixa_de_imposto_o_prazo_ainda_move_a_equivalencia() -> None:
    """Não é só a tabela regressiva que decide, e por isso não há número único."""
    curto = _equivalente(200)    # faixa de 20%
    medio = _equivalente(400)    # faixa de 17,5%
    longo = _equivalente(1095)   # faixa de 15%
    assert curto > medio > longo
    assert curto > 1.14 and longo < 1.07


def test_o_motor_que_viaja_para_a_tela_e_o_mesmo_que_o_python_usa() -> None:
    """As tabelas não são reescritas do outro lado, são transportadas."""
    from fixed_income_catalog import (FGC_PER_CONGLOMERATE_BRL, FGC_ROLLING_CAP_BRL,
                                      IOF_DAILY_TABLE, IR_BRACKETS, PRODUCT_RULES)
    motor = motor_para_navegador()
    assert [(f["ate_dias"], f["aliquota"]) for f in motor["ir"]] == list(IR_BRACKETS)
    assert motor["iof"] == list(IOF_DAILY_TABLE)
    assert motor["fgc"]["por_conglomerado_brl"] == FGC_PER_CONGLOMERATE_BRL
    assert motor["fgc"]["teto_movel_brl"] == FGC_ROLLING_CAP_BRL
    assert set(motor["produtos"]) == set(PRODUCT_RULES)
    for nome, regra in PRODUCT_RULES.items():
        assert motor["produtos"][nome]["fgc"] == regra["fgc"]
        assert motor["produtos"][nome]["ir"] == regra["ir"]


def _resumo_fgc(tmp_path: Path, exposicao: dict) -> dict:
    """Roda a conta de FGC do navegador, a mesma que a tela usa."""
    programa = "\n".join([
        "const DADOS = " + json.dumps(
            {"renda_fixa": {"motor": motor_para_navegador(), "cdi_anual": CDI,
                            "ipca_anual": IPCA}}, ensure_ascii=False) + ";",
        REGUA_RF_JS,
        "const limites = DADOS.renda_fixa.motor.fgc;",
        "console.log(JSON.stringify(resumoFgc(" + json.dumps(exposicao) + ", limites)));",
    ])
    arquivo = tmp_path / "fgc.mjs"
    arquivo.write_text(programa, encoding="utf-8")
    node = shutil.which("node")
    assert node, "node é necessário para conferir a conta do FGC"
    return json.loads(subprocess.run([node, str(arquivo)], capture_output=True, text=True,
                                     encoding="utf-8", check=True).stdout)


def test_o_teto_por_emissor_soma_todos_os_estouros_e_nao_so_o_primeiro(tmp_path) -> None:
    r = _resumo_fgc(tmp_path, {"Alfa": 400_000, "Beta": 310_000, "Gama": 100_000})
    assert r["estouros"] == ["Alfa", "Beta"]
    assert r["excedente_por_emissor"] == pytest.approx(150_000 + 60_000)
    # Gama está dentro do limite e não aparece na lista, mas conta para o teto móvel.
    assert r["coberto"] == pytest.approx(250_000 + 250_000 + 100_000)


def test_espalhar_por_muitos_bancos_nao_levanta_o_teto_de_quatro_anos(tmp_path) -> None:
    """Quinze posições de 200 mil, nenhuma estourando, e mesmo assim descoberta.

    É o caso que o aviso anterior não via: ele só olhava o limite por emissor,
    então uma carteira de três milhões espalhada em quinze bancos passava sem
    nenhum aviso, com dois milhões fora do que a garantia paga.
    """
    exposicao = {f"Banco {i}": 200_000 for i in range(15)}
    r = _resumo_fgc(tmp_path, exposicao)
    assert r["estouros"] == []
    assert r["excedente_por_emissor"] == 0
    assert r["coberto"] == pytest.approx(3_000_000)
    assert r["acima_do_teto_movel"] is True
    assert r["excedente_movel"] == pytest.approx(2_000_000)


def test_exatamente_no_teto_movel_nao_e_estouro(tmp_path) -> None:
    r = _resumo_fgc(tmp_path, {f"Banco {i}": 250_000 for i in range(4)})
    assert r["coberto"] == pytest.approx(1_000_000)
    assert r["acima_do_teto_movel"] is False
    assert r["excedente_movel"] == 0
