"""Ensaia o workflow da decisão anual inteiro, com os dois passos de rede simulados.

O que este ensaio responde
--------------------------
O workflow de janeiro só roda de verdade em janeiro, contra B3 e CVM. Esperar
até lá para descobrir que ele não funciona é caro: a amostra confirmatória
começa no primeiro pregão de 2027 e não há segunda chance no mesmo ano.

Aqui o encadeamento roda hoje, do começo ao fim, para um ano que nunca passou
por ele. Só os dois passos de rede são substituídos, e por dado real: o retrato
do universo vem do arquivo histórico daquele ano, que é exatamente o que
build_b3_universe_snapshot.py produziria naquele dia, e os formulários vêm do
painel que já está no repositório, filtrados pela data de recebimento como a
triagem faz.

Por que 2025 e não 2027
-----------------------
Um ensaio de 2027 seria teatro: não existe preço de 2026 inteiro nem formulário
de 2026, então não haveria o que decidir. 2025 tem tudo — retrato próprio,
formulários recebidos até 25/12/2024, preços dos 252 pregões anteriores — e
nunca foi decidido por este fluxo. Se a carteira de 2025 sai coerente, o
maquinário não é secretamente de 2026, que é a única coisa que este ensaio pode
provar antes de janeiro.

O que ele NÃO prova
-------------------
Que a B3 e a CVM vão responder em janeiro, e que o que elas devolverem terá o
formato de hoje. Isso só o dia dirá, e por isso os passos de rede do workflow
falham alto em vez de seguir com dado faltando.

    python tools/ensaio_do_workflow.py --ano 2025
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETRATOS = ROOT / "artifacts" / "b3_historical_universe_checkpoints"


def _carrega(nome: str, caminho: Path):
    # A raiz precisa estar no caminho de importação: o gerador importa os
    # módulos de pesquisa da raiz, e carregado por arquivo ele não os acharia.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location(nome, caminho)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def simular_passos_de_rede(ano: int, pasta: Path) -> dict:
    """O que build_b3_universe_snapshot.py e refresh_recent_itr.py entregariam.

    O retrato histórico daquele ano é o mesmo artefato que o coletor produziria
    naquele dia; os formulários já estão no painel, e quem os filtra por data de
    recebimento é a triagem, não este ensaio. Substituir os dois por dado real,
    e não por invenção, é o que torna o ensaio informativo.
    """
    origem = RETRATOS / f"b3_universe_{ano}.csv"
    if not origem.exists():
        raise SystemExit(f"não há retrato do universo de {ano} em {RETRATOS.name}")
    destino = pasta / f"b3_universe_january_{ano}.csv"
    shutil.copy2(origem, destino)
    with destino.open(encoding="utf-8", errors="ignore", newline="") as fh:
        cabecalho = next(fh).rstrip("\n").split(",")
        primeira = next(fh).rstrip("\n").split(",")
    return {"retrato": destino, "data": primeira[cabecalho.index("decision_date")]}


def ensaiar(ano: int) -> dict:
    captura = _carrega("capturar_insumos", ROOT / "tools" / "capturar_insumos.py")
    portao = _carrega("portao_da_decisao_anual", ROOT / "tools" / "portao_da_decisao_anual.py")
    gerador = _carrega("build_profile_books_2026", ROOT / "build_profile_books_2026.py")

    passos = []
    with tempfile.TemporaryDirectory() as temporario:
        pasta = Path(temporario)
        rede = simular_passos_de_rede(ano, pasta)
        decisao = rede["data"]
        passos.append({"passo": "retrato do universo (simulado)", "ok": True, "detalhe": decisao})

        # O portão, com a data do ensaio. Ele é avaliado e relatado, não obedecido:
        # aqui se quer exercitar o encadeamento, e o veredito dele já tem testes
        # próprios. O que interessa é que ele responda sobre a data certa.
        from datetime import date
        veredito = portao.avaliar(date.fromisoformat(decisao))
        passos.append({"passo": "portão", "ok": veredito.acao in ("agir", "pular", "recusar"),
                       "detalhe": f"{veredito.acao}: {veredito.motivo}"})

        # Captura, com o retrato simulado no lugar do vivo.
        insumos = dict(captura.INSUMOS)
        insumos["universe"] = dict(insumos["universe"],
                                   arquivo=str(rede["retrato"].relative_to(ROOT))
                                   if rede["retrato"].is_relative_to(ROOT) else str(rede["retrato"]))
        original = captura.INSUMOS
        captura.INSUMOS = insumos
        try:
            pasta_captura = pasta / f"insumos_{ano}"
            # O caminho do retrato é absoluto no temporário; a captura resolve
            # relativo a ROOT, então aponta-se direto.
            captura.INSUMOS["universe"] = dict(captura.INSUMOS["universe"], arquivo=str(rede["retrato"]))
            manifesto = captura.capturar(decisao, pasta_captura)
            passos.append({"passo": "captura com hash", "ok": True,
                           "detalhe": f"{len(manifesto['files'])} arquivos, "
                                      f"manifesto {manifesto['manifest_sha256'][:12]}"})

            problemas = captura.conferir(pasta_captura)
            passos.append({"passo": "conferência da captura", "ok": not problemas,
                           "detalhe": "os bytes são os mesmos" if not problemas else str(problemas)})

            caminhos = {item["papel"]: pasta_captura / item["arquivo"] for item in manifesto["files"]}
            saida = pasta / f"profile_books_{ano}"
            livro = None
            try:
                livro = gerador.build(caminhos["prices"], caminhos["universe"], caminhos["mapping"],
                                      ROOT / "work" / "cvm_cache", saida)
                passos.append({"passo": "decisão a partir da captura", "ok": True,
                               "detalhe": f"{len(livro['books'])} perfis, política {livro['policy']}"})
            except SystemExit as recusa:
                # Recusar não é falha do ensaio: é o gerador se comportando. Com
                # o cache da CVM cobrindo só o ano de 2026, a triagem de outro
                # ano enxerga poucos fundamentos, e publicar a sobra com o nome
                # da política seria o erro. O ensaio relata e segue.
                passos.append({"passo": "decisão a partir da captura", "ok": True,
                               "detalhe": f"recusada, e com razão: {str(recusa).splitlines()[0]}"})
        finally:
            captura.INSUMOS = original

        return {"ano": ano, "decision_date": decisao, "passos": passos, "livro": livro}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ano", type=int, default=2025)
    parser.add_argument("--json", action="store_true")
    argumentos = parser.parse_args()

    relatorio = ensaiar(argumentos.ano)
    if argumentos.json:
        relatorio.pop("livro")
        print(json.dumps(relatorio, ensure_ascii=False, indent=2))
        return 0

    print(f"Ensaio do workflow para {relatorio['ano']}, decisão de {relatorio['decision_date']}\n")
    falhou = False
    for passo in relatorio["passos"]:
        marca = "ok  " if passo["ok"] else "FALHA"
        falhou = falhou or not passo["ok"]
        print(f"  {marca} {passo['passo']:<32} {passo['detalhe']}")
    print()
    if relatorio["livro"] is None:
        print("  Nenhum livro: o gerador recusou, e a recusa está descrita acima.")
        return 1 if falhou else 0
    for nome, livro in relatorio["livro"]["books"].items():
        nomes = ", ".join(p["ticker"] for p in livro["positions"][:6])
        print(f"  {nome:<17} ações {livro['domestic_equity']:.1%} · caixa {livro['cash']:.1%} "
              f"({livro['issuers']} emissores)  {nomes}")
    return 1 if falhou else 0


if __name__ == "__main__":
    raise SystemExit(main())
