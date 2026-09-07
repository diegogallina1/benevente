# -*- coding: utf-8 -*-
"""O coletor de dados abertos: descobre certo, pagina certo e não inventa nada.

O teste não toca a rede. Ele injeta uma função de abertura falsa, o que também
serve de contrato: se alguém trocar urllib por outra biblioteca sem manter o
ponto de injeção, o teste quebra antes de o programa sair chamando trezentos
hosts de terceiros às cegas.

O que importa aqui não é o número de nenhuma instituição. É a disciplina em
volta dele: descoberta pelo caminho da especificação e não por um nome de
família suposto, paginação que não repete a primeira página vinte vezes, host
fora do ar que não derruba os outros, e nenhuma credencial em lugar nenhum.
"""
from __future__ import annotations

from pathlib import Path
import io
import json
import sys
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_open_finance_investments as coletor  # noqa: E402

BASE = "https://api.bancoexemplo.com.br/open-banking/opendata-investments/v1"


class RespostaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def diretorio(*organizacoes) -> list:
    return list(organizacoes)


def organizacao(nome, cnpj, *enderecos, status="Active"):
    return {
        "OrganisationName": nome,
        "RegistrationNumber": cnpj,
        "Status": status,
        "AuthorisationServers": [{
            "CustomerFriendlyName": nome,
            "ApiResources": [{
                "ApiFamilyType": "opendata-investments",
                "ApiVersion": "1.0.1",
                "ApiDiscoveryEndpoints": [{"ApiEndpoint": e} for e in enderecos],
            }],
        }],
    }


def _abrir(mapa, vistos=None):
    """Responde pelo trecho do endereço pedido, e anota o que foi pedido."""
    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        if vistos is not None:
            vistos.append(pedido)
        for pedaco, corpo in mapa.items():
            if pedaco in alvo:
                if isinstance(corpo, Exception):
                    raise corpo
                return RespostaFalsa(json.dumps(corpo).encode("utf-8"))
        raise AssertionError(f"pedido inesperado: {alvo}")
    return abrir


def pagina(itens, total_paginas=1) -> dict:
    return {"data": itens, "links": {}, "meta": {"totalRecords": len(itens),
                                                 "totalPages": total_paginas}}


# --- descoberta -------------------------------------------------------------

def test_a_base_sai_do_caminho_e_nao_do_nome_da_familia() -> None:
    """As duas formas do diretório viram a mesma base, e o resto não vira nada."""
    assert coletor.base_do_endpoint(BASE) == BASE
    assert coletor.base_do_endpoint(f"{BASE}/bank-fixed-incomes") == BASE
    assert coletor.base_do_endpoint(
        "https://api.b.com.br/open-banking/opendata-loans/v1/personal-loans") is None
    assert coletor.base_do_endpoint("nem-url") is None


def test_o_mesmo_participante_nao_entra_uma_vez_por_recurso_publicado() -> None:
    lista = coletor.bases_publicadas(diretorio(organizacao(
        "Banco Exemplo", "45086338000178",
        f"{BASE}/funds", f"{BASE}/bank-fixed-incomes", f"{BASE}/treasure-titles")))
    assert [p["base"] for p in lista] == [BASE]
    assert lista[0]["cnpj"] == "45086338000178"


def test_participante_inativo_fica_de_fora() -> None:
    lista = coletor.bases_publicadas(diretorio(
        organizacao("Banco Ativo", "45086338000178", BASE),
        organizacao("Banco Fora", "11111111000191",
                    "https://api.fora.com.br/open-banking/opendata-investments/v1",
                    status="Inactive")))
    assert [p["organizacao"] for p in lista] == ["Banco Ativo"]


def test_quem_nao_publica_investimentos_nao_aparece() -> None:
    """O diretório inteiro passa por aqui; só o caminho da especificação entra."""
    outra_familia = {
        "OrganisationName": "Banco Só de Empréstimo",
        "RegistrationNumber": "22222222000191",
        "Status": "Active",
        "AuthorisationServers": [{"ApiResources": [{
            "ApiFamilyType": "opendata-loans",
            "ApiDiscoveryEndpoints": [
                {"ApiEndpoint": "https://api.x.com.br/open-banking/opendata-loans/v1"}],
        }]}],
    }
    assert coletor.bases_publicadas(diretorio(outra_familia)) == []


# --- paginação --------------------------------------------------------------

def test_a_paginacao_para_no_total_declarado_pelo_envelope() -> None:
    corpos = [pagina([{"n": i} for i in range(coletor.POR_PAGINA)], total_paginas=2),
              pagina([{"n": "ultimo"}], total_paginas=2)]
    chamadas = []

    def abrir(pedido, timeout=None):
        chamadas.append(pedido.full_url)
        return RespostaFalsa(json.dumps(corpos[len(chamadas) - 1]).encode("utf-8"))

    itens = coletor.buscar_recurso(BASE, "funds", abrir=abrir)
    assert len(itens) == coletor.POR_PAGINA + 1
    assert len(chamadas) == 2
    assert "page=1" in chamadas[0] and f"page-size={coletor.POR_PAGINA}" in chamadas[0]


