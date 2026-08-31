"""As perguntas que definem o perfil — e por que são estas seis.

Questionário de suitability, no Brasil, quase sempre funciona assim: dez a
quinze perguntas, cada resposta vale pontos, a soma cai numa faixa e a faixa
vira um rótulo. O problema é que a pontuação é inventada. Ninguém consegue
defender por que "invisto há mais de cinco anos" vale três pontos e "aceito
oscilação" vale dois, nem o que a soma dos dois significa.

Aqui a lógica é outra e cabe numa frase: **a restrição mais apertada manda**.
Cada pergunta produz um teto de perfil, e o perfil final é o menor deles. Não há
soma, não há peso, não há nota. Se o dinheiro é de dois anos, não importa o
apetite declarado — o horizonte é o teto. Isso é auditável: dá para apontar qual
resposta determinou o resultado, o que uma soma de pontos nunca permite.

A pergunta central é a da queda, e ela é feita com os números reais medidos de
cada perfil (−9,2%, −17,9%, −28,9% na janela declarada), não com adjetivos.
"Perfil moderado" não significa nada; "a pior queda medida foi de dezoito por
cento e durou meses" significa, e é a única forma honesta de perguntar, porque
é exatamente essa a experiência que faz alguém vender no fundo.

O questionário não decide nada sozinho: ele produz um teto e as restrições que
o mapa precisa respeitar. Quem assina continua podendo escolher diferente, desde
que registre o porquê.
"""
from __future__ import annotations

from dataclasses import dataclass, field

#: Do mais apertado ao mais solto. A ordem e o que faz o perfil ser o menor
#: teto entre as respostas, em vez de uma soma de pontos.
PROFILES = ("ultraconservador", "conservador", "equilibrado", "arrojado")
RANK = {name: i for i, name in enumerate(PROFILES)}

#: Piores quedas medidas na janela declarada (2015–2025, política v3). São elas
#: que dão sentido à pergunta central — e publicá-las é o oposto de perguntar
#: "qual o seu apetite a risco?".
WORST_DRAWDOWN = {"ultraconservador": -0.0081, "conservador": -0.0917,
                  "equilibrado": -0.1788, "arrojado": -0.2895}


@dataclass(frozen=True)
class Option:
    value: str
    label: str
    caps_profile: str | None = None      # teto de perfil que esta resposta impõe
    note: str = ""                        # por que ela limita
    short: str = ""                       # forma curta, para o resumo das respostas

    @property
    def brief(self) -> str:
        return self.short or self.label


@dataclass(frozen=True)
class Question:
    key: str
    prompt: str
    help: str
    options: tuple[Option, ...] = ()
    kind: str = "escolha"                 # "escolha", "valor" ou "texto"


QUESTIONS: tuple[Question, ...] = (
    Question(
        "horizonte",
        "Quando vai precisar do dinheiro?",
        "Prazo curto não dá tempo de uma queda se recuperar.",
        (Option("ate_2", "Até dois anos", "conservador",
                "com prazo curto, uma queda não tem tempo de se recuperar", "até 2 anos"),
         Option("2_a_5", "De dois a cinco anos", "equilibrado",
                "cinco anos cobrem a maior parte das quedas medidas, mas não todas", "2 a 5 anos"),
         Option("5_mais", "Cinco anos ou mais", None, "", "5+ anos")),
    ),
    Question(
        "queda",
        "Qual queda você aguenta sem vender?",
        "Na janela medida: ultraconservador 0,8%, conservador 9,2%, equilibrado 17,9%, "
        "arrojado 28,9%.",
        (Option("ate_2", "Até 2%", "ultraconservador",
                "só o ultraconservador ficou dentro desse limite na janela medida",
                "queda até 2%"),
         Option("ate_10", "Até 10%", "conservador",
                "só o conservador ficou dentro desse limite na janela medida", "queda até 10%"),
         Option("ate_20", "Até 20%", "equilibrado",
                "o arrojado passou de 28% na pior queda, além do que foi declarado",
                "queda até 20%"),
         Option("acima_20", "Mais de 20%", None, "", "queda acima de 20%")),
    ),
    Question(
        "reserva",
        "Tem reserva de emergência separada?",
        "Sem reserva, o primeiro imprevisto vira venda forçada.",
        (Option("sim", "Sim", None, "", "com reserva"),
         Option("nao", "Ainda não", "conservador",
                "sem reserva, este dinheiro é a reserva na prática", "sem reserva")),
    ),
    Question(
        "retirada",
        "Vai retirar todo mês?",
        "Retirada mensal exige caixa e limita o que pode oscilar.",
        (Option("nao", "Não", None, "", "sem retirada"),
         Option("sim", "Sim", "equilibrado",
                "retirada recorrente exige caixa e reduz o que pode oscilar", "com retirada")),
    ),
    Question(
        "prejuizo",
        "Tem prejuízo a compensar em ações?",
        "Ele abate o imposto das vendas de agora. Sem informar, o custo sai maior.",
        kind="valor",
    ),
    Question(
        "travar",
        "Alguma posição que não pode vender?",
        "Carência, ação de família. O mapa respeita e registra.",
        kind="texto",
    ),
)


@dataclass
class Intake:
    """As respostas, o perfil que elas permitem e o que o limitou."""
    answers: dict[str, str] = field(default_factory=dict)
    carried_loss_brl: float = 0.0
    locked_tickers: tuple[str, ...] = ()

    @property
    def profile(self) -> str:
        return self.assessment()["profile"]

    def assessment(self) -> dict:
        """O perfil é o menor teto. Sempre dá para apontar quem o impôs."""
        teto, motivos = "arrojado", []
        for question in QUESTIONS:
            escolha = self.answers.get(question.key)
            option = next((o for o in question.options if o.value == escolha), None)
            if option is None:
                continue
            if option.caps_profile is not None and RANK[option.caps_profile] < RANK[teto]:
                teto = option.caps_profile
            # Toda resposta entra, inclusive as que não limitaram nada. Um
            # registro que só guarda a resposta vencedora não permite conferir a
            # conta: quem lê não sabe o que mais foi perguntado.
            motivos.append({"question": question.prompt, "answer": option.label,
                            "caps_at": option.caps_profile or "não limita",
                            "why": option.note or ("teto sem justificativa registrada"
                                                   if option.caps_profile else "não impõe teto")})
        vinculante = [m for m in motivos if m["caps_at"] == teto]
        return {
            "profile": teto,
            "worst_measured_drawdown": WORST_DRAWDOWN[teto],
            "binding": vinculante,
            "all_limits": motivos,
            "rationale": (
                f"Perfil {teto}: "
                + ("; ".join(f"{m['answer'].lower()}, {m['why']}" for m in vinculante if m["why"])
                   or "nenhuma resposta impôs teto abaixo do máximo")
                + "."),
            "unanswered": [q.key for q in QUESTIONS
                           if q.kind == "escolha" and q.key not in self.answers],
        }


def as_json() -> dict:
    """O questionário em formato de dado, para a tela renderizar sem duplicá-lo."""
    return {
        "method": ("A restrição mais apertada define o perfil. Não há pontuação: cada resposta "
                   "impõe um teto e vale o menor deles."),
        "worst_measured_drawdown": WORST_DRAWDOWN,
        "questions": [
            {"key": q.key, "prompt": q.prompt, "help": q.help, "kind": q.kind,
             "options": [{"value": o.value, "label": o.label, "brief": o.brief,
                          "caps_profile": o.caps_profile, "note": o.note} for o in q.options]}
            for q in QUESTIONS
        ],
    }
