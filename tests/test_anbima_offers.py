# -*- coding: utf-8 -*-
"""O coletor da ANBIMA: converte certo e não vaza credencial.

O teste não toca a rede. Ele injeta uma função de abertura falsa, o que também
serve de contrato: se alguém trocar urllib por outra biblioteca sem manter o
ponto de injeção, o teste quebra antes de o programa ir para produção às cegas.

O que importa aqui não é a taxa de nenhum papel, é a disciplina em volta dela:
credencial só do ambiente, segredo fora de log e de arquivo, e o regime do papel
viajando junto para a alocação não confundir debênture com CDB.
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

import build_anbima_offers as coletor  # noqa: E402

SEGREDO = "segredo-que-nao-pode-vazar"


class RespostaFalsa(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _abrir(mapa):
    """Devolve uma função de abertura que responde pelo caminho pedido."""
    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        for pedaco, corpo in mapa.items():
            if pedaco in alvo:
                return RespostaFalsa(json.dumps(corpo).encode("utf-8"))
        raise AssertionError(f"pedido inesperado: {alvo}")
    return abrir


@pytest.fixture
def ambiente(monkeypatch):
    monkeypatch.setenv("ANBIMA_CLIENT_ID", "um-id")
    monkeypatch.setenv("ANBIMA_CLIENT_SECRET", SEGREDO)


def test_sem_credencial_o_programa_para_em_vez_de_adivinhar(monkeypatch, tmp_path) -> None:
    # Aponta para um diretório vazio: numa máquina de quem desenvolve a
    # credencial de verdade existe, e o teste não pode depender de ela faltar.
    monkeypatch.setattr(coletor, "ARQUIVOS_DE_CREDENCIAL", (tmp_path / "nada.env",))
    monkeypatch.delenv("ANBIMA_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANBIMA_CLIENT_SECRET", raising=False)
    with pytest.raises(coletor.SemCredencial):
        coletor.credencial()


def test_o_token_usa_basic_com_o_par_em_base64(ambiente) -> None:
    import base64

    vistos = {}

    def abrir(pedido, timeout=None):
        vistos["auth"] = pedido.get_header("Authorization")
        vistos["corpo"] = json.loads(pedido.data.decode("utf-8"))
        return RespostaFalsa(json.dumps({"access_token": "abc", "expires_in": 3600}).encode())

    assert coletor.token("https://exemplo", abrir=abrir) == "abc"
    esperado = base64.b64encode(f"um-id:{SEGREDO}".encode("utf-8")).decode("ascii")
    assert vistos["auth"] == f"Basic {esperado}"
    assert vistos["corpo"] == {"grant_type": "client_credentials"}


def test_erro_de_autenticacao_nao_repete_o_segredo(ambiente) -> None:
    """A ANBIMA pode ecoar o enviado num 4xx, e log é onde segredo vaza."""
    def abrir(pedido, timeout=None):
        raise urllib.error.HTTPError(
            pedido.full_url, 401, f"credencial {SEGREDO} inválida", {},
            io.BytesIO(f'{{"erro": "{SEGREDO}"}}'.encode("utf-8")))

    with pytest.raises(SystemExit) as caiu:
        coletor.token("https://exemplo", abrir=abrir)
    assert SEGREDO not in str(caiu.value)
    assert "401" in str(caiu.value)


def test_a_taxa_usada_e_a_indicativa_e_o_arquivo_diz_isso(ambiente, tmp_path) -> None:
    linha = {"codigo_ativo": "ABCD11", "data_vencimento": "2030-05-15",
             "taxa_indicativa": "7,45", "taxa_compra": "9,90", "taxa_venda": "5,10",
             "indice": "IPCA", "emissor": "Empresa Exemplo"}
    documento = coletor.coletar("sandbox", abrir=_abrir({
        "oauth/access-token": {"access_token": "abc"},
        "debentures/mercado-secundario": [linha],
        "cri-cra/mercado-secundario": [],
    }))
    papel = documento["products"][0]
    # 7,45 e não 9,90: escolher a ponta conveniente infla a comparação sem
    # mentir em nenhum número isolado, então a escolha fica no arquivo.
    assert papel["rate"] == pytest.approx(0.0745)
    assert papel["index"] == "IPCA+"
    assert papel["maturity"] == "2030-05-15"
    assert "indicativa" in documento["rate_source"]


def test_o_regime_viaja_com_o_papel_para_a_alocacao_nao_confundir(ambiente) -> None:
    """Debênture não tem FGC, e o catálogo precisa saber sem consultar prosa."""
    from fixed_income_catalog import PRODUCT_RULES

    documento = coletor.coletar("sandbox", abrir=_abrir({
        "oauth/access-token": {"access_token": "abc"},
        "debentures/mercado-secundario": [
            {"codigo_ativo": "X", "data_vencimento": "2031-01-01",
             "taxa_indicativa": 6.0, "indice": "DI"}],
        "cri-cra/mercado-secundario": [],
    }))
    assert "FGC" in documento["regime"]
    for papel in documento["products"]:
        assert papel["kind"] in PRODUCT_RULES, papel["kind"]
        assert PRODUCT_RULES[papel["kind"]]["fgc"] is False


def test_linha_incompleta_e_descartada_e_nao_vira_papel_com_taxa_zero(ambiente) -> None:
    """Sem vencimento não há imposto; sem taxa não há comparação."""
    documento = coletor.coletar("sandbox", abrir=_abrir({
        "oauth/access-token": {"access_token": "abc"},
        "debentures/mercado-secundario": [
            {"codigo_ativo": "SEMVENC", "taxa_indicativa": 5.0, "indice": "DI"},
            {"codigo_ativo": "SEMTAXA", "data_vencimento": "2030-01-01", "indice": "DI"},
            {"codigo_ativo": "OUTROIDX", "data_vencimento": "2030-01-01",
             "taxa_indicativa": 5.0, "indice": "TR"},
        ],
        "cri-cra/mercado-secundario": [],
    }))
    assert documento["products"] == []
    contagem = documento["por_fonte"]["debentures/mercado-secundario"]
    assert (contagem["linhas"], contagem["convertidas"]) == (3, 0)


def test_o_repositorio_nao_guarda_credencial_da_anbima() -> None:
    """A mesma regra do certificado da B3, aplicada à chave nova."""
    suspeitos = ("ANBIMA_CLIENT_SECRET=", "client_secret\":", "client_secret =")
    for caminho in [*(ROOT / "tools").glob("*.py"), *ROOT.glob("*.py"),
                    *(ROOT / "data").glob("*.json")]:
        texto = caminho.read_text(encoding="utf-8", errors="ignore")
        for marca in suspeitos:
            assert marca not in texto, f"{caminho.name} parece guardar segredo"


def test_a_versao_que_respondeu_fica_gravada_e_o_404_desce_de_versao(ambiente) -> None:
    """Os caminhos do v2 não estão na documentação pública, então descobre-se.

    Um 404 significa "esta rota não existe nesta versão" e faz cair para a
    anterior. Um 403 não: ele diz que o app não tem o produto habilitado, e
    descer de versão nesse caso esconderia um problema de contratação atrás de
    um resultado vazio.
    """
    tentadas = []

    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        if "oauth/access-token" in alvo:
            return RespostaFalsa(json.dumps({"access_token": "abc"}).encode("utf-8"))
        tentadas.append(alvo)
        if "/v2/" in alvo:
            raise urllib.error.HTTPError(alvo, 404, "não existe", {}, io.BytesIO(b"{}"))
        return RespostaFalsa(json.dumps([]).encode("utf-8"))

    documento = coletor.coletar("sandbox", abrir=abrir)
    assert all(c["versao"] == "v1" for c in documento["por_fonte"].values())
    assert any("/v2/" in x for x in tentadas) and any("/v1/" in x for x in tentadas)
    assert documento["api_version_requested"] == "auto"


def test_403_nao_faz_cair_de_versao_porque_nao_e_rota_ausente(ambiente) -> None:
    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        if "oauth/access-token" in alvo:
            return RespostaFalsa(json.dumps({"access_token": "abc"}).encode("utf-8"))
        raise urllib.error.HTTPError(alvo, 403, "sem produto", {}, io.BytesIO(b"{}"))

    with pytest.raises(SystemExit) as caiu:
        coletor.coletar("sandbox", abrir=abrir)
    assert "403" in str(caiu.value) and "Habilite" in str(caiu.value)


def test_abrir_e_so_por_nome_para_engano_posicional_nao_alcancar_a_rede() -> None:
    """Foi assim que um teste chamou a ANBIMA de verdade sem ninguém notar."""
    import inspect

    for funcao in (coletor.token, coletor.buscar, coletor.coletar,
                   coletor.buscar_na_melhor_versao):
        parametro = inspect.signature(funcao).parameters["abrir"]
        assert parametro.kind is inspect.Parameter.KEYWORD_ONLY, funcao.__name__


def test_a_credencial_pode_vir_de_arquivo_ignorado_pelo_git(monkeypatch, tmp_path) -> None:
    """"Não sei onde por" é o começo de todo segredo commitado."""
    monkeypatch.delenv("ANBIMA_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANBIMA_CLIENT_SECRET", raising=False)
    arquivo = tmp_path / ".env.anbima"
    arquivo.write_text("\n".join([
        "# comentario",
        "ANBIMA_CLIENT_ID=do-arquivo",
        'ANBIMA_CLIENT_SECRET="aspas"',
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(coletor, "ARQUIVOS_DE_CREDENCIAL", (arquivo,))
    assert coletor.credencial() == ("do-arquivo", "aspas")


def test_o_ambiente_vence_o_arquivo(monkeypatch, tmp_path) -> None:
    """Em produção a variável manda; o arquivo é conveniência de quem roda local."""
    arquivo = tmp_path / ".env.anbima"
    arquivo.write_text("\n".join([
        "ANBIMA_CLIENT_ID=do-arquivo", "ANBIMA_CLIENT_SECRET=x",
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(coletor, "ARQUIVOS_DE_CREDENCIAL", (arquivo,))
    monkeypatch.setenv("ANBIMA_CLIENT_ID", "do-ambiente")
    monkeypatch.setenv("ANBIMA_CLIENT_SECRET", "y")
    assert coletor.credencial() == ("do-ambiente", "y")


def test_nenhum_arquivo_de_credencial_esta_rastreado_pelo_git() -> None:
    """A pergunta certa é ao git, não ao .gitignore.

    A versão anterior deste teste procurava o nome no .gitignore e passava. Um
    arquivo com client_id e client_secret reais foi commitado e publicado num
    repositório público com este teste verde, porque o .gitignore não alcança
    arquivo que já entrou no índice. O proxy passava; a propriedade não.
    """
    import subprocess

    for caminho in coletor.ARQUIVOS_DE_CREDENCIAL:
        rastreado = subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(caminho)],
            cwd=str(ROOT), capture_output=True)
        assert rastreado.returncode != 0, f"{caminho} está sob controle de versão"


def test_o_carregador_recusa_ler_de_arquivo_versionado(monkeypatch, tmp_path) -> None:
    """Recusar é melhor que avisar: o próximo commit não pergunta."""
    arquivo = tmp_path / "credencial.env"
    arquivo.write_text("\n".join([
        "ANBIMA_CLIENT_ID=x", "ANBIMA_CLIENT_SECRET=y",
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(coletor, "ARQUIVOS_DE_CREDENCIAL", (arquivo,))
    monkeypatch.setattr(coletor, "_versionado", lambda _: True)
    monkeypatch.delenv("ANBIMA_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANBIMA_CLIENT_SECRET", raising=False)
    with pytest.raises(coletor.SemCredencial) as caiu:
        coletor.credencial()
    assert "git rm --cached" in str(caiu.value)


def test_o_primeiro_lugar_procurado_fica_fora_do_repositorio() -> None:
    """Arquivo dentro do repo depende do .gitignore ter efeito. Fora, não."""
    primeiro = coletor.ARQUIVOS_DE_CREDENCIAL[0]
    assert ROOT not in primeiro.parents, primeiro


def test_fundos_usa_o_proprio_feed_e_nao_o_de_precos(ambiente) -> None:
    pedidos = []

    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        if "oauth/access-token" in alvo:
            return RespostaFalsa(json.dumps({"access_token": "abc"}).encode("utf-8"))
        pedidos.append(alvo)
        return RespostaFalsa(json.dumps([{"cnpj": "00.000.000/0001-00"}]).encode("utf-8"))

    documento = coletor.coletar_fundos("sandbox", abrir=abrir)
    assert all("/feed/fundos/" in x for x in pedidos), pedidos
    assert not any("precos-indices" in x for x in pedidos)
    assert documento["rotas"]["fundos"]["linhas"] == 1


def test_fundo_nao_entra_na_regua_de_ofertas(ambiente) -> None:
    """Retorno realizado e taxa contratada não se comparam sem hipótese declarada."""
    def abrir(pedido, timeout=None):
        if "oauth/access-token" in pedido.full_url:
            return RespostaFalsa(json.dumps({"access_token": "abc"}).encode("utf-8"))
        return RespostaFalsa(json.dumps([]).encode("utf-8"))

    documento = coletor.coletar_fundos("sandbox", abrir=abrir)
    assert "products" not in documento
    assert "come-cotas" in documento["aviso"]
    assert coletor.DESTINO_FUNDOS != coletor.DESTINO


def test_401_faz_trocar_de_cabecalho_antes_de_desistir(ambiente) -> None:
    """A documentação não diz como mandar o token na chamada ao feed.

    Então o programa tenta as candidatas. Aqui a primeira é recusada e a segunda
    aceita, e o arquivo tem de registrar qual funcionou: sem isso, a próxima
    pessoa adivinha de novo.
    """
    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        if "oauth/access-token" in alvo:
            return RespostaFalsa(json.dumps({"access_token": "abc"}).encode("utf-8"))
        if pedido.get_header("Access_token") is not None:
            raise urllib.error.HTTPError(alvo, 401, "recusado", {}, io.BytesIO(b"{}"))
        return RespostaFalsa(json.dumps([]).encode("utf-8"))

    documento = coletor.coletar("sandbox", abrir=abrir)
    assert all(c["cabecalho"] == "bearer" for c in documento["por_fonte"].values())


def test_401_em_todos_os_cabecalhos_explica_o_que_conferir(ambiente) -> None:
    def abrir(pedido, timeout=None):
        alvo = pedido.full_url
        if "oauth/access-token" in alvo:
            return RespostaFalsa(json.dumps({"access_token": "abc"}).encode("utf-8"))
        raise urllib.error.HTTPError(alvo, 401, "recusado", {}, io.BytesIO(b"{}"))

    with pytest.raises(SystemExit) as caiu:
        coletor.coletar("sandbox", abrir=abrir)
    mensagem = str(caiu.value)
    assert "401" in mensagem
    # A saída precisa dizer o que conferir, e não só que deu errado.
    assert "sandbox" in mensagem and "produção" in mensagem
