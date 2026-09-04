"""Ensaio: refaz a decisão de janeiro de 2026 e confere se ela reproduz o publicado.

Por que isto existe
-------------------
A amostra confirmatória da política declarada começa no primeiro pregão de 2027.
Até lá, tudo o que o projeto publica sobre 2026 é reconstrução, e a reconstrução
é defensável porque a política é declarada. A partir de 2027 não é mais: a
decisão precisa ser tomada NA data, com os dados disponíveis NA data. Se ela for
produzida depois, com dados de depois, a amostra nasce contaminada e a
afirmação central do trabalho morre junto.

O caminho seguro para chegar lá é ensaiar contra um ano cuja resposta já se
conhece. Este programa refaz a decisão de 02/01/2026 a partir dos insumos e
compara com o livro publicado, papel por papel e peso por peso. Se reproduzir, o
maquinário serve; onde não reproduzir, aparece exatamente o que falta.

O que ele já encontrou, e que não é hipótese
--------------------------------------------
1. O argumento padrão --mapping do gerador apontava para um arquivo sem coluna
   isin, e current_mapping funde por ticker E isin: quem rodasse o comando como
   documentado recebia KeyError, não a carteira. Corrigido no gerador.
2. Os três perfis publicados reproduzem exatamente.
3. O ultraconservador NÃO reproduz, e a diferença é de método, não de erro
   aritmético. Está descrita em `divergencia_do_ultraconservador` abaixo.

    python tools/ensaio_decisao_anual.py
    python tools/ensaio_decisao_anual.py --json   # para consumo por teste
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLICADO = ROOT / "artifacts" / "profile_books_2026" / "profile_books_2026.json"
GERADOR = ROOT / "build_profile_books_2026.py"

#: Cada insumo da decisão, e de onde ele viria para outro ano. Esta é a lista de
#: compras de 2027, e ela está aqui, junto do que a usa, em vez de num documento
#: que envelhece separado do código.
INSUMOS = {
    "prices": ("data/prices_b3_cotahist_2011_2026.csv",
               "painel de preços do COTAHIST; reconstruível por build_b3_total_return_panel.py"),
    "universe": ("artifacts/b3_universe_january_2026.csv",
                 "retrato do universo B3 NA data da decisão; build_b3_universe_snapshot.py"),
    "mapping": ("data/b3_historical_cvm_ticker_map_2012_2025.csv",
                "ponte B3/CVM auditada, com isin; build_b3_cvm_mapping.py"),
    "fundamentals": ("data/fundamentals_b3_cvm_full_2013_2025_v2.csv",
                     "ITR e DFP com data de recebimento; cvm_fundamentals.py e refresh_recent_itr.py"),
}

#: Tudo que amarra o fluxo a 2026. Vira a lista de mudanças para 2027.
#:
#: Cada entrada traz a própria marca, e não uma busca solta pelo arquivo: com
#: uma expressão só para todos, duas amarras diferentes no mesmo arquivo se
#: reportavam presentes porque uma casava com a marca da outra.
PRESOS_A_2026 = (
    ("build_profile_books_2026.py", "DECISION_YEAR escrito como constante",
     r"^DECISION_YEAR\s*=\s*2026"),
    ("build_profile_books_2026.py", "nomes de saída com o ano dentro",
     r'"fundamentals_2026\.csv"|"profile_books_2026\.json"'),
    ("build_current_2026_decision.py", "current_mapping fixa universe_year 2025 e 2026",
     r"universe_year\.eq\(2025\)|carried\[.universe_year.\]\s*=\s*2026"),
    ("build_current_2026_decision.py", "_january_price_row lê COTAHIST_A2026.ZIP",
     r"COTAHIST_A2026\.ZIP"),
)


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest() if caminho.exists() else ""


def executa(destino: Path) -> dict:
    """Roda o gerador com os insumos declarados e devolve o livro que ele produz."""
    comando = [sys.executable, str(GERADOR),
               "--prices", INSUMOS["prices"][0],
               "--universe", INSUMOS["universe"][0],
               "--mapping", INSUMOS["mapping"][0],
               "--output", str(destino)]
    resultado = subprocess.run(comando, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    if resultado.returncode != 0:
        raise SystemExit(f"o gerador não rodou:\n{resultado.stdout}\n{resultado.stderr}")
    return json.loads((destino / "profile_books_2026.json").read_text(encoding="utf-8"))


def compara(publicado: dict, ensaiado: dict) -> list[dict]:
    """Papel por papel e peso por peso, só para os perfis que o publicado tem."""
    linhas = []
    for perfil, livro in publicado["books"].items():
        refeito = ensaiado["books"].get(perfil)
        if refeito is None:
            linhas.append({"perfil": perfil, "reproduz": False, "porque": "ausente no ensaio"})
            continue
        tickers_pub = [p["ticker"] for p in livro["positions"]]
        tickers_ens = [p["ticker"] for p in refeito["positions"]]
        pesos_pub = [round(p["weight"], 10) for p in livro["positions"]]
        pesos_ens = [round(p["weight"], 10) for p in refeito["positions"]]
        iguais = tickers_pub == tickers_ens and pesos_pub == pesos_ens
        linhas.append({
            "perfil": perfil,
            "reproduz": iguais,
            "tickers_iguais": tickers_pub == tickers_ens,
            "pesos_iguais": pesos_pub == pesos_ens,
            "acoes_publicado": round(livro["domestic_equity"], 6),
            "acoes_ensaio": round(refeito["domestic_equity"], 6),
        })
    return linhas


def divergencia_do_ultraconservador(ensaiado: dict) -> dict:
    """O único perfil com duas respostas, e a diferença é de método.

    O que o site publica vem de build_ultraconservador_book.py, que pega o livro
    do conservador e escala os pesos pelo fator 0,114286, ou seja 4% sobre 35%.
    O gerador calcula o degrau direto, com o teto por ativo próprio do
    ultraconservador, e os pesos saem diferentes: o total em ações é o mesmo,
    3,2%, mas a distribuição entre os papéis não.

    Qual dos dois é o certo não é questão aritmética, é de interpretação da
    política, e por isso este programa relata em vez de escolher. A declaração
    do quarto degrau diz que a regra "moveu o teto de ações, e só ele", e que o
    degrau herda a camada do conservador em vez de ganhar multiplicadores
    próprios escolhidos depois de ver resultado. Escalar os pesos do conservador
    é fiel a essa frase. Recalcular sob um teto por ativo próprio é um segundo
    método, e precisa ser declarado se for o escolhido.
    """
    caminho = ROOT / "web" / "current_decision_2026_ultraconservador.json"
    publicado = json.loads(caminho.read_text(encoding="utf-8"))
    refeito = ensaiado["books"].get("ultraconservador")
    if refeito is None:
        return {"situacao": "o gerador não produz o degrau"}
    pesos_pub = {h["ticker"]: round(h["weight"], 8) for h in publicado["holdings"]}
    pesos_ens = {p["ticker"]: round(p["weight"], 8) for p in refeito["positions"]}
    comuns = sorted(set(pesos_pub) & set(pesos_ens))
    # O total em ações sai dos dois lados por caminhos diferentes e difere na
    # sexta casa; comparar com o publicado, e não com uma constante, evita
    # rotular como divergência o que é arredondamento.
    total_publicado = sum(peso for ticker, peso in pesos_pub.items() if ticker != "IVVB11")
    total_ensaio = refeito["domestic_equity"]
    return {
        "situacao": "dois métodos, duas respostas",
        "publicado_por": "build_ultraconservador_book.py (escala o conservador por 0,114286)",
        "ensaiado_por": "build_profile_books_2026.py (calcula o degrau sob o teto por ativo próprio)",
        "total_em_acoes": {"publicado": round(total_publicado, 6), "ensaio": round(total_ensaio, 6),
                           "igual": abs(total_publicado - total_ensaio) < 1e-4},
        "pesos_diferentes_em": [t for t in comuns if pesos_pub[t] != pesos_ens[t]],
        "exemplo": {t: {"publicado": pesos_pub[t], "ensaio": pesos_ens[t]} for t in comuns[:3]},
        "quem_decide": "interpretação da política, não aritmética; ver a declaração do quarto degrau",
    }


def pinos_de_2026() -> list[dict]:
    """Confere que cada amarra a 2026 ainda está lá, para a lista não envelhecer."""
    encontrados = []
    for arquivo, descricao, padrao in PRESOS_A_2026:
        texto = (ROOT / arquivo).read_text(encoding="utf-8") if (ROOT / arquivo).exists() else ""
        marca = re.search(padrao, texto, re.M)
        encontrados.append({"arquivo": arquivo, "amarra": descricao, "presente": bool(marca)})
    return encontrados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="Saída legível por máquina.")
    argumentos = parser.parse_args()

    publicado = json.loads(PUBLICADO.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as pasta:
        ensaiado = executa(Path(pasta))

    relatorio = {
        "decision_date": publicado["decision_date"],
        "insumos": [{"papel": papel, "arquivo": caminho, "existe": (ROOT / caminho).exists(),
                     "sha256": _sha(ROOT / caminho), "de_onde_vem": origem}
                    for papel, (caminho, origem) in INSUMOS.items()],
        "reproducao": compara(publicado, ensaiado),
        "divergencia_do_ultraconservador": divergencia_do_ultraconservador(ensaiado),
        "presos_a_2026": pinos_de_2026(),
    }
    if argumentos.json:
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
        return 0

    print(f"Ensaio da decisão de {relatorio['decision_date']}\n")
    for linha in relatorio["reproducao"]:
        marca = "reproduz" if linha["reproduz"] else "NÃO REPRODUZ"
        print(f"  {linha['perfil']:<14} {marca}")
    print()
    divergencia = relatorio["divergencia_do_ultraconservador"]
    print(f"  ultraconservador: {divergencia['situacao']}")
    if divergencia.get("pesos_diferentes_em"):
        total = divergencia["total_em_acoes"]
        print(f"    total em ações: {total['publicado']:.4%} publicado, {total['ensaio']:.4%} no ensaio "
              f"({'igual' if total['igual'] else 'DIFERENTE'})")
        print(f"    distribuição entre papéis: diferente em {len(divergencia['pesos_diferentes_em'])} dos 12")
    presentes = [p for p in relatorio["presos_a_2026"] if p["presente"]]
    resolvidas = [p for p in relatorio["presos_a_2026"] if not p["presente"]]
    print(f"\n  amarras a 2026: {len(resolvidas)} resolvida(s), {len(presentes)} de pé")
    for pino in presentes:
        print(f"    falta  {pino['arquivo']}: {pino['amarra']}")
    for pino in resolvidas:
        print(f"    ok     {pino['arquivo']}: {pino['amarra']}")
    faltando = [i for i in relatorio["insumos"] if not i["existe"]]
    if faltando:
        print("\n  INSUMO AUSENTE:")
        for item in faltando:
            print(f"    {item['arquivo']} — {item['de_onde_vem']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
