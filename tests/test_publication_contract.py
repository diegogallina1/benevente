import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_has_canonical_stage_and_five_core_blocks() -> None:
    home = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "Carregando" not in home
    # A faixa de topo saiu a pedido de revisão: um selo fixo martela menos que um
    # banner. A alegação de estágio continua obrigatória — no rodapé.
    assert "stage-ribbon" not in home and "PROTÓTIPO DE PESQUISA" not in home
    assert "Protótipo de pesquisa" in home
    # Quantos perfis a home declara vem da política, e não de um número escrito
    # aqui. A frase dizia "três" enquanto a escada já tinha quatro, e um teste
    # que repetisse o número teria confirmado a frase errada.
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from politica import escada
    quantos = {3: "três", 4: "quatro", 5: "cinco"}[len(escada())]
    assert f"A política vigente declara {quantos} perfis" in home
    assert "diagnóstico retrospectivo, não validação prospectiva" in home
    assert "Reproduzir no GitHub" not in home
    # A separação continua sendo a tese, mas deixou de ser a primeira frase: a
    # home abre pelo problema do leitor. O contrato exige que ela esteja
    # declarada, não que esteja numa redação específica.
    assert all(papel in home for papel in ("CALCULA", "EXPLICA", "DECIDE"))
    assert "Revisor humano responsável" in home
    # E que a home roteie por jornada, não pelas versões internas do motor.
    assert "Entenda a pesquisa" in home and "Veja o produto de governança" in home
    assert "Benevente 1</strong>" not in home and "Benevente 2</strong>" not in home
    # A home enxugou de seis blocos para três mais o público. O passo a passo
    # do "como decide" e o dossiê ano a ano saíram porque já existiam, melhor
    # servidos, no método e nas páginas de versão — repetir os dois na entrada
    # era o que fazia o leitor frio se perder.
    for core_class in ("hero shell", "version-gateway shell", "comparison shell"):
        assert core_class in home
    for moved in ("model-shell", "lab-section", 'id="carteira"'):
        assert moved not in home, f"{moved} voltou para a home"
    assert "Feito para quem assina a recomendação" in home
    for moved_class in ("research-signal shell", "evidence-board shell", "research-disclosure shell"):
        assert moved_class not in home
    assert "hero-performance" in home
    assert "Benevente 2, Ibovespa e CDI" not in home  # comparison is visual, not repeated as prose
    # The home must be meaningful before JavaScript runs, so the ladder's own
    # figures are the static fallback. They used to be the retired rule's.
    assert all(label in home for label in ("+259,6%", "+382,9%", "+629,1%", "+167,6%"))
    assert "543,8%" not in home and "509,8%" not in home
    # O estúdio que trocava de versão na home saiu junto com o dossiê: cada
    # página de versão já traz o seu próprio histórico de decisões, e manter um
    # seletor de versão na entrada era pedir ao leitor frio que escolhesse entre
    # módulos internos antes de saber o que o produto faz.
    assert "data-dossier-strategy" not in home
    unified = (ROOT / "web" / "versoes.html").read_text(encoding="utf-8")
    for mode in ("b1", "b2"):
        assert f'data-strategy-decisions="{mode}"' in unified, mode


def test_benevente_2_has_direct_benchmarks_and_shared_design_system() -> None:
    pages = [ROOT / "web" / name for name in (
        "index.html", "versoes.html", "metodo.html", "para-escritorios.html", "quant-ai.html"
    )]
    for path in pages:
        source = path.read_text(encoding="utf-8")
        # A família tem de ser a que o CSS pede, e não qualquer uma. O site
        # carregava Plus Jakarta Sans e pedia outra coisa em var(--sans): as
        # duas nunca se encontraram e a página inteira caía na fonte do
        # sistema. Um teste que aceitasse só "carrega alguma fonte" deixaria
        # esse defeito passar de novo.
        assert "family=Figtree" in source, path
        assert "DM+Mono" not in source, path
        assert "design-system.css" in source, path
    # The two version pages were consolidated into one tab; the old URLs stay as
    # redirects so external links keep landing somewhere sensible.
    unified = (ROOT / "web" / "versoes.html").read_text(encoding="utf-8")
    for name in ("benevente-1.html", "benevente-2.html"):
        redirect = (ROOT / "web" / name).read_text(encoding="utf-8")
        assert "versoes.html" in redirect and "http-equiv=\"refresh\"" in redirect, name
    assert (ROOT / "web" / "btech.html").read_text(encoding="utf-8").count("para-escritorios.html") >= 1
    # O site de produto publica só a política que está em uso. As duas escadas
    # lado a lado eram duas tabelas quase iguais, e quem chega para contratar
    # não precisa escolher entre elas: só uma existe. As duas continuam juntas
    # nos manuscritos, que é onde comparar módulo com módulo faz sentido.
    assert 'data-ladder="benevente2"' in unified
    assert 'data-ladder="benevente1"' not in unified
    assert "data-ladder-seal" in unified
    assert 'data-version-metric="b1-cagr"' not in unified
    assert 'data-version-metric="b2-cagr"' not in unified
    # The 2026 shadow book was decided under the previous policy and says so.
    assert "política anterior" in unified


