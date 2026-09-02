# -*- coding: utf-8 -*-
"""Nenhum degrau da escada some pelo caminho, e o reconstruído diz que é.

A escada apareceu escrita à mão em seis lugares: gerador do app, do site, do
monitor diário, das mudanças, da faixa e a página de carteiras. Enquanto ela
teve três degraus, as seis cópias concordaram. Quando ganhou o quarto, cada uma
passou a errar de um jeito diferente, e nenhuma reclamou.

Este arquivo testa a propriedade, não a lista: qualquer degrau que a política
declare precisa aparecer em toda superfície que publica o ano. Acrescentar o
quinto degrau amanhã não pede edição aqui.

A segunda metade é sobre honestidade e não sobre cobertura. Três séries foram
marcadas a mercado enquanto 2026 acontecia. A quarta foi reconstruída depois,
da mesma cesta e pela mesma função, e essa diferença precisa viajar junto do
número em vez de ficar só num texto ao lado.
"""
from __future__ import annotations

from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"


def escada() -> list[str]:
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from politica import escada as declarada
    return declarada()


def _payload_do_app() -> dict:
    fonte = (WEB / "plano.js").read_text(encoding="utf-8")
    corpo = fonte[fonte.index("{", fonte.index("DADOS")):]
    return json.JSONDecoder().raw_decode(corpo)[0]


def test_todo_degrau_declarado_aparece_em_toda_superficie_de_2026() -> None:
    perfis = set(escada())
    assert len(perfis) >= 4

    vivo = json.loads((WEB / "live_profiles_2026.json").read_text(encoding="utf-8"))
    faixa = json.loads((WEB / "forecast_2026.json").read_text(encoding="utf-8"))
    mudancas = json.loads((WEB / "mudancas_2026.json").read_text(encoding="utf-8"))
    app = _payload_do_app()

    for nome, publicado in (
        ("live_profiles_2026", set(vivo["profiles"])),
        ("forecast_2026", set(faixa["profiles"])),
        ("mudancas_2026", set(mudancas["profiles"])),
        ("app: escada", set(app["profiles"])),
        ("app: acompanhamento", set(app["acompanhamento"]["perfis"])),
        ("app: mudanças", set(app["mudancas"]["perfis"])),
    ):
        assert perfis <= publicado, f"{nome} perdeu {sorted(perfis - publicado)}"

    for perfil in perfis:
        assert (WEB / f"current_decision_2026_{perfil}.json").exists(), perfil
        assert (WEB / f"live_performance_{perfil}.json").exists(), perfil


def test_a_serie_reconstruida_nao_se_passa_por_acompanhada() -> None:
    vivo = json.loads((WEB / "live_profiles_2026.json").read_text(encoding="utf-8"))
    faixa = json.loads((WEB / "forecast_2026.json").read_text(encoding="utf-8"))
    app = _payload_do_app()

    reconstruidos = [p for p, r in vivo["profiles"].items() if r.get("reconstructed")]
    assert reconstruidos, "nenhum perfil marcado: ou a marca sumiu, ou o campo mudou de nome"

    for perfil in reconstruidos:
        livro = json.loads((WEB / f"current_decision_2026_{perfil}.json").read_text(encoding="utf-8"))
        # De onde veio a cesta, e que a data de derivação não se confunde com a
        # data em que a seleção foi decidida. Fundir as duas transformaria uma
        # reconstrução de agosto numa decisão de janeiro.
        assert livro["derivation"]["selection_decided_on"] < livro["derivation"]["derived_on"]
        # A faixa de quem foi declarado com o ano em curso não pode se
        # apresentar como declarada antes do ano.
        assert faixa["profiles"][perfil]["band_declared_before_year"] is False
        assert app["acompanhamento"]["perfis"][perfil]["faixa_de_janeiro"] is False

    # A versão anterior deste bloco exigia que as três faixas "de janeiro" se
    # dissessem declaradas antes do ano. Era a narrativa, não o dado: o cone foi
    # gerado em 27/08/2026 com semente 20260826, a v3 foi registrada em 26/08, e
    # a série diária foi commitada em 26/08. Nenhuma faixa de 2026 existia antes
    # de 2026. O teste agora exige o contrário, e exige que a data publicada seja
    # a de agosto e não um literal de janeiro.
    for perfil, r in faixa["profiles"].items():
        assert r["band_declared_before_year"] is False, perfil
        assert r["band_drawn_on"] >= "2026-08-26", (perfil, r["band_drawn_on"])
        assert app["acompanhamento"]["perfis"][perfil]["faixa_de_janeiro"] is False, perfil

    # E a tela não pode continuar dizendo "projetada em janeiro" para todo mundo.
    tela = (WEB / "plano.js").read_text(encoding="utf-8")
    assert "faixa_de_janeiro ? " in tela


def test_nenhum_gerador_carrega_a_propria_copia_da_escada() -> None:
    """A lista escrita à mão é o defeito, e ele reaparece por cópia."""
    # Duas formas da mesma cópia: a lista de literais do Python e do JavaScript,
    # e a sequência solta de um laço de shell. A segunda escapou da primeira
    # varredura e ficou meses publicando três perfis de quatro.
    copiada = re.compile(r'"conservador"\s*,\s*"equilibrado"\s*,\s*"arrojado"'
                         r'|conservador\s+equilibrado\s+arrojado')
    alvos = [*(ROOT / "tools").glob("*.py"), *WEB.glob("*.js"),
             *(ROOT / ".github" / "workflows").glob("*.yml")]
    culpados = []
    for caminho in alvos:
        texto = caminho.read_text(encoding="utf-8")
        # A linha que explica o defeito pode nomear os três sem cometê-lo.
        texto = "\n".join(
            linha for linha in texto.splitlines() if not linha.strip().startswith("#"))
        if copiada.search(texto):
            culpados.append(str(caminho.relative_to(ROOT)))
    assert not culpados, f"escada copiada em {culpados}: leia de tools/politica.py"


def test_a_declaracao_congelada_nao_foi_reescrita_para_caber_o_que_veio_depois() -> None:
    """O que mudou depois entra como adendo datado, não por cima do registro."""
    import hashlib

    registro = ROOT / "data" / "benevente_profile_ladder_v4_registration.json"
    declarado = json.loads(registro.read_text(encoding="utf-8"))
    assert declarado["registration_sha256"].startswith("4d8fb114c92188239d456370550b173c")
    # A frase original continua lá: o degrau não foi acompanhado, e não passa a
    # ter sido só porque agora existe uma reconstrução publicada.
    assert "não carrega acompanhamento de 2026" in declarado["asymmetry_disclosure"]

    adendo = json.loads((ROOT / "data" / "benevente_profile_ladder_v4_tracking_addendum.json")
                        .read_text(encoding="utf-8"))
    assert adendo["amends_sha256"] == declarado["registration_sha256"]
    corpo = {k: v for k, v in adendo.items() if k != "addendum_sha256"}
    esperado = hashlib.sha256(
        json.dumps(corpo, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")).hexdigest()
    assert adendo["addendum_sha256"] == esperado, "o adendo foi editado sem refazer o hash"
    assert adendo["band"]["declared_before_year"] is False
