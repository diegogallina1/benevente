# -*- coding: utf-8 -*-
"""Confere a ligação com a B3 no ambiente de certificação.

Roda depois que o pacote de acesso chegar por e-mail. Não faz cadastro, não
aceita termos e não cria conta — essas etapas são de quem assina, não de um
programa.

O que ele faz é responder, em ordem, as perguntas que travam uma integração
nova, e parar na primeira que falhar em vez de despejar um traceback:

1. As variáveis de ambiente existem?
2. O certificado e a chave estão onde dizem estar, em PEM?
3. O TLS mútuo fecha com a B3?
4. Os caminhos das APIs de negócio estão configurados?

Cada resposta negativa vem com o que fazer a seguir.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from b3_client import (CERT_HOST, CERT_PORT, HEALTHCHECK, Credenciais,  # noqa: E402
                       ConfiguracaoAusente, Endpoints, sessao_mtls)

CONFIG = ROOT / "data" / "b3_endpoints.json"
VARIAVEIS = {
    "B3_CERT_P12": "certificado em PEM, convertido do .p12 que a B3 enviou",
    "B3_CERT_KEY_PEM": "chave privada em PEM, do mesmo .p12",
    "B3_CERT_SENHA": "senha do .p12 (usada só na conversão)",
    "B3_CA_BUNDLE": "CA da B3, para validar o servidor",
    "B3_CLIENT_ID": "identificador do licenciado, do pacote de acesso",
}
CONVERSAO = (
    "  openssl pkcs12 -in b3.p12 -clcerts -nokeys -out b3_cert.pem\n"
    "  openssl pkcs12 -in b3.p12 -nocerts -nodes  -out b3_key.pem")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--token", help="token do pacote de acesso")
    parser.add_argument("--host", default=CERT_HOST)
    args = parser.parse_args()

    print(f"Ambiente de certificação: {args.host} (porta {CERT_PORT})\n")

    print("1. Variáveis de ambiente")
    faltando = [v for v in VARIAVEIS if not os.environ.get(v)]
    for nome, para_que in VARIAVEIS.items():
        marca = "  ok  " if nome not in faltando else "  --  "
        print(f"{marca}{nome:<18} {para_que}")
    if faltando:
        print("\n   Defina as que faltam e rode de novo. Para converter o .p12:")
        print(CONVERSAO)
        return 1

    print("\n2. Arquivos no lugar")
    for nome in ("B3_CERT_P12", "B3_CERT_KEY_PEM", "B3_CA_BUNDLE"):
        caminho = Path(os.environ[nome])
        if not caminho.exists():
            print(f"  --  {nome} aponta para {caminho}, que não existe.")
            return 1
        cabecalho = caminho.read_text(encoding="utf-8", errors="ignore")[:64]
        formato = "PEM" if "-----BEGIN" in cabecalho else "NÃO parece PEM"
        print(f"  {'ok  ' if formato == 'PEM' else '--  '}{nome:<18} {formato}")
        if formato != "PEM":
            print("\n   O pacote da B3 vem em .p12; converta antes:")
            print(CONVERSAO)
            return 1

    print("\n3. TLS mútuo")
    if not args.token:
        print("  --  passe --token para chamar o healthcheck da B3.")
        print("      O token vem no pacote de acesso enviado por e-mail.")
        return 1
    try:
        transporte = sessao_mtls(Credenciais.do_ambiente())
        status, corpo = transporte(
            "GET", f"{args.host}{HEALTHCHECK.format(token=args.token)}",
            {"Authorization": f"Bearer {args.token}"}, {})
    except ConfiguracaoAusente as erro:
        print(f"  --  {erro}")
        return 1
    except Exception as erro:                                   # noqa: BLE001
        print(f"  --  a conexão não fechou: {type(erro).__name__}: {erro}")
        print("      Erro de certificado costuma ser CA errada ou par cert/chave trocado.")
        return 1
    print(f"  {'ok  ' if status == 200 else '--  '}HTTP {status} · {corpo}")
    if status != 200:
        return 1

    print("\n4. Caminhos das APIs de negócio")
    endpoints = Endpoints.de_arquivo(CONFIG)
    pendentes = [nome for nome in ("posicao", "movimentacao", "negociacao", "guia", "autorizacao")
                 if not getattr(endpoints, nome)]
    for nome in ("posicao", "movimentacao", "negociacao", "guia", "autorizacao"):
        valor = getattr(endpoints, nome)
        print(f"  {'ok  ' if valor else '--  '}{nome:<14} {valor or 'não configurado'}")
    if pendentes:
        print(f"\n   Preencha {CONFIG.relative_to(ROOT)} com os caminhos da Documentação")
        print("   Técnica do portal. O arquivo diz onde encontrar cada um.")
        return 1

    print("\nLigação completa. O cliente pode ler posição de um investidor que tenha autorizado.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
