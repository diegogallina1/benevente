"""Congela os insumos da decisão anual na data, com hash, e confere depois.

Por que copiar e não só anotar o hash
--------------------------------------
A decisão de um ano precisa continuar reproduzível anos depois. Anotar o hash de
um arquivo que muda não reproduz nada: quando alguém for conferir, o arquivo já
é outro e o hash só prova que era diferente. Os quatro insumos ficam guardados
inteiros, num diretório com o ano no nome, e o manifesto diz o que cada um é, de
onde veio e quanto pesa.

Dois deles mudam sozinhos com o tempo, e é por isso que a cópia importa. O painel
de fundamentos ganha ITR e DFP novos e pode revisar registros antigos; o painel
de preços é reconstruído a cada carga do COTAHIST. A triagem já descarta
formulário recebido depois da data da decisão, então a disciplina point-in-time
está na lógica; a captura garante que os bytes que a lógica leu continuem os
mesmos.

O que a captura recusa
----------------------
Ela não grava captura incompleta. Se faltar um insumo, ou se o retrato do
universo for de outra data que não a da decisão, ela para. Publicar uma carteira
a partir de insumo faltando é o modo de falha que o projeto inteiro existe para
não ter.

    python tools/capturar_insumos.py --decisao 2027-01-04
    python tools/capturar_insumos.py --conferir artifacts/insumos_2027
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]

#: Os quatro insumos da decisão anual, o que cada um é e quem o produz. É a
#: lista de compras de qualquer ano, e vive aqui, junto de quem a usa.
INSUMOS = {
    "prices": {
        "arquivo": "data/prices_b3_cotahist_2011_2026.csv",
        "papel": "painel de preços diários, do COTAHIST",
        "produzido_por": "build_b3_total_return_panel.py, a partir do COTAHIST em cache",
        "muda_sozinho": True,
    },
    "universe": {
        "arquivo": "artifacts/b3_universe_january_2026.csv",
        "papel": "retrato do universo B3 na data da decisão, com liquidez",
        "produzido_por": "build_b3_universe_snapshot.py",
        "muda_sozinho": False,
    },
    "mapping": {
        "arquivo": "data/b3_historical_cvm_ticker_map_2012_2025.csv",
        "papel": "ponte B3/CVM auditada, com isin, que liga papel a emissor",
        "produzido_por": "build_b3_cvm_mapping.py",
        "muda_sozinho": False,
    },
    "fundamentals": {
        "arquivo": "data/fundamentals_b3_cvm_full_2013_2025_v2.csv",
        "papel": "ITR e DFP com data de recebimento pelo regulador",
        "produzido_por": "cvm_fundamentals.py e refresh_recent_itr.py",
        "muda_sozinho": True,
    },
}

MANIFESTO = "manifesto.json"


def _sha(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _data_do_universo(caminho: Path) -> str:
    """A data que o retrato diz ser a da decisão, lida sem carregar o arquivo todo."""
    with caminho.open(encoding="utf-8", errors="ignore", newline="") as fh:
        cabecalho = next(fh).rstrip("\n").split(",")
        primeira = next(fh).rstrip("\n").split(",")
    return primeira[cabecalho.index("decision_date")]


def capturar(decisao: str, destino: Path | None = None) -> dict:
    ano = int(decisao[:4])
    destino = destino or ROOT / "artifacts" / f"insumos_{ano}"

    faltando = [item["arquivo"] for item in INSUMOS.values() if not (ROOT / item["arquivo"]).exists()]
    if faltando:
        raise SystemExit("captura recusada, insumo ausente:\n  " + "\n  ".join(faltando))

    universo = ROOT / INSUMOS["universe"]["arquivo"]
    data_do_retrato = _data_do_universo(universo)
    if data_do_retrato != decisao:
        # O retrato é o que amarra a decisão à data. Capturar um de outro dia
        # produziria uma carteira que parece certa e não é.
        raise SystemExit(
            f"captura recusada: o retrato do universo é de {data_do_retrato}, "
            f"e a decisão pedida é de {decisao}. Gere o retrato da data com "
            "build_b3_universe_snapshot.py antes de capturar.")

    destino.mkdir(parents=True, exist_ok=True)
    arquivos = []
    for papel, item in INSUMOS.items():
        origem = ROOT / item["arquivo"]
        copia = destino / Path(item["arquivo"]).name
        shutil.copy2(origem, copia)
        arquivos.append({
            "papel": papel,
            "arquivo": copia.name,
            "origem": item["arquivo"],
            "sha256": _sha(copia),
            "bytes": copia.stat().st_size,
            "descricao": item["papel"],
            "produzido_por": item["produzido_por"],
            "muda_sozinho": item["muda_sozinho"],
        })

    manifesto = {
        "decision_date": decisao,
        "captured_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "why": (
            "Os quatro insumos da decisão de janeiro, guardados inteiros e com hash, para que a "
            "carteira do ano continue reproduzível a partir dos mesmos bytes. Dois deles mudam "
            "sozinhos com o tempo, e é por isso que a cópia existe: anotar o hash de um arquivo "
            "que muda não reproduz nada."),
        "point_in_time": (
            "A triagem descarta formulário recebido depois da data da decisão, então a disciplina "
            "está na lógica. A captura garante que os bytes que a lógica leu continuem os mesmos."),
        "files": arquivos,
    }
    corpo = json.dumps(manifesto, ensure_ascii=False, indent=2, sort_keys=True)
    manifesto["manifest_sha256"] = hashlib.sha256(corpo.encode("utf-8")).hexdigest()
    (destino / MANIFESTO).write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8", newline="\n")
    return manifesto


def conferir(pasta: Path) -> list[str]:
    """Rehasheia o que foi capturado. Silêncio é o resultado bom."""
    manifesto = json.loads((pasta / MANIFESTO).read_text(encoding="utf-8"))
    problemas = []
    guardado = dict(manifesto)
    esperado = guardado.pop("manifest_sha256", "")
    corpo = json.dumps(guardado, ensure_ascii=False, indent=2, sort_keys=True)
    if hashlib.sha256(corpo.encode("utf-8")).hexdigest() != esperado:
        problemas.append("o próprio manifesto foi alterado depois de escrito")
    for item in manifesto["files"]:
        caminho = pasta / item["arquivo"]
        if not caminho.exists():
            problemas.append(f"{item['arquivo']}: sumiu da captura")
            continue
        atual = _sha(caminho)
        if atual != item["sha256"]:
            problemas.append(
                f"{item['arquivo']}: capturado {item['sha256'][:12]}, hoje {atual[:12]}")
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--decisao", help="Data da decisão, AAAA-MM-DD.")
    parser.add_argument("--destino", type=Path, default=None)
    parser.add_argument("--conferir", type=Path, default=None,
                        help="Confere uma captura existente em vez de criar outra.")
    argumentos = parser.parse_args()

    if argumentos.conferir:
        problemas = conferir(argumentos.conferir)
        for linha in problemas:
            print(f"DIVERGE  {linha}")
        if problemas:
            print(f"\n{len(problemas)} divergência(s): a captura não vale mais como prova.")
            return 1
        print("A CAPTURA CONFERE: os bytes são os mesmos do dia.")
        return 0

    if not argumentos.decisao:
        parser.error("informe --decisao AAAA-MM-DD ou --conferir <pasta>")
    manifesto = capturar(argumentos.decisao, argumentos.destino)
    total = sum(item["bytes"] for item in manifesto["files"])
    print(f"captura de {manifesto['decision_date']}: {len(manifesto['files'])} arquivos, "
          f"{total / 1048576:.1f} MB")
    for item in manifesto["files"]:
        print(f"  {item['papel']:<13} {item['sha256'][:12]}  {item['arquivo']}")
    print(f"  manifesto {manifesto['manifest_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
