"""Decide se hoje é dia de tomar a decisão anual, e recusa quando não é.

A automação que publica carteira precisa errar para o lado de não fazer nada. O
modo de falha caro não é deixar de decidir num dia — é decidir no dia errado,
com insumo velho, e publicar uma carteira que parece certa. Este portão fica
antes de qualquer coisa que escreva, e responde três palavras: agir, pular ou
recusar.

  agir     hoje é dia útil de janeiro e o ano ainda não tem decisão
  pular    não é janeiro, é fim de semana, ou o ano já foi decidido
  recusar  é para agir, mas alguma condição impede, e seguir seria pior

A diferença entre pular e recusar importa para quem lê a automação: pular é o
esperado na maioria dos dias e sai em silêncio; recusar é anormal e tem de
aparecer como falha, com o motivo.

Feriado não é tratado aqui de propósito. O calendário da B3 muda, e uma cópia
dele neste arquivo envelheceria sem avisar. Quem responde é o dado: o retrato do
universo só existe se houve pregão, e a captura recusa retrato de outra data.
Em feriado o passo seguinte falha por ausência de dado, que é a resposta certa
vinda de quem sabe.

    python tools/portao_da_decisao_anual.py --hoje 2027-01-04
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]

#: A janela em que a automação sequer olha. Depois do dia 15 de janeiro, uma
#: decisão que não foi tomada não é mais caso de automação: é caso de alguém
#: olhar por que não foi.
PRIMEIRO_DIA, ULTIMO_DIA = 1, 15


@dataclass(frozen=True)
class Veredito:
    acao: str          # "agir", "pular" ou "recusar"
    motivo: str
    ano: int

    @property
    def codigo(self) -> int:
        """Recusar é falha; agir e pular, não."""
        return 1 if self.acao == "recusar" else 0


def livro_do_ano(ano: int) -> Path:
    return ROOT / "artifacts" / f"profile_books_{ano}" / f"profile_books_{ano}.json"


def captura_do_ano(ano: int) -> Path:
    return ROOT / "artifacts" / f"insumos_{ano}" / "manifesto.json"


def avaliar(hoje: date, forcar: bool = False) -> Veredito:
    ano = hoje.year

    if livro_do_ano(ano).exists():
        publicado = json.loads(livro_do_ano(ano).read_text(encoding="utf-8"))
        return Veredito("pular", f"o ano já foi decidido em {publicado['decision_date']}", ano)

    if not forcar:
        if hoje.month != 1:
            return Veredito("pular", "a decisão anual é de janeiro", ano)
        if not PRIMEIRO_DIA <= hoje.day <= ULTIMO_DIA:
            # Passou a janela sem decisão: isso não se resolve sozinho, e
            # silenciar seria esconder que o ano começou sem carteira.
            return Veredito("recusar",
                            f"passou o dia {ULTIMO_DIA} de janeiro e o ano não tem decisão", ano)
        if hoje.weekday() >= 5:
            return Veredito("pular", "fim de semana, não há pregão", ano)

    # A captura do ano anterior tem de existir: sem ela, não há com o que
    # comparar o que vai ser produzido, e o ensaio perde o pé.
    if not captura_do_ano(ano - 1).exists():
        return Veredito("recusar",
                        f"não há captura de {ano - 1} para servir de referência ao ensaio", ano)

    return Veredito("agir", "dia útil dentro da janela e o ano ainda não tem decisão", ano)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--hoje", default=None, help="Data a avaliar, AAAA-MM-DD. Padrão: hoje em São Paulo.")
    parser.add_argument("--forcar", action="store_true",
                        help="Ignora janela e dia da semana. Não ignora ano já decidido.")
    parser.add_argument("--github-output", type=Path, default=None,
                        help="Arquivo onde escrever acao= e ano= para o workflow ler.")
    argumentos = parser.parse_args()

    hoje = (date.fromisoformat(argumentos.hoje) if argumentos.hoje
            else datetime.now(ZoneInfo("America/Sao_Paulo")).date())
    veredito = avaliar(hoje, argumentos.forcar)

    print(f"{veredito.acao}: {veredito.motivo} (ano {veredito.ano}, avaliado em {hoje})")
    if argumentos.github_output:
        with argumentos.github_output.open("a", encoding="utf-8") as fh:
            fh.write(f"acao={veredito.acao}\nano={veredito.ano}\n")
    return veredito.codigo


if __name__ == "__main__":
    raise SystemExit(main())
