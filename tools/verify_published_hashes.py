"""Confere todo SHA-256 publicado contra os bytes que o repositório entrega.

Um hash publicado como prova de procedência só vale se um terceiro, clonando o
repositório, calcular o mesmo valor. Em 03/09/2026 vinte e três não valiam: as
cópias de trabalho no Windows recebiam CRLF por causa de core.autocrlf, os
geradores hasheavam esses bytes, e o valor publicado não batia com o arquivo que
qualquer outra pessoa tinha. Nenhum blob jamais teve CRLF; o defeito estava na
ponta que calculava. O .gitattributes passou a fixar LF, e este verificador
existe para que a divergência apareça no dia em que voltar.

Ele compara sempre contra `git show HEAD:<arquivo>`, que é exatamente o que um
clone recebe, e não contra a cópia local, que pode estar diferente.

    python tools/verify_published_hashes.py           # falha se houver divergência
    python tools/verify_published_hashes.py --listar  # mostra tudo que conferiu
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
HEXA = re.compile(r"^[0-9a-f]{64}$")

#: Registros vivos: descrevem o estado atual e são regerados quando ele muda.
#: Divergência aqui é defeito e reprova.
VIVOS = (
    "web/research_manifest.json",
    "web/protocol_versions.json",
    "web/strategy_decisions.json",
    "web/data_contract.json",
)

#: Registros congelados: descrevem um momento e não podem ser reescritos. Uma
#: divergência aqui é fato histórico, não defeito, e está descrita em
#: data/correcao_hashes_2026_09_04.json. Este verificador confere que a
#: descrição continua batendo com a realidade, e é isso que impede a correção
#: de envelhecer em silêncio.
CONGELADOS = "data/correcao_hashes_2026_09_04.json"


def blob(caminho: str) -> bytes | None:
    """Os bytes que um clone recebe, não os do disco desta máquina."""
    resultado = subprocess.run(["git", "show", f"HEAD:{caminho}"], cwd=ROOT, capture_output=True)
    return resultado.stdout if resultado.returncode == 0 else None


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def declaracoes(no: object, origem: str) -> Iterator[tuple[str, str, str]]:
    """Devolve (origem, arquivo, hash) para todo par arquivo/sha256 do documento.

    Duas formas aparecem nos registros: um objeto com `source`/`file` ao lado de
    `sha256`, e um dicionário `sources_sha256` que mapeia caminho para hash
    direto, como no ledger de decisões. As duas contam.
    """
    if isinstance(no, dict):
        alvo = no.get("source") or no.get("file") or no.get("path")
        valor = no.get("sha256")
        if isinstance(alvo, str) and isinstance(valor, str) and HEXA.match(valor):
            # Entrada que declara, ela própria, que o conteúdo saiu deste
            # caminho: não é divergência, é história, e é conferida à parte.
            if "superseded_content_retrievable_at" not in no:
                yield origem, alvo, valor
        for chave, filho in no.items():
            if chave.endswith("sources_sha256") and isinstance(filho, dict):
                for caminho, digest in filho.items():
                    if isinstance(digest, str) and HEXA.match(digest):
                        yield origem, caminho, digest
                continue
            yield from declaracoes(filho, origem)
    elif isinstance(no, list):
        for filho in no:
            yield from declaracoes(filho, origem)


def confere_superados() -> list[str]:
    """Entradas cujo conteúdo foi substituído: o hash tem de existir no histórico.

    O protocolo de acompanhamento 1.0.0 foi substituído pelo 1.1.0 no mesmo
    caminho. O hash da linha antiga descreve um documento que não está mais lá,
    e recalculá-lo apagaria a procedência. Em vez disso a linha diz onde o
    conteúdo ainda vive, e aqui se confere que vive mesmo.
    """
    problemas = []
    for registro in VIVOS:
        documento = json.loads((ROOT / registro).read_text(encoding="utf-8"))
        for entrada in documento.get("versions", []):
            endereco = entrada.get("superseded_content_retrievable_at")
            if not endereco:
                continue
            ref = endereco.split()[-1] if endereco.startswith("git show") else endereco
            resultado = subprocess.run(["git", "show", ref], cwd=ROOT, capture_output=True)
            if resultado.returncode != 0:
                problemas.append(f"{registro}: {entrada['name']} aponta para {ref}, que não existe")
            elif _sha(resultado.stdout) != entrada["sha256"]:
                problemas.append(
                    f"{registro}: {entrada['name']} diz que o conteúdo de {entrada['sha256'][:12]} "
                    f"está em {ref}, mas lá o hash é {_sha(resultado.stdout)[:12]}")
    return problemas


def confere_vivos() -> list[str]:
    problemas = []
    for registro in VIVOS:
        documento = json.loads((ROOT / registro).read_text(encoding="utf-8"))
        for _, arquivo, publicado in declaracoes(documento, registro):
            conteudo = blob(arquivo.replace("\\", "/").lstrip("./"))
            if conteudo is None:
                continue  # arquivo fora do controle de versão; nada a comparar
            atual = _sha(conteudo)
            if atual != publicado:
                com_crlf = _sha(conteudo.replace(b"\n", b"\r\n"))
                causa = "hash calculado sobre bytes com CRLF" if publicado == com_crlf else "conteúdo diferente"
                problemas.append(f"{registro}: {arquivo} publica {publicado[:12]}, entrega {atual[:12]} ({causa})")
    return problemas


def confere_congelados() -> list[str]:
    """A correção descreve cada divergência histórica; aqui se checa a descrição."""
    correcao = json.loads((ROOT / CONGELADOS).read_text(encoding="utf-8"))
    problemas = []
    for item in correcao["divergences"]:
        conteudo = blob(item["file"])
        if conteudo is None:
            problemas.append(f"{CONGELADOS}: {item['file']} não está mais versionado")
            continue
        atual = _sha(conteudo)
        if atual != item["true_sha256"]:
            problemas.append(
                f"{CONGELADOS}: {item['file']} mudou desde a correção "
                f"(descrito {item['true_sha256'][:12]}, hoje {atual[:12]})")
            continue
        com_crlf = _sha(conteudo.replace(b"\n", b"\r\n"))
        causa = "crlf" if item["registered_sha256"] == com_crlf else "conteudo_mudou"
        if causa != item["cause"]:
            problemas.append(
                f"{CONGELADOS}: {item['file']} está descrito como '{item['cause']}' e hoje é '{causa}'")
    return problemas


def confere_politica_vigente() -> list[str]:
    """Todo arquivo que a política vigente declara: ou o hash bate, ou a divergência está assumida.

    Este é o buraco por onde a deriva passou. Os testes existentes conferiam
    que cada hash declarado tem 64 caracteres e que certa chave existe, nunca
    que o valor corresponde ao arquivo. Dois arquivos foram editados depois de
    registrados e ninguém notou por semanas.

    Aqui, um arquivo declarado só pode divergir se a divergência estiver escrita
    em data/correcao_hashes_2026_09_04.json com o valor de hoje. Editar de novo
    um arquivo declarado passa a reprovar, e a saída é assumir a nova
    divergência ou registrar uma política nova. Ficar calado deixa de ser uma
    das opções.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("politica", ROOT / "tools" / "politica.py")
    politica = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(politica)
    registro = json.loads(politica.REGISTRO.read_text(encoding="utf-8"))

    correcao = json.loads((ROOT / CONGELADOS).read_text(encoding="utf-8"))
    assumidas = {
        item["file"]: item["true_sha256"]
        for item in correcao["divergences"]
        if item["registration"] == f"data/{politica.REGISTRO.name}" and item["file"]
    }

    problemas = []
    for arquivo, declarado in registro.get("code", {}).items():
        conteudo = blob(arquivo)
        if conteudo is None:
            problemas.append(f"{politica.REGISTRO.name}: declara {arquivo}, que não está versionado")
            continue
        atual = _sha(conteudo)
        if atual == declarado:
            continue
        if arquivo not in assumidas:
            problemas.append(
                f"{politica.REGISTRO.name}: {arquivo} não confere com o hash declarado e a "
                f"divergência não está assumida em {CONGELADOS}")
        elif assumidas[arquivo] != atual:
            problemas.append(
                f"{politica.REGISTRO.name}: {arquivo} mudou de novo depois da correção "
                f"(assumido {assumidas[arquivo][:12]}, hoje {atual[:12]}). Assuma a nova "
                "divergência ou registre uma política nova.")
    return problemas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listar", action="store_true", help="Mostra o que foi conferido, não só o que falhou.")
    args = parser.parse_args()

    problemas = (confere_vivos() + confere_superados() + confere_congelados()
                 + confere_politica_vigente())
    if args.listar:
        for registro in VIVOS:
            documento = json.loads((ROOT / registro).read_text(encoding="utf-8"))
            quantos = sum(1 for _ in declaracoes(documento, registro))
            print(f"{registro}: {quantos} hash(es) declarados")
        correcao = json.loads((ROOT / CONGELADOS).read_text(encoding="utf-8"))
        print(f"{CONGELADOS}: {len(correcao['divergences'])} divergência(s) históricas descritas")

    if problemas:
        for linha in problemas:
            print(f"DIVERGE  {linha}")
        print(f"\n{len(problemas)} divergência(s). Um hash publicado precisa bater com o que o clone entrega.")
        return 1
    print("TODO HASH PUBLICADO CONFERE COM OS BYTES QUE O REPOSITÓRIO ENTREGA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
