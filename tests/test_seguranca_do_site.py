"""A postura de segurança do site é contrato, não configuração esquecida.

A auditoria de 02/09/2026 encontrou a lista de origens da API sem o domínio
canônico do próprio site: toda requisição POST vinda de benevente.dgo.fi era
respondida com 403, porque o navegador manda Origin em requisição que não é GET
mesmo quando ela é de mesma origem. O defeito passou porque nada aqui olhava
para os cabeçalhos, para a CSP ou para a guarda da API. Estes testes olham, e
tiram os valores dos próprios artefatos em vez de repeti-los à mão.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
VERCEL = json.loads((WEB / "vercel.json").read_text(encoding="utf-8"))
GUARD = (WEB / "api" / "_guard.js").read_text(encoding="utf-8")
RADAR_JS = (WEB / "event-radar.js").read_text(encoding="utf-8")


def _cabecalhos() -> dict[str, str]:
    regras = [regra for regra in VERCEL["headers"] if regra["source"] == "/(.*)"]
    assert regras, "a regra de cabeçalhos deve valer para todo caminho"
    return {item["key"]: item["value"] for item in regras[0]["headers"]}


def _csp() -> dict[str, str]:
    valor = _cabecalhos()["Content-Security-Policy"]
    diretivas = {}
    for parte in valor.split(";"):
        nome, _, resto = parte.strip().partition(" ")
        if nome:
            diretivas[nome] = resto.strip()
    return diretivas


def dominio_canonico() -> str:
    """A origem que as páginas declaram como canônica, lida das páginas."""
    encontrados = set()
    for pagina in sorted(WEB.glob("*.html")):
        for href in re.findall(r'rel="canonical"\s+href="(https://[^"/]+)', pagina.read_text(encoding="utf-8")):
            encontrados.add(href)
    assert len(encontrados) == 1, f"as páginas declaram origens canônicas divergentes: {sorted(encontrados)}"
    return encontrados.pop()


# --- a guarda da API conhece o site ----------------------------------------

def test_a_lista_padrao_de_origens_inclui_o_dominio_canonico() -> None:
    canonico = dominio_canonico()
    bloco = GUARD[GUARD.index("DEFAULT_ORIGINS"):GUARD.index("BENEVENTE_ALLOWED_ORIGINS")]
    assert canonico in bloco, (
        f"{canonico} é o domínio que as páginas declaram e precisa estar na lista padrão "
        "de origens da API: sem ele, todo POST do site publicado recebe 403")


def test_a_lista_de_origens_nao_depende_de_variavel_de_ambiente_para_funcionar() -> None:
    # O projeto na Vercel não tinha nenhuma variável configurada quando isto foi
    # escrito. Um padrão que só está certo com variável é um padrão errado.
    assert "process.env.BENEVENTE_ALLOWED_ORIGINS || DEFAULT_ORIGINS" in GUARD


def test_a_guarda_nao_libera_origem_arbitraria() -> None:
    assert "allowed.has(origin)" in GUARD
    for proibido in ("*", "startsWith(", "includes(origin", "endsWith("):
        assert f"return {proibido}" not in GUARD, f"comparação frouxa de origem: {proibido}"


# --- os cabeçalhos publicados ----------------------------------------------

@pytest.mark.parametrize("cabecalho,esperado", [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("X-Permitted-Cross-Domain-Policies", "none"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
])
def test_cabecalho_de_endurecimento_presente(cabecalho: str, esperado: str) -> None:
    assert _cabecalhos().get(cabecalho) == esperado


def test_hsts_longo_e_com_subdominios() -> None:
    hsts = _cabecalhos()["Strict-Transport-Security"]
    idade = int(re.search(r"max-age=(\d+)", hsts).group(1))
    assert idade >= 31_536_000, "HSTS abaixo de um ano"
    assert "includeSubDomains" in hsts


@pytest.mark.parametrize("diretiva,valor", [
    ("default-src", "'none'"),
    ("object-src", "'none'"),
    ("base-uri", "'none'"),
    ("frame-ancestors", "'none'"),
    ("form-action", "'self'"),
    ("connect-src", "'self'"),
])
def test_diretiva_fechada_da_csp(diretiva: str, valor: str) -> None:
    assert _csp().get(diretiva) == valor


def test_script_src_nao_admite_inline_nem_eval() -> None:
    # É esta diretiva que transforma injeção de HTML em texto feio em vez de
    # execução: sem 'unsafe-inline' o navegador ignora onerror= e <script>.
    script = _csp()["script-src"]
    assert script == "'self'", script
    for veneno in ("'unsafe-inline'", "'unsafe-eval'", "data:", "*"):
        assert veneno not in script


def test_a_csp_permite_exatamente_as_origens_externas_que_as_paginas_usam() -> None:
    csp = _csp()
    permitidas = {parte for valor in csp.values() for parte in valor.split() if parte.startswith("https://")}
    usadas = set()
    for pagina in sorted(WEB.glob("*.html")):
        texto = pagina.read_text(encoding="utf-8")
        for url in re.findall(r'(?:href|src)="(https://[^"/]+)', texto):
            if url != dominio_canonico():
                usadas.add(url)
    assert usadas <= permitidas, f"a página carrega origem que a CSP bloqueia: {sorted(usadas - permitidas)}"
    assert permitidas <= usadas, f"a CSP permite origem que nenhuma página usa: {sorted(permitidas - usadas)}"


def test_a_csp_nao_admite_nenhuma_origem_externa() -> None:
    """Desde que as fontes são hospedadas aqui, não há terceiro a permitir."""
    csp = _csp()
    assert csp["font-src"] == "'self'", csp["font-src"]
    externas = [parte for valor in csp.values() for parte in valor.split() if parte.startswith("http")]
    assert not externas, f"a CSP ainda abre origem externa: {externas}"


@pytest.mark.parametrize("pagina", sorted(WEB.glob("*.html")), ids=lambda p: p.name)
def test_nenhuma_pagina_manda_o_visitante_falar_com_terceiro(pagina: Path) -> None:
    # Enquanto a folha vinha do Google, o IP de cada visitante chegava lá antes
    # da primeira letra aparecer. Isso é privacidade, e some se alguém colar de
    # volta um <link> de conveniência.
    texto = pagina.read_text(encoding="utf-8")
    for terceiro in re.findall(r'(?:href|src)="(https?://[^"]+)"', texto):
        assert terceiro.startswith(dominio_canonico()), f"{pagina.name} busca {terceiro}"


@pytest.mark.parametrize("pagina", sorted(WEB.glob("*.html")), ids=lambda p: p.name)
def test_a_analitica_e_de_primeira_parte(pagina: Path) -> None:
    """Medir acesso não pode custar a privacidade que o site acabou de comprar.

    A analítica da Cloudflare era injetada na borda a partir de um domínio de
    terceiro e a CSP a bloqueava. Esta vem de /_vercel/, mesma origem: passa em
    script-src 'self' e o envio passa em connect-src 'self'. Um script de
    medição apontando para fora quebra este teste, que é o objetivo.
    """
    texto = pagina.read_text(encoding="utf-8")
    marcas = re.findall(r'<script[^>]+src="([^"]+)"', texto)
    analitica = [src for src in marcas if "insights" in src or "analytics" in src or "beacon" in src]
    assert analitica, f"{pagina.name} não carrega a analítica"
    for src in analitica:
        assert src.startswith("/_vercel/"), f"{pagina.name} mede acesso por terceiro: {src}"
    # Uma tag por produto. A integração automática da Vercel empilhou quatro por
    # página, medindo a mesma visita duas vezes e cobrando dois carregamentos.
    assert sorted(analitica) == ["/_vercel/insights/script.js", "/_vercel/speed-insights/script.js"], analitica


def test_o_site_nao_precisa_de_passo_de_build() -> None:
    """Um package.json em web/ faz a Vercel buscar um diretório de saída que não existe.

    Foi assim que a publicação parou: a integração automática instalou
    @vercel/speed-insights, um pacote de framework que este site estático não
    usa, e o passo de build que veio junto derrubou o deploy com "No Output
    Directory named public". As duas tags de mesma origem medem sem nada disso.
    """
    for nome in ("package.json", "pnpm-lock.yaml", "package-lock.json", "yarn.lock"):
        assert not (WEB / nome).exists(), (
            f"web/{nome} faz a Vercel rodar um build neste site estático e a publicação falha")


def test_nenhum_arquivo_publicado_tem_fim_de_linha_do_windows() -> None:
    """A cópia de trabalho precisa ser byte a byte o que o repositório entrega.

    O .gitattributes guarda web/ com LF. Um gerador que escreva com o padrão do
    Windows deixa CRLF na cópia local: os bytes passam a diferir dos que
    qualquer clone recebe, o hash de cache carimbado no HTML é calculado sobre
    os bytes errados, e o teste de carimbo passa aqui e quebra na CI. Já
    aconteceu três vezes, por três geradores diferentes. Este teste falha na
    primeira, e a correção é sempre a mesma: newline="\\n" em quem escreve.
    """
    culpados = []
    for arquivo in sorted(WEB.rglob("*")):
        if arquivo.is_file() and arquivo.suffix in {".js", ".css", ".html", ".json", ".txt", ".xml"}:
            if b"\r\n" in arquivo.read_bytes():
                culpados.append(str(arquivo.relative_to(WEB)))
    assert not culpados, (
        f"CRLF em arquivo publicado: {culpados}. Quem escreveu precisa passar "
        'newline="\\n"; converta o arquivo antes de recarimbar.')


def test_toda_fonte_declarada_existe_no_diretorio_publicado() -> None:
    """url() apontando para arquivo ausente cai calado na fonte do sistema.

    É o defeito que este repositório já cometeu duas vezes com nome de família;
    ao passar a hospedar os arquivos, o mesmo silêncio passa a ser possível por
    caminho errado.
    """
    folha = WEB / "fontes.css"
    referencias = re.findall(r"url\('\./([^']+)'\)", folha.read_text(encoding="utf-8"))
    assert referencias, "web/fontes.css não referencia nenhum arquivo"
    ausentes = sorted({ref for ref in referencias if not (WEB / ref).exists()})
    assert not ausentes, f"fontes.css aponta para arquivo que não existe: {ausentes}"
    # E nenhum arquivo publicado sem regra que o use.
    usados = {Path(ref).name for ref in referencias}
    orfaos = sorted(p.name for p in (WEB / "fonts").glob("*.woff2") if p.name not in usados)
    assert not orfaos, f"fonte publicada que nenhuma regra usa: {orfaos}"


def test_as_fontes_tem_cache_imutavel_e_nome_com_hash() -> None:
    """Cache eterno só é seguro porque o nome muda quando o conteúdo muda."""
    regra = [r for r in VERCEL["headers"] if r["source"] == "/fonts/(.*)"]
    assert regra, "falta a regra de cache para /fonts/"
    cache = {item["key"]: item["value"] for item in regra[0]["headers"]}["Cache-Control"]
    assert "immutable" in cache and "max-age=31536000" in cache, cache
    for arquivo in sorted((WEB / "fonts").glob("*.woff2")):
        digest = arquivo.name.split(".")[-2]
        assert re.fullmatch(r"[0-9a-f]{8}", digest), f"{arquivo.name} sem hash no nome"
        import hashlib
        real = hashlib.sha256(arquivo.read_bytes()).hexdigest()[:8]
        assert digest == real, f"{arquivo.name} tem hash de outro conteúdo ({real})"


# --- o radar renderiza texto de terceiro ------------------------------------

def test_todo_campo_de_terceiro_no_radar_passa_por_escape() -> None:
    """O radar publica manchete de terceiro; interpolação crua ali é injeção.

    A checagem é estrutural: qualquer ${item.…} ou ${analysis.…} dentro de um
    template do radar tem de estar embrulhado por escape, attr, link, Number,
    date ou stateLabel. Isso pega o campo novo que alguém acrescentar amanhã.
    """
    permitidos = ("escape(", "attr(", "link(", "Number(", "date(", "stateLabel[", "String(")
    cruas = []
    for expressao in re.findall(r"\$\{([^}]*)\}", RADAR_JS):
        alvo = expressao.strip()
        if not re.search(r"\b(item|analysis|run|data)\.", alvo):
            continue
        if not any(marca in alvo for marca in permitidos):
            cruas.append(alvo)
    assert not cruas, f"campo interpolado sem escape no radar: {cruas}"


def test_o_radar_recusa_esquema_de_url_que_executa() -> None:
    # escape() não desarma javascript:; o filtro de esquema desarma.
    assert 'url.protocol === "https:" || url.protocol === "http:"' in RADAR_JS
    assert 'href="${escape(href)}"' in RADAR_JS


# --- a automação que tem permissão de escrita -------------------------------

WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))


@pytest.mark.parametrize("caminho", WORKFLOWS, ids=lambda p: p.name)
def test_action_presa_a_sha_e_nao_a_tag(caminho: Path) -> None:
    """Tag é ponteiro móvel; estes jobs têm contents:write e um deles tem segredo."""
    for referencia in re.findall(r"uses:\s*(\S+)", caminho.read_text(encoding="utf-8")):
        _, _, versao = referencia.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", versao), f"{referencia} não está preso a um SHA"


@pytest.mark.parametrize("caminho", WORKFLOWS, ids=lambda p: p.name)
def test_nenhum_gatilho_executa_codigo_de_terceiro(caminho: Path) -> None:
    # pull_request_target e workflow_run rodam com os segredos do repositório a
    # partir de código que veio de fora. O repositório é público e aceita PR.
    texto = caminho.read_text(encoding="utf-8")
    for gatilho in ("pull_request_target:", "workflow_run:", "issue_comment:"):
        assert gatilho not in texto, f"{caminho.name} usa gatilho perigoso: {gatilho}"


@pytest.mark.parametrize("caminho", WORKFLOWS, ids=lambda p: p.name)
def test_texto_de_terceiro_nao_entra_em_shell_por_interpolacao(caminho: Path) -> None:
    """${{ }} dentro de run: é substituição textual antes do shell rodar."""
    texto = caminho.read_text(encoding="utf-8")
    dentro_de_run = False
    for linha in texto.split("\n"):
        despida = linha.strip()
        if despida.startswith("run:"):
            dentro_de_run = True
        elif despida.startswith("- name:") or despida.startswith("uses:") or despida.startswith("env:"):
            dentro_de_run = False
        if dentro_de_run and "${{" in linha:
            assert re.search(r"\$\{\{\s*(secrets|vars|github\.token|env)\.", linha), (
                f"{caminho.name}: interpolação em run: sem origem confiável -> {despida}")


def test_todo_hash_publicado_confere_com_o_que_o_clone_recebe() -> None:
    """Prova de procedência que só vale nesta máquina não é prova de nada.

    Vinte e seis hashes publicados foram calculados sobre bytes com CRLF de uma
    cópia de trabalho no Windows, enquanto o repositório entrega LF: quem
    clonasse e conferisse encontrava outro valor. O verificador compara sempre
    contra `git show HEAD:<arquivo>`, que é o que o clone recebe.
    """
    resultado = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verify_published_hashes.py")],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


# --- nada de segredo no que é publicado ------------------------------------

def test_o_diretorio_publicado_nao_carrega_credencial() -> None:
    padrao = re.compile(
        r"(re_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|"
        r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})")
    culpados = []
    for arquivo in WEB.rglob("*"):
        if not arquivo.is_file() or arquivo.suffix.lower() in {".pdf", ".png", ".jpg", ".woff2"}:
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        if padrao.search(texto):
            culpados.append(str(arquivo.relative_to(ROOT)))
    assert not culpados, f"credencial em arquivo publicado: {culpados}"


def test_a_chave_do_provedor_de_email_so_existe_no_ambiente() -> None:
    lead = (WEB / "api" / "demo-request.js").read_text(encoding="utf-8")
    assert "process.env.RESEND_API_KEY" in lead
    # A chave não pode chegar ao corpo de nenhuma resposta nem ao log.
    assert "RESEND_API_KEY}" not in lead.replace("${process.env.RESEND_API_KEY}", "")
    assert "console.error(\"Lead email delivery failed\", emailResponse.status)" in lead
