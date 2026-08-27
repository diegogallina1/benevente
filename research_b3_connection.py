"""Demonstra a conexão com a B3 e, principalmente, o que ela não resolve.

O caso é o mais comum que existe numa carteira brasileira: uma ação boa comprada
há muito tempo. A posição chega da B3 sem problema; o custo dela, não, porque a
base da Área do Investidor começa em 01/11/2019 e a compra é anterior.

O resultado é desconfortável e é o ponto: a maior posição da carteira, a que
carrega o maior imposto latente, é justamente a que não dá para apurar. Um
produto que quisesse parecer completo estimaria o custo. Este nomeia a lacuna e
pede o dado, porque um imposto estimado tem a mesma aparência de um medido.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import json

from b3_client import B3Client, Endpoints, Frescor, classificar, referencia_esperada
from b3_connection import (BASE_COMECA_EM, COBERTURA, Consentimento, Negociacao,
                           Qualidade, reconstruir_custo, relatorio_de_lacunas)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "artifacts" / "b3_connection_v1"

#: Custódia como a API de Posição devolve: quantidade e valor, sem custo.
CUSTODIA = {"CURY3": (4_000, 44_000.0), "WEGE3": (3_000, 180_000.0),
            "MGLU3": (10_000, 25_000.0)}

#: Negociações como a API devolve: só a partir de 01/11/2019.
NEGOCIACOES = [
    Negociacao("CURY3", date(2021, 3, 12), "compra", 2_500, 6.10),
    Negociacao("CURY3", date(2022, 8, 4), "compra", 1_500, 5.20),
    Negociacao("MGLU3", date(2021, 6, 1), "compra", 6_000, 22.00),
    Negociacao("MGLU3", date(2021, 11, 9), "compra", 4_000, 15.00),
    # A WEGE3 foi comprada em 2017: a base não tem essa compra. O que existe é
    # um aumento posterior, que explica só um terço da posição.
    Negociacao("WEGE3", date(2023, 5, 18), "compra", 1_000, 38.00),
]


def main() -> None:
    consentimento = Consentimento(
        documento_hash=Consentimento.anonimiza("123.456.789-09"),
        licenciado="Benevente", concedido_em="2026-08-26T09:12:00-03:00",
        escopo=("Posição", "Movimentação", "Negociação de Ativos", "Eventos Provisionados"))
    registro = consentimento.registro()

    print("CONSENTIMENTO")
    print(f"  documento: {registro['documento_hash'][:16]}… (hash; o CPF não é guardado)")
    print(f"  escopo:    {', '.join(registro['escopo'])}")
    print(f"  revogação: {registro['revogavel_em']}")
    print(f"  registro:  {registro['registro_sha256'][:16]}…")

    print(f"\nCUSTO RECONSTRUÍDO (base da B3 desde {BASE_COMECA_EM:%d/%m/%Y})")
    custos = {}
    for ticker, (quantidade, valor) in sorted(CUSTODIA.items()):
        custo = reconstruir_custo(ticker, quantidade, NEGOCIACOES)
        custos[ticker] = custo
        marca = "ok " if custo.qualidade.apura_imposto else "!! "
        print(f"  {marca}{ticker:<8} valor R$ {valor:>10,.0f} · custo "
              f"R$ {custo.valor_brl:>10,.0f} · cobertura {custo.cobertura:>5.0%}")
        print(f"       {custo.qualidade.value}")
        if custo.observacao:
            print(f"       {custo.observacao}")

    lacunas = relatorio_de_lacunas(custos)
    print(f"\nLACUNAS: {lacunas['com_custo_defensavel']} de {lacunas['total_posicoes']} "
          f"posições com custo defensável")
    for ticker, dados in lacunas["pendentes"].items():
        print(f"  {ticker}: {dados['observacao']}")
    print(f"\n  {lacunas['consequencia']}")

    print("\nO QUE A CONEXÃO NÃO ENTREGA")
    for item in COBERTURA["nao_entrega"]:
        print(f"  · {item}")

    # O estado da carga, que a tela precisa distinguir de "nada mudou".
    agora = datetime(2026, 8, 27, 10, 21)
    cenarios = {
        "atual": classificar(agora, referencia_esperada(agora), True),
        "sem_movimento": classificar(agora, referencia_esperada(agora), False),
        "nao_atualizou": classificar(agora, date(2026, 8, 20), False),
        "cedo": classificar(agora.replace(hour=7), None, False),
    }
    print("\nFRESCOR DA CARGA")
    for nome, estado in cenarios.items():
        print(f"  {nome:<15} {estado.value}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "connection_example.json").write_text(json.dumps({
        "status": "demonstration_only",
        "warning": "Custódia e negociações sintéticas, escritas para exercitar o módulo.",
        "source": "APIs da Área do Investidor da B3, Manual Técnico",
        "base_starts": BASE_COMECA_EM.isoformat(),
        "consent": registro,
        "coverage": COBERTURA,
        "cost_basis": {t: {"valor_brl": c.valor_brl, "qualidade": c.qualidade.value,
                           "cobertura": round(c.cobertura, 4), "observacao": c.observacao}
                       for t, c in sorted(custos.items())},
        "gaps": lacunas,
        "freshness": {
            "reference": "D-1, publicado a partir das 8h",
            "sla_monthly": 0.97,
            "why_it_matters": (
                "Com 97% de disponibilidade ao mês, a carteira deixa de chegar por volta de uma "
                "vez por mês. Uma tela que trata 'sem movimentação' e 'não atualizou' do mesmo "
                "jeito mostra a posição de anteontem como se fosse a de ontem, sem avisar."),
            "states": {nome: estado.value for nome, estado in cenarios.items()},
            "example": {"state": "sem_movimento",
                        "explicacao": cenarios["sem_movimento"].value,
                        "data_referencia": referencia_esperada(agora).isoformat(),
                        "utilizavel": True},
        },
    }, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
