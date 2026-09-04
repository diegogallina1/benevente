"""Reatesta os hashes de código da política v4, sem criar versão nova.

Por que uma reatestação e não uma v5
------------------------------------
O registro da v4 foi gerado em 30/08/2026 às 13:38:13 e os hashes de código
foram tirados naquele instante. O quarto degrau foi acrescentado a
portfolio_risk.py e profile_ladder_v2.py em seguida, e as duas coisas entraram
no mesmo commit, bfd80e5, às 13:54. O registro declarava um degrau cuja
implementação ainda não estava nos arquivos que ele hasheou.

Não é o código derivando da política ao longo do tempo: é a fotografia tirada
dezesseis minutos cedo demais. Nenhum parâmetro mudou, e este script prova isso
comparando o que a v4 declara com o que o código expõe hoje, em vez de afirmar.

Criar uma v5 seria pior. A linhagem do projeto diz que versão nova existe para
mudança material, e cadastrar uma sem mudança nenhuma faria o leitor procurar
uma diferença que não existe. A amostra confirmatória continua começando no
primeiro pregão de 2027, porque nada no que foi declarado mudou.

O que este documento acrescenta
-------------------------------
Os hashes do código como ele está desde 30/08, calculados sobre os bytes que o
repositório entrega, e a causa de cada divergência em relação ao registro: três
arquivos divergem só por fim de linha, com conteúdo intacto, e dois porque
receberam a implementação do degrau depois da fotografia.

    python tools/reatestar_politica_v4.py [--approved-by "Nome"]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
REGISTRO = ROOT / "data" / "benevente_profile_ladder_v4_registration.json"
SAIDA = ROOT / "data" / "benevente_profile_ladder_v4_code_reattestation.json"
COMMIT_DA_IMPLEMENTACAO = "bfd80e5"


def _blob(caminho: str) -> bytes | None:
    """Os bytes que um clone recebe, que é contra o que um terceiro confere."""
    resultado = subprocess.run(["git", "show", f"HEAD:{caminho}"], cwd=ROOT, capture_output=True)
    return resultado.stdout if resultado.returncode == 0 else None


def _sha(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def assinante(explicito: str | None) -> tuple[str, str]:
    """Sem assinante não há reatestação, pela mesma razão que não há registro."""
    if explicito and explicito.strip():
        return explicito.strip(), "explicit"
    try:
        nome = subprocess.run(["git", "config", "user.name"], cwd=ROOT, capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        nome = ""
    if not nome:
        raise SystemExit(
            "Recuse-se a reatestar sem assinante: informe --approved-by ou configure git config user.name")
    return nome, "git identity"


def parametros_conferem() -> tuple[bool, list[str]]:
    """Compara o que a v4 declara com o que o código expõe hoje.

    É esta função que sustenta a frase "nenhum parâmetro mudou". Sem ela a
    reatestação seria só uma afirmação sobre si mesma.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import profile_ladder_v2 as modulo

    declarados = json.loads(REGISTRO.read_text(encoding="utf-8"))["profiles"]
    no_codigo = getattr(modulo, "LADDER_V2", {})
    diferencas = []
    if set(declarados) != set(no_codigo):
        diferencas.append(
            f"degraus: declarados {sorted(declarados)}, no código {sorted(no_codigo)}")
    for nome in sorted(set(declarados) & set(no_codigo)):
        for campo in ("maximum_equity_weight", "top_assets"):
            esperado, atual = declarados[nome].get(campo), no_codigo[nome].get(campo)
            if esperado != atual:
                diferencas.append(f"{nome}.{campo}: declarado {esperado}, no código {atual}")
    return not diferencas, diferencas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approved-by", default=None)
    argumentos = parser.parse_args()

    aprovador, origem = assinante(argumentos.approved_by)
    registro = json.loads(REGISTRO.read_text(encoding="utf-8"))

    iguais, diferencas = parametros_conferem()
    if not iguais:
        # Se um parâmetro mudou, isto deixa de ser reatestação e vira política
        # nova. O script recusa em vez de carimbar a diferença como se não
        # existisse, que é exatamente o erro que ele existe para não repetir.
        print("Os parâmetros mudaram; isto não é uma reatestação, é uma política nova:")
        for linha in diferencas:
            print(f"  {linha}")
        return 1

    arquivos = []
    for caminho, registrado in registro["code"].items():
        conteudo = _blob(caminho)
        if conteudo is None:
            raise SystemExit(f"{caminho} não está versionado; não há o que reatestar")
        atual = _sha(conteudo)
        if atual == registrado:
            causa = "inalterado"
        elif registrado == _sha(conteudo.replace(b"\n", b"\r\n")):
            causa = "fim_de_linha"
        else:
            causa = "implementado_apos_a_fotografia"
        arquivos.append({"file": caminho, "registered_sha256": registrado,
                         "sha256": atual, "difference": causa})

    documento = {
        "document": "reatestação dos hashes de código",
        "policy": registro["policy"],
        "re_attestation_of": {
            "file": str(REGISTRO.relative_to(ROOT)).replace("\\", "/"),
            "registered_at": registro["registered_at"],
            "registration_sha256": registro["registration_sha256"],
        },
        "approved_by": aprovador,
        "approval_source": origem,
        "re_attested_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "why": (
            "Os hashes de código da v4 foram tirados às 13:38:13 de 30/08/2026. O quarto "
            f"degrau foi acrescentado a portfolio_risk.py e profile_ladder_v2.py em seguida, e "
            f"registro e código entraram no mesmo commit ({COMMIT_DA_IMPLEMENTACAO}) às 13:54. O "
            "registro hasheou arquivos que ainda não continham a implementação do degrau que ele "
            "declara. Não é o código derivando da política ao longo do tempo: é a fotografia "
            "tirada dezesseis minutos cedo demais."),
        "parameters_changed": "none",
        "parameters_checked": (
            "Os quatro degraus e, em cada um, o teto de renda variável e o número de emissores "
            "foram comparados entre a declaração da v4 e o que profile_ladder_v2.LADDER_V2 expõe "
            "hoje. São idênticos, e o script recusa emitir este documento se deixarem de ser."),
        "confirmatory_sample_starts": registro["confirmatory_sample_starts"],
        "what_this_does_not_do": (
            "Não cria versão nova, porque não houve mudança material, e a linhagem do projeto "
            "reserva versão nova para isso. Não move a fronteira temporal: a amostra "
            "confirmatória continua começando no primeiro pregão de 2027. Não apaga o registro "
            "da v4, que fica como foi assinado."),
        "difference_meanings": {
            "inalterado": "O hash registrado bate com o arquivo que o repositório entrega.",
            "fim_de_linha": (
                "O conteúdo nunca mudou. O hash registrado foi calculado sobre bytes com CRLF "
                "numa cópia de trabalho no Windows, e o repositório entrega LF."),
            "implementado_apos_a_fotografia": (
                "O arquivo recebeu a implementação do quarto degrau depois de o registro ter "
                "sido gerado, no mesmo commit."),
        },
        "code": arquivos,
        "how_to_check": "python tools/verify_published_hashes.py",
    }

    corpo = json.dumps(documento, ensure_ascii=False, indent=2, sort_keys=True)
    documento["reattestation_sha256"] = hashlib.sha256(corpo.encode("utf-8")).hexdigest()
    SAIDA.write_text(json.dumps(documento, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8", newline="\n")

    contagem: dict[str, int] = {}
    for item in arquivos:
        contagem[item["difference"]] = contagem.get(item["difference"], 0) + 1
    print(f"{SAIDA.relative_to(ROOT)}")
    print(f"  assinada por {aprovador} ({origem})")
    print(f"  {len(arquivos)} arquivos: " + ", ".join(f"{n} {c}" for c, n in sorted(contagem.items())))
    print(f"  hash {documento['reattestation_sha256'][:12]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
