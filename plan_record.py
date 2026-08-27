"""O registro da decisão: o que a tela emite e o dossiê consome.

Até aqui o dossiê era gerado de um exemplo fixo. A pessoa respondia quatro
perguntas, informava um custo, escolhia um plano — e o PDF saía com outras
respostas, outro custo e o plano que o script preferisse. Para uma demonstração
passava; para um documento que leva assinatura, não.

Este módulo define o que separa as duas metades. A tela produz um registro
pequeno e legível: as respostas, os custos declarados e o plano escolhido. O
gerador recebe esse registro e refaz as contas do zero, com o módulo de sempre.
Nenhum número atravessa a fronteira — só as decisões. É o que garante que o
dossiê não possa discordar da tela por acidente, porque não há dois cálculos.

Duas propriedades que o registro carrega de propósito:

* **Custo declarado é marcado como declarado.** Quando o cliente informa quanto
  pagou, aquilo entra como ``Qualidade.DECLARADO``, não como reconstruído. O
  dossiê imprime a diferença, e ela importa: um é extrato da B3, o outro é
  memória de quem tem interesse no resultado.
* **O plano não escolhido continua no documento.** O registro guarda a escolha,
  e o gerador monta os dois lados de qualquer forma. Uma decisão sem alternativa
  documentada não se distingue, depois, de uma execução automática.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json

from b3_connection import Qualidade
from client_intake import PROFILES, QUESTIONS, Intake
from portfolio_mapping import Position

SCHEMA = "benevente_plan_record_v1"
CAMINHOS = ("adequar", "adaptar")


@dataclass(frozen=True)
class PlanRecord:
    """A decisão de uma pessoa, do jeito que a tela a produz."""
    answers: dict[str, str]
    chosen_path: str
    declared_costs: dict[str, float] = field(default_factory=dict)
    decided_at: str = ""
    client: str = ""

    def __post_init__(self) -> None:
        if self.chosen_path not in CAMINHOS:
            raise ValueError(f"plano deve ser um de {CAMINHOS}, veio {self.chosen_path!r}")
        obrigatorias = {q.key for q in QUESTIONS if q.kind == "escolha"}
        faltando = sorted(obrigatorias - set(self.answers))
        if faltando:
            raise ValueError(f"faltam respostas: {faltando}")
        for pergunta in QUESTIONS:
            escolha = self.answers.get(pergunta.key)
            if escolha is None:
                continue
            validas = {o.value for o in pergunta.options}
            if validas and escolha not in validas:
                raise ValueError(f"{pergunta.key}: {escolha!r} não é uma resposta possível")
        for ticker, valor in self.declared_costs.items():
            if not isinstance(valor, (int, float)) or valor < 0:
                raise ValueError(f"custo declarado de {ticker} inválido: {valor!r}")

    @property
    def intake(self) -> Intake:
        return Intake(answers=dict(self.answers))

    @property
    def profile(self) -> str:
        perfil = self.intake.profile
        assert perfil in PROFILES
        return perfil

    def to_json(self) -> dict:
        return {
            "schema": SCHEMA,
            "decided_at": self.decided_at,
            "client": self.client,
            "answers": dict(self.answers),
            "profile": self.profile,
            "declared_costs": {k: round(float(v), 2) for k, v in sorted(self.declared_costs.items())},
            "chosen_path": self.chosen_path,
        }

    @classmethod
    def from_json(cls, payload: dict) -> "PlanRecord":
        if payload.get("schema") != SCHEMA:
            raise ValueError(f"registro de esquema desconhecido: {payload.get('schema')!r}")
        registro = cls(
            answers=dict(payload["answers"]),
            chosen_path=payload["chosen_path"],
            declared_costs={k: float(v) for k, v in (payload.get("declared_costs") or {}).items()},
            decided_at=payload.get("decided_at", ""),
            client=payload.get("client", ""),
        )
        # O perfil viaja no registro por conveniência de leitura, mas quem manda
        # são as respostas: se os dois discordarem, alguém editou o arquivo.
        declarado = payload.get("profile")
        if declarado and declarado != registro.profile:
            raise ValueError(
                f"o registro diz perfil {declarado!r}, mas as respostas dão {registro.profile!r}")
        return registro


def apply_declared_costs(positions: list[Position], declared: dict[str, float]) -> list[Position]:
    """Substitui o custo das posições que o cliente informou.

    A posição volta marcada como ``DECLARADO``, nunca como reconstruída: o
    dossiê precisa poder dizer que aquele número veio de memória, não de
    extrato. Informar custo de uma posição que a B3 já explicava é permitido e
    também vira declarado — quem informa está afirmando que sabe melhor, e isso
    fica registrado.
    """
    procurados = {t.removesuffix(".SA").upper() for t in declared}
    achados = set()
    saida = []
    for posicao in positions:
        chave = posicao.ticker.removesuffix(".SA").upper()
        if chave in procurados:
            achados.add(chave)
            valor = next(v for t, v in declared.items()
                         if t.removesuffix(".SA").upper() == chave)
            saida.append(Position(
                ticker=posicao.ticker, bucket=posicao.bucket,
                market_value_brl=posicao.market_value_brl, cost_basis_brl=float(valor),
                source=posicao.source, conglomerate=posicao.conglomerate,
                days_held=posicao.days_held, liquid=posicao.liquid,
                cost_quality=Qualidade.DECLARADO))
        else:
            saida.append(posicao)
    sobrando = sorted(procurados - achados)
    if sobrando:
        raise ValueError(f"custo declarado para posição que não existe na carteira: {sobrando}")
    return saida


def load(path) -> PlanRecord:
    return PlanRecord.from_json(json.loads(path.read_text(encoding="utf-8")))