def test_site_data_contract_matches_canonical_sources() -> None:
    contract = json.loads((ROOT / "web" / "data_contract.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "web" / "research_manifest.json").read_text(encoding="utf-8"))
    universe = json.loads((ROOT / "web" / "b3_universe.json").read_text(encoding="utf-8"))
    protocol_path = ROOT / "artifacts" / "published_nested" / "protocol.json"

    assert contract["research_window"]["annual_decisions"] == manifest["evaluation"]["annual_decisions"]
    assert contract["historical_panel"]["evaluated_distinct_issuers"] == manifest["coverage"]["evaluated_distinct_issuers"]
    assert contract["historical_panel"]["price_series"] == manifest["coverage"]["price_tickers"]
    assert contract["historical_panel"]["fundamental_records"] == manifest["coverage"]["fundamental_records"]
    assert contract["current_b3_catalog"]["instruments"] == universe["instrument_count"]
    assert contract["current_b3_catalog"]["observed_at"] == universe["observed_at"]
    assert contract["corporate_events"]["primary_records_within_observed_spans"] == manifest["coverage"]["primary_event_records"]
    assert contract["corporate_events"]["current_endpoint_queried_series"] == manifest["coverage"]["primary_event_tickers_endpoint_queried"]
    assert contract["corporate_events"]["historically_reconciled_series"] == manifest["coverage"]["primary_event_tickers_historically_reconciled"]
    assert contract["corporate_events"]["material_return_differences_over_5pp"] == manifest["primary_reconciliation"]["material_differences_over_5pp"]
    assert contract["prospective_protocol"]["sha256"] == __import__("hashlib").sha256(protocol_path.read_bytes()).hexdigest()
    versions = json.loads((ROOT / "web" / "protocol_versions.json").read_text(encoding="utf-8"))
    assert [item["name"] for item in versions["versions"]] == [
        "Benevente 1", "Benevente 2", "Acompanhamento diário 1.0.0"
    ]


def test_site_uses_honest_language_model_and_cadence_claims() -> None:
    home = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    method = (ROOT / "web" / "metodo.html").read_text(encoding="utf-8")
    quant = (ROOT / "web" / "quant-ai.html").read_text(encoding="utf-8")
    combined = home + method
    assert "teste de sensibilidade, não prova de descontaminação" in combined
    assert "Não há evidência de contaminação temporal" not in method
    assert "teste de sensibilidade, não prova de descontaminação" in method
    assert "does not reject a benefit in other periods" in quant


def test_public_site_text_is_utf8_and_has_no_placeholder_metrics() -> None:
    text_extensions = {".html", ".js", ".css", ".json"}
    for path in (ROOT / "web").rglob("*"):
        if path.suffix.lower() not in text_extensions:
            continue
        source = path.read_text(encoding="utf-8")
        assert "\ufffd" not in source, path
        if path.suffix.lower() in {".html", ".js"}:
            assert "NaN%" not in source, path
            assert "A recalcular" not in source, path


def test_browser_bundle_has_one_hash_and_honest_approval_state_per_decision() -> None:
    bundle = json.loads((ROOT / "web" / "annual_research.json").read_text(encoding="utf-8"))
    assert len(bundle["annual"]) == 11
    for decision in bundle["annual"]:
        assert re.fullmatch(r"[0-9a-f]{64}", decision["decision_evidence_sha256"])
        assert "não houve aprovação humana" in decision["approval_status"]


def test_release_manifest_distinguishes_labels_from_evaluated_issuers() -> None:
    manifest = json.loads((ROOT / "web" / "research_manifest.json").read_text(encoding="utf-8"))
    assert manifest["coverage"]["evaluated_distinct_issuers"] == 514
    assert manifest["coverage"]["historical_issuer_labels"] == 2051
    assert "historical_issuers" not in manifest["coverage"]


def test_papers_share_the_language_model_boundary() -> None:
    btech = (ROOT / "paper" / "fucape_btech_2026.md").read_text(encoding="utf-8")
    ieee = (ROOT / "paper" / "ieee_cifer_2027.tex").read_text(encoding="utf-8")
    for name in ("Perlin", "Pelster", "Kim", "FINSABER"):
        assert name in btech
    assert "o modelo apenas explica fatos aprovados" in btech
    assert "There is no edge from $e_t$ to $S$, $A$ or $P$" in ieee
    assert "github.com/diegogallina1" not in ieee
    assert "benevente-wealth-system.vercel.app" not in ieee


def test_ieee_supplement_is_anonymous_and_self_manifested() -> None:
    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "build_ieee_anonymous_supplement.py")],
        cwd=ROOT,
        check=True,
    )
    archive_path = ROOT / "outputs" / "Benevente_Quant_AI_IEEE_Anonymous_Supplement.zip"
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        assert "README.md" in names
        assert "MANIFEST.sha256" in names
        assert "artifacts/published_nested/protocol.json" in names
        readable = "\n".join(
            archive.read(name).decode("utf-8", errors="ignore")
            for name in names
            if name.endswith((".md", ".json", ".py"))
        ).lower()
    assert "diegogallina" not in readable
    assert "github.com/" not in readable
    assert "benevente-wealth-system.vercel.app" not in readable