def test_host_que_ignora_a_pagina_nao_vira_vinte_copias() -> None:
    """Resultado grande e errado é pior que erro: mil linhas parecem resultado."""
    cheia = pagina([{"n": i} for i in range(coletor.POR_PAGINA)], total_paginas=99)
    itens = coletor.buscar_recurso(BASE, "funds", abrir=_abrir({BASE: cheia}))
    assert len(itens) == coletor.POR_PAGINA


def test_paginacao_que_nao_converge_falha_alto() -> None:
    contador = {"n": 0}

    def abrir(pedido, timeout=None):
        contador["n"] += 1
        corpo = pagina([{"n": contador["n"]}] * coletor.POR_PAGINA, total_paginas=99)
        return RespostaFalsa(json.dumps(corpo).encode("utf-8"))

    with pytest.raises(coletor.RecursoIndisponivel):
        coletor.buscar_recurso(BASE, "funds", abrir=abrir)


# --- robustez e contrato ----------------------------------------------------

def test_um_host_fora_do_ar_nao_derruba_os_outros() -> None:
    fora = "https://api.caiu.com.br/open-banking/opendata-investments/v1"

    def abrir(pedido, timeout=None):
        if fora in pedido.full_url:
            raise urllib.error.HTTPError(pedido.full_url, 429, "Too Many Requests",
                                         {}, io.BytesIO(b""))
        return RespostaFalsa(json.dumps(pagina([{"ok": True}])).encode("utf-8"))

    documento = coletor.coletar(
        abrir=abrir, pausa=0,
        diretorio=diretorio(organizacao("Banco Bom", "45086338000178", BASE),
                            organizacao("Banco Caiu", "11111111000191", fora)))
    bons = [p for p in documento["participantes"] if p["organizacao"] == "Banco Bom"]
    assert bons[0]["recursos"]["funds"]["linhas"] == 1
    assert len(documento["falhas"]) == len(coletor.RECURSOS)
    assert "HTTP 429" in documento["falhas"][0]


def test_resposta_que_nao_e_json_e_falha_nomeada_e_nao_traceback() -> None:
    def abrir(pedido, timeout=None):
        return RespostaFalsa(b"<html>portal do banco</html>")

    with pytest.raises(coletor.RecursoIndisponivel) as caiu:
        coletor.buscar_recurso(BASE, "funds", abrir=abrir)
    assert "não é JSON" in str(caiu.value)


def test_nenhuma_chamada_leva_cabecalho_de_autorizacao() -> None:
    """O contrato do módulo: dados abertos não têm esquema de segurança.

    Se um dia alguém acrescentar um cabeçalho aqui, é porque passou a chamar a
    API de dados de clientes — e essa exige ser participante autorizado, o que
    este projeto não é. O teste é o lugar onde isso para.
    """
    vistos = []
    coletor.coletar(abrir=_abrir({BASE: pagina([{"ok": True}])}, vistos), pausa=0,
                    diretorio=diretorio(organizacao("Banco Exemplo", "45086338000178", BASE)))
    assert vistos
    for pedido in vistos:
        assert pedido.get_header("Authorization") is None
        assert pedido.get_header("Access_token") is None
        assert pedido.get_method() == "GET"


def test_o_documento_diz_que_a_data_e_a_da_coleta_e_nao_a_da_apuracao() -> None:
    """A API não devolve período de referência em campo nenhum.

    Sem esse aviso escrito no arquivo, quem lê daqui a um ano supõe que a
    distribuição é do mês em que ele está lendo.
    """
    documento = coletor.coletar(
        abrir=_abrir({BASE: pagina([{"ok": True}])}), pausa=0,
        diretorio=diretorio(organizacao("Banco Exemplo", "45086338000178", BASE)))
    assert documento["colhido_em"].endswith("+00:00")
    assert "não tem campo de período de referência" in documento["aviso_de_data"]
    assert "não oferta comprável" in documento["aviso_de_uso"]
    assert documento["origem"] == "AUTOMATICA_PUBLICA"


def test_a_impressao_do_conteudo_muda_quando_o_conteudo_muda() -> None:
    """Sem hash, uma coleta seguinte alega que mudou; com hash, prova."""
    def documento_com(linhas):
        return coletor.coletar(
            abrir=_abrir({BASE: pagina(linhas)}), pausa=0,
            diretorio=diretorio(organizacao("Banco Exemplo", "45086338000178", BASE)))

    antes = documento_com([{"taxa": "1.020000"}])
    depois = documento_com([{"taxa": "1.030000"}])
    assert (antes["participantes"][0]["recursos"]["funds"]["sha256"]
            != depois["participantes"][0]["recursos"]["funds"]["sha256"])


def test_coleta_vazia_nao_apaga_coleta_boa(tmp_path) -> None:
    destino = tmp_path / "dados_abertos_open_finance.json"
    cheio = coletor.coletar(
        abrir=_abrir({BASE: pagina([{"ok": True}])}), pausa=0,
        diretorio=diretorio(organizacao("Banco Exemplo", "45086338000178", BASE)))
    coletor.gravar(destino, cheio)

    vazio = coletor.coletar(abrir=_abrir({}), pausa=0, diretorio=[])
    with pytest.raises(SystemExit) as parou:
        coletor.gravar(destino, vazio)
    assert "fica como está" in str(parou.value)
    assert json.loads(destino.read_text(encoding="utf-8"))["participantes"]
