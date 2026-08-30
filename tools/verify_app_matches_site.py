# -*- coding: utf-8 -*-
"""O app e o site dizem a mesma coisa?

O site e o protótipo do app nasceram de artefatos comuns, mas nada obrigava os
dois a continuarem de acordo. São superfícies diferentes, editadas em momentos
diferentes, e a divergência que aparece primeiro nunca é numérica: é de
linguagem. Foi o que aconteceu — o cartão do app dizia "1 de 2 módulos" para
alguém que nunca leu a tabela de /versoes onde a palavra é definida.

Este verificador cobre as duas coisas. Que os números do app sejam os mesmos que
o site publica, e que o app não use vocabulário que só existe no site.

Roda junto dos testes. Se falhar, uma das duas superfícies mudou sozinha.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from client_intake import PROFILES, WORST_DRAWDOWN  # noqa: E402
from fixed_income_catalog import FGC_PER_CONGLOMERATE_BRL  # noqa: E402

APP = ROOT / "artifacts" / "portfolio_mapping_v1" / "mapping_by_profile.json"
TELA = ROOT / "docs" / "desenho_tela_mapa.html"
REGISTRO = ROOT / "data" / "benevente_profile_ladder_v3_registration.json"
INDEX = ROOT / "web" / "index.html"

#: Palavras que o site define em algum canto e que o app não pode usar sem
#: explicar. Quem chega pelo app não leu /versoes.
JARGAO_PROIBIDO = (
    "módulo", "módulos",          # o site só define a palavra numa tabela em /versoes
    "overlay", "sleeve", "drawdown", "backtest",   # inglês do manuscrito
    "endpoint", "isin",           # especificação da API, não texto de investidor
    "cesta", "escopo",            # jargão tributário e nosso, não do cliente
    "perna",                      # gíria de mesa
)


def checar() -> list[tuple[bool, str]]:
    app = json.loads(APP.read_text(encoding="utf-8"))
    registro = json.loads(REGISTRO.read_text(encoding="utf-8"))
    index = INDEX.read_text(encoding="utf-8")
    tela = TELA.read_text(encoding="utf-8")
    r: list[tuple[bool, str]] = []

    # --- os mesmos números nas duas superfícies ---
    for perfil in PROFILES:
        alvo = registro["profiles"][perfil]
        dados = app["profiles"][perfil]
        livro = json.loads((ROOT / "web" / f"current_decision_2026_{perfil}.json")
                           .read_text(encoding="utf-8"))
        acoes = [h for h in livro["holdings"] if h["ticker"] != "IVVB11"]

        r.append((abs(dados["adaptar"]["equity_budget"] - alvo["maximum_equity_weight"]) < 5e-4,
                  f"{perfil}: orçamento de ações do app {dados['adaptar']['equity_budget']:.2%} "
                  f"== registro {alvo['maximum_equity_weight']:.2%}"))
        r.append((len(acoes) == alvo["top_assets"],
                  f"{perfil}: {len(acoes)} emissores no livro == {alvo['top_assets']} no registro"))
        r.append((dados["decision"] == livro["decision_date"],
                  f"{perfil}: decisão {dados['decision']} == livro do site "
                  f"{livro['decision_date']}"))

        # A pior queda que a pergunta central usa é a que o site publica.
        texto = f"−{abs(WORST_DRAWDOWN[perfil]) * 100:.2f}%".replace(".", ",")
        r.append((texto in index,
                  f"{perfil}: pior queda {texto} do questionário está publicada na home"))

    r.append((f"R$ {FGC_PER_CONGLOMERATE_BRL / 1000:.0f}.000".replace(".000", ".000") in tela
              or "250.000" in tela,
              f"teto do FGC de R$ {FGC_PER_CONGLOMERATE_BRL:,.0f} aparece na tela do app"
              .replace(",", ".")))
    r.append((set(app["profiles"]) == set(PROFILES),
              "os três perfis do app são os mesmos do questionário"))

    # --- e o app não fala uma língua que só o site ensina ---
    corpo = tela[tela.index("<div class=\"wrap\">"):]
    # O jargão que escapou da última vez estava dentro do script, não na
    # marcação: o alerta é montado em JavaScript e só existe depois que a pessoa
    # escolhe um plano. Ler só o HTML estático deixava passar exatamente o texto
    # que o cliente lê. Agora as cadeias literais do script entram na varredura.
    script = "\n".join(re.findall(r"<script>(.*?)</script>", corpo, flags=re.S))
    # Comentário de código não é texto de cliente: mantê-lo na varredura
    # transformaria a explicação de uma decisão em falso positivo.
    script = re.sub(r"^\s*//.*$", "", script, flags=re.M)
    # E só o que parece frase. Nome de variável e chave de JSON também são
    # literais, e incluí-los faz o verificador acusar "cesta" dentro de um
    # ``forEach(([cesta, d])`` e "escopo" numa chave do consentimento. Alarme
    # falso é pior que nenhum alarme: ensina a ignorar o alarme verdadeiro.
    frase = re.compile(r"^(?=.*\s)(?![^\"]*[{}()=<>])[^\"\\]{20,}$")
    literais = " ".join(x for x in re.findall(r'"([^"\\]{4,})"', script)
                        if frase.match(x))
    visivel = re.sub(r"<script>.*?</script>", "", corpo, flags=re.S)
    visivel = (re.sub(r"<[^>]+>", " ", visivel) + " " + literais).lower()
    for palavra in JARGAO_PROIBIDO:
        r.append((not re.search(rf"\b{palavra}\b", visivel),
                  f"a tela do app não usa '{palavra}' sem explicar"))

    # --- e nunca empresta o histórico ao caminho que não o tem ---
    for perfil in PROFILES:
        r.append((app["profiles"][perfil]["adaptar"]["track_record_applies"] is False,
                  f"{perfil}: manter a carteira não reivindica o histórico publicado"))
        r.append((app["profiles"][perfil]["adequar"]["track_record_applies"] is True,
                  f"{perfil}: adequar ao perfil reivindica o histórico, e pode"))
    return r


def main() -> int:
    resultados = checar()
    for ok, texto in resultados:
        print(("ok      " if ok else "FALHA   ") + texto)
    ruins = [t for ok, t in resultados if not ok]
    print()
    if ruins:
        print(f"{len(ruins)} DIVERGÊNCIA(S) ENTRE O APP E O SITE.")
        return 1
    print(f"APP E SITE DE ACORDO EM {len(resultados)} PONTOS.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
