"""O cliente da B3, exercitado sem credencial nenhuma.

Ninguém tem o certificado antes do contrato, então a lógica que decide se uma
leitura serve precisa ser testável sem rede. O transporte é injetado e aqui é um
dublê com respostas gravadas; o que se testa é o portão de consentimento, o
limite diário e — o mais importante — a diferença entre "não teve movimento" e
"não atualizou".

Essa distinção é a razão deste arquivo existir. Com SLA de 97% ao mês, a
carteira deixa de chegar por volta de uma vez por mês. Uma tela que confunde os
dois casos mostra a posição de anteontem como se fosse a de ontem, sem avisar, e
o cliente decide vender com base nela.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from b3_client import (CONSULTAS_POR_DIA, B3Client, ConfiguracaoAusente, Credenciais,
                       Endpoints, Frescor, LimiteDiario, LivroDeChamadas, classificar,
                       referencia_esperada)

DOC = "a" * 64
TOKEN = "token-de-teste"
COMPLETO = Endpoints(posicao="/api/posicao/v3/investidor", movimentacao="/api/mov/v2",
                     negociacao="/api/neg/v2", guia="/api/guia/v1",
                     autorizacao="/api/autorizacao/v1")


def transporte(respostas: dict):
    """Dublê: casa pelo caminho e devolve (status, corpo) gravados."""
    chamadas = []

    def _t(metodo, url, headers, params):
        chamadas.append((metodo, url, dict(params)))
        assert headers["Authorization"] == f"Bearer {TOKEN}"
        for trecho, resposta in respostas.items():
            if trecho in url:
                return resposta
        return (404, None)

    _t.chamadas = chamadas
    return _t


# --- o cliente recusa em vez de adivinhar --------------------------------

def test_caminho_nao_configurado_falha_dizendo_por_que():
    cliente = B3Client(transporte({}), Endpoints())
    with pytest.raises(ConfiguracaoAusente, match="posicao"):
        cliente.endpoints.exigir("posicao")


def test_credencial_ausente_nomeia_as_variaveis(monkeypatch):
    for var in ("B3_CERT_P12", "B3_CERT_SENHA", "B3_CA_BUNDLE", "B3_CLIENT_ID"):
        monkeypatch.delenv(var, raising=False)
    with pytest.raises(ConfiguracaoAusente, match="B3_CERT_P12"):
        Credenciais.do_ambiente()


def test_nenhum_segredo_mora_no_modulo():
    """O caminho e a senha vêm do ambiente; o repositório não guarda nada."""
    from pathlib import Path
    fonte = (Path(__file__).resolve().parents[1] / "b3_client.py").read_text(encoding="utf-8")
    for suspeito in ("BEGIN CERTIFICATE", "BEGIN PRIVATE KEY", ".p12\"", "senha=\""):
        assert suspeito not in fonte


# --- consentimento é perguntado à B3, nunca lembrado ---------------------

def test_sem_autorizacao_nada_e_lido():
    t = transporte({"/api/autorizacao/v1": (200, {"autorizado": False})})
    leitura = B3Client(t, COMPLETO).ler_posicao(DOC, TOKEN, datetime(2026, 8, 27, 10, 0))
    assert leitura.frescor is Frescor.SEM_CONSENTIMENTO
    assert leitura.payload is None
    assert not leitura.utilizavel
    assert not any("posicao" in url for _, url, _ in t.chamadas), "leu posição sem autorização"


def test_a_autorizacao_e_perguntada_a_cada_carga():
    """Um sinalizador local sobreviveria à revogação feita dentro da B3."""
    t = transporte({"/api/autorizacao/v1": (200, {"autorizado": True}),
                    "/api/posicao": (200, {"dataReferencia": "2026-08-26"})})
    cliente = B3Client(t, COMPLETO)
    cliente.ler_posicao(DOC, TOKEN, datetime(2026, 8, 27, 10, 0))
    cliente.ler_posicao("b" * 64, TOKEN, datetime(2026, 8, 27, 10, 0))
    autorizacoes = [c for c in t.chamadas if "autorizacao" in c[1]]
    assert len(autorizacoes) == 2


# --- limite de uma chamada por investidor por dia ------------------------

def test_segunda_chamada_do_dia_e_recusada():
    t = transporte({"/api/autorizacao/v1": (200, {"autorizado": True}),
                    "/api/posicao": (200, {"dataReferencia": "2026-08-26"})})
    cliente = B3Client(t, COMPLETO)
    cliente.ler_posicao(DOC, TOKEN, datetime(2026, 8, 27, 10, 0))
    with pytest.raises(LimiteDiario, match="27/08/2026"):
        cliente.ler_posicao(DOC, TOKEN, datetime(2026, 8, 27, 16, 0))
    assert CONSULTAS_POR_DIA == 1


def test_no_dia_seguinte_pode_de_novo():
    livro = LivroDeChamadas()
    livro.registrar(DOC, date(2026, 8, 27))
    livro.registrar(DOC, date(2026, 8, 28))


# --- frescor: a distinção que a tela precisa fazer -----------------------

def test_antes_das_oito_nao_ha_dado_de_ontem():
    assert referencia_esperada(datetime(2026, 8, 27, 7, 59)) is None
    assert classificar(datetime(2026, 8, 27, 7, 59), None, False) is Frescor.CEDO


def test_depois_das_oito_a_referencia_e_o_pregao_anterior():
    assert referencia_esperada(datetime(2026, 8, 27, 8, 1)) == date(2026, 8, 26)


def test_segunda_de_manha_espera_a_sexta_nao_o_domingo():
    segunda = datetime(2026, 8, 31, 9, 0)
    assert segunda.weekday() == 0
    assert referencia_esperada(segunda) == date(2026, 8, 28)


def test_sem_movimento_e_diferente_de_nao_atualizou():
    """A confusão entre os dois mostra a carteira de anteontem como a de ontem."""
    agora = datetime(2026, 8, 27, 10, 0)
    assert classificar(agora, date(2026, 8, 26), False) is Frescor.SEM_MOVIMENTO
    assert classificar(agora, date(2026, 8, 25), False) is Frescor.NAO_ATUALIZOU
    assert classificar(agora, None, False) is Frescor.NAO_ATUALIZOU


def test_sem_movimento_ainda_serve_e_nao_atualizou_nao():
    agora = datetime(2026, 8, 27, 10, 0)
    t = transporte({"/api/autorizacao/v1": (200, {"autorizado": True}),
                    "/api/posicao": (200, {"dataReferencia": "2026-08-26"})})
    boa = B3Client(t, COMPLETO).ler_posicao(DOC, TOKEN, agora, moveu=False)
    assert boa.frescor is Frescor.SEM_MOVIMENTO and boa.utilizavel

    t2 = transporte({"/api/autorizacao/v1": (200, {"autorizado": True}),
                     "/api/posicao": (200, {"dataReferencia": "2026-08-20"})})
    velha = B3Client(t2, COMPLETO).ler_posicao(DOC, TOKEN, agora)
    assert velha.frescor is Frescor.NAO_ATUALIZOU and not velha.utilizavel
    assert velha.atraso_em_dias == 7


def test_falha_da_api_nao_vira_dado_bom():
    t = transporte({"/api/autorizacao/v1": (200, {"autorizado": True}),
                    "/api/posicao": (503, None)})
    leitura = B3Client(t, COMPLETO).ler_posicao(DOC, TOKEN, datetime(2026, 8, 27, 10, 0))
    assert leitura.frescor is Frescor.NAO_ATUALIZOU
    assert not leitura.utilizavel


def test_a_tela_recebe_o_estado_junto_do_dado():
    t = transporte({"/api/autorizacao/v1": (200, {"autorizado": True}),
                    "/api/posicao": (200, {"dataReferencia": "2026-08-20"})})
    para_tela = B3Client(t, COMPLETO).ler_posicao(
        DOC, TOKEN, datetime(2026, 8, 27, 10, 0)).para_tela()
    assert para_tela["utilizavel"] is False
    assert para_tela["atraso_em_dias"] == 7
    assert "não atualizou" in para_tela["explicacao"]


def test_a_guia_diz_quem_se_moveu():
    t = transporte({"/api/guia/v1": (200, {"documentos": [DOC, "c" * 64]})})
    assert B3Client(t, COMPLETO).documentos_com_movimentacao(
        TOKEN, date(2026, 8, 26)) == {DOC, "c" * 64}


def test_guia_indisponivel_nao_inventa_lista():
    t = transporte({"/api/guia/v1": (500, None)})
    assert B3Client(t, COMPLETO).documentos_com_movimentacao(TOKEN, date(2026, 8, 26)) == set()


# --- nada de material criptográfico no repositório ------------------------

def test_o_repositorio_nao_versiona_certificado_nem_chave():
    """O .p12 da B3 vira PEM na conversão, e um dos arquivos é chave privada.

    Converter dentro do repositório é o caminho natural de quem está com pressa.
    Este teste existe para que o commit seguinte não vaze a chave.
    """
    import subprocess
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    versionados = subprocess.run(["git", "ls-files"], cwd=raiz, capture_output=True,
                                 text=True, check=True).stdout.splitlines()
    perigosos = [f for f in versionados
                 if f.lower().endswith((".p12", ".pfx", ".jks", ".pem", ".key",
                                        ".crt", ".cer"))]
    assert not perigosos, f"material criptográfico versionado: {perigosos}"

    ignore = (raiz / ".gitignore").read_text(encoding="utf-8")
    for padrao in ("*.p12", "*.pem", "*.key", "*.jks"):
        assert padrao in ignore, f".gitignore não cobre {padrao}"


def test_a_verificacao_de_certificado_nunca_e_desligada():
    """verify=False faz a conexão funcionar e deixa de ser TLS mútuo de fato."""
    from pathlib import Path
    fonte = (Path(__file__).resolve().parents[1] / "b3_client.py").read_text(encoding="utf-8")
    assert "verify = False" not in fonte and "verify=False" not in fonte
    assert "sessao.verify = credenciais.ca_bundle" in fonte
