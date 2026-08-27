"""Fase 0 do canal: a fila precisa estar certa antes de existir entrega.

Um alerta errado no celular de alguém não se desfaz. Esta fase existe para que
a lógica de gatilho seja conferida à mão por semanas, e os testes prendem as
propriedades que tornam essa conferência possível: nada é enviado, nada duplica,
todo item se rastreia até um artefato e a cadeia não pode ser reescrita em
silêncio.
"""
from pathlib import Path
import json

import pytest

from tools.notify_queue import TEMPLATES, run

ROOT = Path(__file__).resolve().parents[1]
FILA = ROOT / "artifacts" / "notification_queue" / "queue.json"


@pytest.fixture(scope="module")
def fila():
    return json.loads(FILA.read_text(encoding="utf-8"))


def test_a_fase_zero_nao_entrega_nada(fila) -> None:
    assert fila["phase"] == "0_dry_run"
    assert all(item["state"] == "queued_dry_run" for item in fila["items"])
    fonte = (ROOT / "tools" / "notify_queue.py").read_text(encoding="utf-8")
    for proibido in ("requests.post", "urlopen", "graph.facebook.com", "api.whatsapp"):
        assert proibido not in fonte, f"a Fase 0 não pode conter caminho de envio: {proibido}"


def test_todo_item_se_rastreia_ate_um_artefato(fila) -> None:
    """O item aponta para um arquivo real, com hash bem formado.

    A versão anterior deste teste comparava o hash guardado com o hash atual do
    arquivo, e estava errada de um jeito que só apareceria em produção: o
    acompanhamento reescreve ``web/live_performance_*.json`` todo pregão, e um
    alerta enfileirado ontem passaria a apontar para um hash que não existe mais.
    A CI quebraria no dia seguinte ao primeiro alerta.

    O retrato é imutável de propósito — é justamente ele que permite dizer, três
    anos depois, qual versão do artefato originou o alerta. O que se verifica
    aqui é a forma; que o hash seja o do arquivo no momento em que foi escrito é
    verificado em test_o_hash_gravado_e_o_do_arquivo_no_momento_do_registro.
    """
    for item in fila["items"]:
        origem = ROOT / "web" / item["source"]["file"]
        assert origem.exists(), item["source"]["file"]
        sha = item["source"]["sha256"]
        assert len(sha) == 64 and all(c in "0123456789abcdef" for c in sha), item["key"]


def test_o_hash_gravado_e_o_do_arquivo_no_momento_do_registro(tmp_path) -> None:
    """A propriedade que o teste acima não pode mais conferir retroativamente."""
    import hashlib

    from tools.notify_queue import _item

    origem = tmp_path / "live_performance_conservador.json"
    origem.write_text('{"a": 1}', encoding="utf-8")
    esperado = hashlib.sha256(origem.read_bytes()).hexdigest()

    item = _item("radar_revisao", "k", {"quantidade": "1", "tickers": "X", "data": "01/01/2026"},
                 origem, None)
    assert item["source"]["sha256"] == esperado

    # E muda quando o arquivo muda: o retrato é do conteúdo, não do nome.
    origem.write_text('{"a": 2}', encoding="utf-8")
    outro = _item("radar_revisao", "k2", {"quantidade": "1", "tickers": "X", "data": "01/01/2026"},
                  origem, None)
    assert outro["source"]["sha256"] != esperado


def test_a_cadeia_nao_pode_ser_reescrita_em_silencio(fila) -> None:
    import hashlib
    anterior = None
    for item in fila["items"]:
        assert item["previous_record_sha256"] == anterior
        corpo = {k: v for k, v in item.items() if k != "record_sha256"}
        esperado = hashlib.sha256(
            json.dumps(corpo, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert item["record_sha256"] == esperado, f"{item['key']} foi editado depois de enfileirado"
        anterior = item["record_sha256"]


def test_rodar_de_novo_nao_duplica(tmp_path) -> None:
    """O pipeline roda todo dia útil; sem chave estável, o alerta repetiria diariamente."""
    primeira = run(tmp_path)
    segunda = run(tmp_path)
    assert segunda["novos"] == []
    assert segunda["total"] == primeira["total"]


def test_o_texto_vem_de_modelo_e_nao_de_geracao(fila) -> None:
    """A plataforma exige modelo aprovado fora da janela de conversa.

    Se o texto fosse gerado, cada alerta seria um texto novo e nenhum deles
    passaria pela aprovação prévia. O modelo fica no código e só os campos mudam.
    """
    for item in fila["items"]:
        modelo = TEMPLATES[item["template"]]
        assert set(item["variables"]) == set(modelo["campos"])
        assert item["preview"] == modelo["texto"].format(**item["variables"])


def test_todo_alerta_lembra_que_nao_ha_ordem(fila) -> None:
    """A propriedade que mantém o produto dentro do que o escritório pode fazer."""
    for item in fila["items"]:
        if item["template"] == "radar_revisao":
            assert "não altera pesos" in item["preview"]
        else:
            assert "Nenhuma ordem foi transmitida" in item["preview"]


def test_a_exposicao_do_alerta_bate_com_o_acompanhamento(fila) -> None:
    """O número do alerta é o número publicado, não um recálculo paralelo."""
    for item in fila["items"]:
        if item["template"] != "camada_mudou":
            continue
        perfil = item["key"].split(":")[1]
        live = json.loads((ROOT / "web" / f"live_performance_{perfil}.json").read_text(encoding="utf-8"))
        alvos = {d["effective_on"]: d["target_equity_weight"]
                 for d in live["benevente2_overlay"]["risk_decisions"]}
        data = item["key"].split(":")[2]
        esperado = f"{alvos[data] * 100:.1f}%".replace(".", ",")
        assert item["variables"]["exposicao_depois"] == esperado
