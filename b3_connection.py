"""A conexão com a B3, e o que ela honestamente não traz.

O mapa até aqui recebia a carteira pronta. Este módulo é de onde ela vem, e
escrevê-lo mudou o mapa, porque a leitura do manual técnico da B3 derrubou uma
suposição que estava embutida em tudo: a de que a posição chega com o custo.

Ela não chega. As APIs da Área do Investidor têm endpoint de Posição, de
Movimentação, de Negociação, de Eventos Provisionados — e nenhum de preço médio
ou custo de aquisição. O custo precisa ser **reconstruído** das negociações, e a
reconstrução tem três buracos que não se fecham com engenharia:

* **A base da B3 começa em 01/11/2019.** Ação comprada antes disso chega sem
  nenhuma compra que a explique. Quem investe há mais tempo — exatamente o
  cliente com mais ganho acumulado e mais imposto em jogo — é quem tem o dado
  pior.
* **Transferência entre custodiantes (STVM) traz o ativo sem a história.** A
  posição aparece, as compras que a formaram ficaram na outra corretora.
* **Renda fixa de balcão traz apenas quantidade, ISIN, data de aquisição e
  vencimento.** Sem valor, sem custo. E só o regime depositado mais o registrado
  com Selo Certifica.

A saída errada seria estimar o custo faltante e seguir. O mapa mostra imposto, o
imposto vira decisão de vender ou não, e um imposto inventado é pior que imposto
nenhum: ele parece uma medição. A saída deste módulo é declarar a qualidade do
custo por posição e deixar o mapa recusar-se a somar o que não sabe.

O consentimento também é da B3, não nosso: o investidor autoriza dentro da área
logada dela e revoga em Minha Conta → Segurança → Aplicativos e Sites, sem
passar por nós. Guardamos o registro de que houve consentimento — encadeado e
com hash, como todo o resto do projeto —, nunca a credencial.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import hashlib
import json

#: A base da Área do Investidor começa aqui. Antes disso a B3 não tem o dado, e
#: nenhuma chamada, retentativa ou paginação faz aparecer.
BASE_COMECA_EM = date(2019, 11, 1)

#: Só uma consulta por investidor por dia: é orientação expressa do manual, e a
#: API Guia existe para dizer quem teve movimentação e evitar o resto.
CONSULTAS_POR_DIA = 1

#: Os dados são de D-1, publicados a partir das 8h.
REFERENCIA = "D-1, disponível a partir das 8h"


class Qualidade(str, Enum):
    """De onde veio o custo de aquisição — e o quanto ele suporta uma conta.

    A ordem importa: só ``RECONSTRUIDO`` e ``DECLARADO`` sustentam apuração de
    imposto. ``PARCIAL`` e ``AUSENTE`` não, e o mapa precisa saber disso sem ter
    que adivinhar por um valor sentinela.
    """
    RECONSTRUIDO = "reconstruído das negociações na B3"
    DECLARADO = "declarado pelo cliente e não conferido"
    PARCIAL = "reconstruído só em parte: há posição anterior a 01/11/2019"
    AUSENTE = "sem custo: a B3 não fornece e ninguém informou"

    @property
    def apura_imposto(self) -> bool:
        return self in (Qualidade.RECONSTRUIDO, Qualidade.DECLARADO)


@dataclass(frozen=True)
class Consentimento:
    """O registro de que houve autorização. Nunca a credencial.

    A autorização acontece dentro da área logada da B3 e é revogada lá também.
    O que fica aqui é a prova de que existiu, com quando e para qual escopo —
    porque no dia em que alguém perguntar por que lemos a carteira de fulano, a
    resposta precisa ser um documento, não uma lembrança.
    """
    documento_hash: str                    # SHA-256 do CPF/CNPJ, nunca o número
    licenciado: str
    concedido_em: str                      # ISO-8601
    escopo: tuple[str, ...]
    revogavel_em: str = ("investidor.b3.com.br, em Minha Conta, Segurança, "
                         "Aplicativos e Sites")
    registro_anterior_sha256: str | None = None

    @staticmethod
    def anonimiza(documento: str) -> str:
        """CPF vira hash antes de tocar em qualquer registro nosso."""
        limpo = "".join(c for c in documento if c.isdigit())
        if len(limpo) not in (11, 14):
            raise ValueError("Documento deve ser CPF (11) ou CNPJ (14) dígitos.")
        return hashlib.sha256(limpo.encode("utf-8")).hexdigest()

    def registro(self) -> dict:
        corpo = {
            "documento_hash": self.documento_hash,
            "licenciado": self.licenciado,
            "concedido_em": self.concedido_em,
            "escopo": list(self.escopo),
            "revogavel_em": self.revogavel_em,
            "registro_anterior_sha256": self.registro_anterior_sha256,
            "credencial_armazenada": False,
        }
        corpo["registro_sha256"] = hashlib.sha256(
            json.dumps(corpo, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")).encode("utf-8")).hexdigest()
        return corpo


@dataclass(frozen=True)
class Negociacao:
    """Uma compra ou venda, como a API de Negociação de Ativos devolve."""
    ticker: str
    data: date
    lado: str                              # "compra" ou "venda"
    quantidade: float
    preco: float

    @property
    def financeiro(self) -> float:
        return self.quantidade * self.preco


@dataclass
class Custo:
    """O custo apurado e o quanto dele se pode defender."""
    valor_brl: float
    quantidade_coberta: float
    quantidade_total: float
    qualidade: Qualidade
    observacao: str = ""

    @property
    def cobertura(self) -> float:
        return (self.quantidade_coberta / self.quantidade_total
                if self.quantidade_total > 0 else 0.0)


def reconstruir_custo(ticker: str, quantidade_atual: float,
                      negociacoes: list[Negociacao]) -> Custo:
    """Custo médio a partir das negociações, com o buraco declarado.

    Percorre compras e vendas em ordem e abate as vendas ao custo médio, que é o
    que a legislação manda. Se ao fim as compras conhecidas não explicam a
    quantidade que está em custódia, a diferença veio de antes de 01/11/2019 ou
    de uma transferência entre corretoras — e isso é dito, não preenchido.
    """
    if quantidade_atual <= 0:
        return Custo(0.0, 0.0, 0.0, Qualidade.AUSENTE, "posição zerada")

    relevantes = sorted((n for n in negociacoes if n.ticker == ticker),
                        key=lambda n: n.data)
    if not relevantes:
        return Custo(0.0, 0.0, quantidade_atual, Qualidade.AUSENTE,
                     "nenhuma negociação na base da B3 explica esta posição")

    quantidade, custo = 0.0, 0.0
    for n in relevantes:
        if n.lado == "compra":
            quantidade += n.quantidade
            custo += n.financeiro
        else:
            if quantidade <= 0:
                # Venda sem compra anterior conhecida: a posição vendida veio de
                # antes da base. Abater ao custo zero inventaria um ganho.
                continue
            medio = custo / quantidade
            vendida = min(n.quantidade, quantidade)
            quantidade -= vendida
            custo -= medio * vendida

    if quantidade <= 0:
        return Custo(0.0, 0.0, quantidade_atual, Qualidade.AUSENTE,
                     "as negociações conhecidas zeram a posição, mas há saldo em "
                     "custódia: a origem dele está fora da base")

    medio = custo / quantidade
    coberta = min(quantidade, quantidade_atual)
    faltando = quantidade_atual - coberta
    if faltando > max(1e-6, quantidade_atual * 1e-4):
        return Custo(round(medio * coberta, 2), coberta, quantidade_atual,
                     Qualidade.PARCIAL,
                     f"{faltando:.0f} de {quantidade_atual:.0f} unidades sem compra "
                     f"na base (anteriores a {BASE_COMECA_EM:%d/%m/%Y} ou "
                     f"transferidas de outra corretora)")
    return Custo(round(medio * quantidade_atual, 2), quantidade_atual, quantidade_atual,
                 Qualidade.RECONSTRUIDO,
                 f"{len([n for n in relevantes if n.lado == 'compra'])} compra(s) "
                 f"desde {relevantes[0].data:%d/%m/%Y}")


#: O que a conexão entrega e o que não entrega, como dado e não como prosa —
#: para a tela, o dossiê e a documentação lerem a mesma coisa.
COBERTURA = {
    "entrega": [
        "Renda variável depositada na B3: ações, ETFs, BDRs, FIIs — quantidade e valor",
        "Tesouro Direto: quantidade e valor",
        "Negociações (compras e vendas) desde 01/11/2019",
        "Eventos corporativos provisionados",
        "Empréstimo de ativos e derivativos",
    ],
    "entrega_pela_metade": [
        "Renda fixa de balcão: só quantidade, ISIN, data de aquisição e vencimento — "
        "sem valor de mercado e sem custo",
        "Renda fixa: apenas o regime depositado e o registrado com Selo Certifica",
    ],
    "nao_entrega": [
        "Preço médio ou custo de aquisição: não existe endpoint para isso",
        "Qualquer dado anterior a 01/11/2019",
        "Ativos fora da B3: fundos não registrados, previdência, cripto, conta no exterior",
        "Imóveis, participações societárias e o que nunca passou por custódia",
    ],
    "condicoes": [
        "A API é contratada com a B3; o ambiente de certificação é livre, o de produção não",
        "O investidor autoriza dentro da área logada da B3 e revoga lá, sem passar por nós",
        "Dados de D-1, publicados a partir das 8h, uma consulta por investidor por dia",
        "SLA de disponibilidade de 97% ao mês: a carteira pode simplesmente não chegar",
    ],
}


def relatorio_de_lacunas(custos: dict[str, Custo]) -> dict:
    """O que precisa do cliente antes de o imposto poder ser somado."""
    pendentes = {t: c for t, c in custos.items() if not c.qualidade.apura_imposto}
    return {
        "total_posicoes": len(custos),
        "com_custo_defensavel": len(custos) - len(pendentes),
        "pendentes": {t: {"qualidade": c.qualidade.value, "observacao": c.observacao,
                          "cobertura": round(c.cobertura, 4)}
                      for t, c in sorted(pendentes.items())},
        "consequencia": (
            "Enquanto houver posição sem custo defensável, o imposto do plano é parcial. "
            "O mapa mostra o que consegue apurar e nomeia o que ficou de fora, em vez de "
            "estimar a diferença — um imposto estimado tem a mesma aparência de um imposto "
            "medido e leva à mesma decisão de vender."),
    }
