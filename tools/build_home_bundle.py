"""O pacote que a página inicial de fato consome, e só ele.

A home baixava ``annual_research.json`` inteiro — 138 KB — para usar três
chaves. As outras duas, ``holdings`` e ``transitions``, somam 94 KB e alimentam
o razão de decisões que vive em Módulos e perfis, não na home: o renderizador
que as leria devolve cedo porque a seção correspondente não existe mais ali.
Baixar dado que nenhum pixel consome é custo puro, e num celular em rede lenta
é custo que aparece.

Este programa deriva o pacote enxuto do arquivo completo, para que os dois não
possam divergir: se o arquivo de origem mudar e este não for regerado, o teste
de contrato falha em vez de a página servir um número velho.
"""
from __future__ import annotations

from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web" / "annual_research.json"
OUT = ROOT / "web" / "annual_research_home.json"

#: O que a home lê. Derivado por inspeção do app.js, não por suposição: cada
#: chave abaixo aparece no código que a página executa.
SECTIONS = ("meta", "annual", "monthly_curve")
#: Dentro de ``meta``, os campos que nenhuma linha da home lê. O maior deles,
#: ``evidence``, é o dossiê da política arquivada e pesa quase 4 KB sozinho.
META_DROP = ("sample", "sources", "institutional_performance_verified",
             "holdout_validation", "evidence", "protocol")


def build() -> dict:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    bundle = {key: source[key] for key in SECTIONS if key in source}
    bundle["meta"] = {k: v for k, v in bundle["meta"].items() if k not in META_DROP}
    bundle["meta"]["derived_from"] = SOURCE.name
    bundle["meta"]["bundle_note"] = (
        "Recorte da página inicial. O arquivo completo, com o razão de decisões e as "
        "transições de exposição, continua em annual_research.json e alimenta Módulos e perfis.")
    OUT.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return bundle


def main() -> None:
    build()
    antes, depois = SOURCE.stat().st_size / 1024, OUT.stat().st_size / 1024
    # Sem sinais tipográficos aqui: o console do Windows abre em cp1252 e um
    # menos U+2212 derruba a ferramenta na linha do print, depois de ela já ter
    # feito o trabalho todo. Falhar ao contar o resultado é falhar à toa.
    print(f"{OUT.name}: {depois:.1f} KB (de {antes:.1f} KB), "
          f"economia de {antes - depois:.1f} KB por carregamento da home")


if __name__ == "__main__":
    main()