def test_o_app_pede_so_fontes_que_ele_carrega() -> None:
    """O app tinha a própria folha de estilo e a própria fonte inventada.

    O site já era testado assim, porque uma vez pediu uma família e carregou
    outra, e as duas nunca se encontraram: a página inteira caiu na fonte do
    sistema sem nada quebrar. O app repetiu o defeito com Schibsted Grotesk e
    sobreviveu meses, inclusive com o rodapé afirmando a tipografia errada.

    O teste não fixa qual é a família. Ele exige que toda família nomeada na
    folha de estilo esteja entre as que a página manda o navegador buscar.
    """
    for nome in ("app.html", ):
        fonte = (ROOT / "web" / nome).read_text(encoding="utf-8")
        carregadas = set(re.findall(r"family=([A-Za-z0-9+]+)", fonte))
        carregadas = {f.replace("+", " ") for f in carregadas}
        assert carregadas, nome
        pedidas = set()
        for pilha in re.findall(r"font-family:\s*([^;}]+)", fonte):
            pedidas.update(re.findall(r'"([^"]+)"', pilha))
        orfas = sorted(pedidas - carregadas)
        assert not orfas, (
            f"{nome} pede {orfas} e carrega {sorted(carregadas)}: a família que "
            f"ninguém busca cai calada na fonte do sistema")
        # E o rodapé não pode nomear uma tipografia diferente da que a página usa.
        declarada = re.search(r"Tipografia ([^<]+)\.", fonte)
        assert declarada, nome
        for familia in re.split(r"\s+e\s+", declarada.group(1)):
            assert familia.strip() in carregadas, (familia, sorted(carregadas))


def test_sem_trava_a_pagina_tem_de_se_declarar_prototipo_sintetico() -> None:
    """O que torna a trava desligável é a carteira não ser de ninguém.

    A trava nunca foi segurança: a comparação roda no navegador e qualquer
    pessoa que abra o código passa. Ela mantinha o visitante casual fora de uma
    tela inacabada. Desligada, o que resta impedindo um mal-entendido é a página
    dizer o que é, e isso passa a ser obrigação verificada e não hábito.

    Se um dia a trava voltar, este teste não atrapalha: ele só exige o que a
    página já deveria dizer de qualquer jeito.
    """
    import sys
    sys.path.insert(0, str(ROOT / "tools"))
    from build_mapa_prototype import TRAVA_LIGADA

    pagina = (ROOT / "web" / "app.html").read_text(encoding="utf-8")
    script = (ROOT / "web" / "plano.js").read_text(encoding="utf-8")

    assert 'name="robots" content="noindex, nofollow"' in pagina
    assert "protótipo" in pagina.lower()
    assert "sintética" in pagina.lower()
    assert "Nenhuma ordem é transmitida" in pagina

    if TRAVA_LIGADA:
        assert 'id="senha"' in pagina and 'id="entrar"' in pagina
        assert "__SHA__" not in script and "sha256" in script.lower()
    else:
        # Campo de senha sem o código que o lê é pior que os dois estados: parece
        # quebrado e convida alguém a digitar uma senha num campo inerte.
        assert 'id="senha"' not in pagina and 'id="entrar"' not in pagina
        assert "Senha de acesso" not in pagina


def test_a_trava_desligada_nao_leva_dado_real_junto() -> None:
    """Sem trava, a única defesa é o dado ser sintético. Então ele tem de ser."""
    import json
    import re

    fonte = (ROOT / "web" / "plano.js").read_text(encoding="utf-8")
    dados = json.JSONDecoder().raw_decode(fonte[fonte.index("{", fonte.index("DADOS")):])[0]
    bruto = json.dumps(dados, ensure_ascii=False)
    # CPF, e-mail e telefone não têm o que fazer num payload sintético, e se
    # aparecerem é porque alguém apontou a tela para dado de gente.
    assert not re.search(r"\d{3}\.\d{3}\.\d{3}-\d{2}", bruto), "CPF no payload"
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", bruto), "e-mail no payload"
    # E a tela não pode estar carregando credencial nenhuma junto do payload.
    assert dados["b3"]["consent"]["credencial_armazenada"] is False
