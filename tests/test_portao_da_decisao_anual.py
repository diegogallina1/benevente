"""O portão da decisão anual erra para o lado de não fazer nada.

A automação que publica carteira tem um modo de falha caro, e não é deixar de
decidir num dia: é decidir no dia errado, com insumo velho, e publicar uma
carteira que parece certa. Estes testes fixam as três respostas e a diferença
entre elas — pular é silêncio esperado, recusar é falha que precisa aparecer.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _portao():
    spec = importlib.util.spec_from_file_location(
        "portao_da_decisao_anual", ROOT / "tools" / "portao_da_decisao_anual.py")
    modulo = importlib.util.module_from_spec(spec)
    # Registrar antes de executar: @dataclass procura o módulo em sys.modules
    # para resolver a classe, e sem isso quebra com AttributeError em NoneType.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_ano_ja_decidido_nao_e_decidido_de_novo() -> None:
    """2026 tem livro publicado: nem no dia dele a automação deve reescrever."""
    veredito = _portao().avaliar(date(2026, 1, 2))
    assert veredito.acao == "pular"
    assert "já foi decidido" in veredito.motivo
    assert veredito.codigo == 0


def test_dia_util_de_janeiro_sem_decisao_manda_agir() -> None:
    veredito = _portao().avaliar(date(2027, 1, 4))
    assert veredito.acao == "agir", veredito.motivo
    assert veredito.codigo == 0


def test_fim_de_semana_e_fora_de_janeiro_sao_silencio() -> None:
    modulo = _portao()
    for dia, esperado in ((date(2027, 1, 3), "fim de semana"), (date(2027, 2, 10), "janeiro")):
        veredito = modulo.avaliar(dia)
        assert veredito.acao == "pular", (dia, veredito.motivo)
        assert esperado in veredito.motivo
        assert veredito.codigo == 0


def test_janeiro_passar_sem_decisao_e_falha_e_nao_silencio() -> None:
    """Isso não se resolve sozinho, e silenciar esconderia o ano sem carteira."""
    veredito = _portao().avaliar(date(2027, 1, 20))
    assert veredito.acao == "recusar"
    assert veredito.codigo == 1


def test_sem_captura_do_ano_anterior_o_portao_recusa() -> None:
    """Sem referência, o ensaio perde o pé e a decisão sai sem com o que ser comparada."""
    veredito = _portao().avaliar(date(2028, 1, 3))
    assert veredito.acao == "recusar"
    assert "captura de 2027" in veredito.motivo
    assert veredito.codigo == 1


def test_forcar_nao_ignora_ano_ja_decidido() -> None:
    """A saída de emergência abre a janela, não autoriza reescrever o passado."""
    veredito = _portao().avaliar(date(2026, 7, 15), forcar=True)
    assert veredito.acao == "pular"
    assert "já foi decidido" in veredito.motivo


def test_o_workflow_so_escreve_depois_do_portao() -> None:
    """Todo passo que toca dado ou repositório fica atrás da condição do portão."""
    import yaml
    fluxo = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "decisao-anual.yml").read_text(encoding="utf-8"))
    passos = fluxo["jobs"]["decidir"]["steps"]
    nomes_livres = {"Baixar repositório", "Preparar Python", "Instalar dependências", "Portão"}
    for passo in passos:
        if passo.get("name") in nomes_livres:
            continue
        assert passo.get("if") == "steps.portao.outputs.acao == 'agir'", passo.get("name")
    # E ele abre pull request em vez de publicar: quem aprova é uma pessoa.
    ultimo = passos[-1]["run"]
    assert "gh pr create" in ultimo
    assert "git push origin main" not in ultimo


def test_o_portao_escreve_as_chaves_que_o_workflow_le(tmp_path) -> None:
    """O contrato tem dois lados, e só um estava preso.

    O teste acima prende o lado do YAML: todo passo que escreve fica atrás de
    ``steps.portao.outputs.acao``. Nada prendia o lado do Python. Renomear a
    chave no portão deixava a suíte inteira verde — e em janeiro o job ficaria
    verde também, que é o pior jeito de isto falhar: sem a chave, o ``if`` de
    cada passo dá falso, nada roda, e o mês passa sem decisão parecendo sucesso.
    É exatamente o silêncio que o cabeçalho do workflow diz querer impedir.

    As chaves esperadas saem do YAML, não de uma lista escrita aqui: uma lista
    escrita à mão envelhece quando o workflow passa a ler outra saída, e o teste
    aprovaria de novo a mesma falha silenciosa.
    """
    import re
    import subprocess

    fluxo = (ROOT / ".github" / "workflows" / "decisao-anual.yml").read_text(encoding="utf-8")
    lidas = set(re.findall(r"steps\.portao\.outputs\.([A-Za-z_][A-Za-z0-9_]*)", fluxo))
    assert lidas, "o workflow deixou de ler saída do portão; este teste perdeu o objeto"

    saida = tmp_path / "github_output"
    concluido = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "portao_da_decisao_anual.py"),
         "--hoje", "2026-07-15", "--github-output", str(saida)],
        capture_output=True, text=True)
    assert saida.exists(), (
        f"o portão não escreveu arquivo nenhum: {concluido.stderr.strip()}")

    escritas = {linha.split("=", 1)[0]
                for linha in saida.read_text(encoding="utf-8").splitlines() if "=" in linha}
    faltando = lidas - escritas
    assert not faltando, (
        f"o workflow lê {sorted(faltando)} em steps.portao.outputs, e o portão "
        f"escreve {sorted(escritas)}. Em janeiro o if daria falso, nada rodaria "
        f"e o job ficaria verde sem decidir.")
