"""Benevente Wealth System — local, human-reviewed decision-support UI."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from advisor import build_proposal, demo_snapshots, snapshots_from_frame, write_audit_bundle
from config import SystemConfig
from data_loader import PointInTimeDataLoader
from fund_comparator import CvmFundDailyClient, format_cnpj
from pilot_tracker import build_performance
from production_policy import PROFILE_DEFAULTS, ProductionPolicy
from research_runner import evaluate
from universes import load_universe_snapshot
from validate_research import validate


ROOT = Path(__file__).resolve().parent
UI_ARTIFACTS = ROOT / "artifacts" / "ui"
DEFAULT_FUND_CNPJ = "73.232.530/0001-39"
DEFAULT_FUND_NAME = "Dynamo Cougar FIF (referência de gestão ativa)"


def artifact_folder(kind: str) -> Path:
    path = UI_ARTIFACTS / kind / pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path.mkdir(parents=True, exist_ok=True)
    return path


def percent(value: float) -> str:
    return f"{value:.1%}" if pd.notna(value) else "—"


def inject_style() -> None:
    st.markdown("""<style>
    :root { --navy:#102a43; --ink:#1c2b39; --muted:#5e7184; --teal:#0f766e; --paper:#ffffff; --line:#dce5ed; --bg:#f5f8fb; }
    .stApp { background:var(--bg); color:var(--ink); }
    [data-testid="stSidebar"] { background:var(--navy); }
    [data-testid="stSidebar"] * { color:#edf6fc !important; }
    [data-testid="stSidebar"] .stRadio label { padding: .35rem 0; }
    .block-container { max-width: 1180px; padding-top: 2.25rem; padding-bottom: 4rem; }
    h1 { font-size:2.55rem !important; letter-spacing:-.055em; color:var(--navy) !important; margin-bottom:.15rem !important; }
    h2 { color:var(--navy) !important; letter-spacing:-.025em; margin-top:1.25rem !important; }
    h3 { color:var(--navy) !important; }
    p, li { color:var(--ink); }
    .hero { background:linear-gradient(115deg,#102a43 0%,#174e63 100%); color:#fff; padding:2.1rem 2.25rem; border-radius:18px; margin:.65rem 0 1.5rem; box-shadow:0 12px 30px rgba(16,42,67,.16); }
    .hero h2,.hero p { color:#fff !important; margin:0; } .hero h2 { font-size:1.65rem; margin-bottom:.45rem; }
    .eyebrow { color:#8ce3d4 !important; font-size:.76rem; font-weight:700; letter-spacing:.12em; text-transform:uppercase; margin-bottom:.4rem !important; }
    .badge { display:inline-block; background:#e5f7f3; color:#0b635e; border-radius:999px; padding:.22rem .65rem; font-size:.77rem; font-weight:650; margin:.2rem .3rem .2rem 0; }
    .soft-card { background:var(--paper); border:1px solid var(--line); border-radius:14px; padding:1.15rem 1.25rem; min-height:122px; box-shadow:0 3px 10px rgba(32,65,88,.035); }
    .soft-card h3 { font-size:1rem; margin:.1rem 0 .38rem; } .soft-card p { color:var(--muted); font-size:.9rem; margin:0; }
    div[data-testid="stForm"] { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1.35rem 1.5rem .6rem; }
    [data-testid="stMetric"] { background:#fff; border:1px solid var(--line); border-radius:12px; padding:.85rem 1rem; }
    [data-testid="stMetricLabel"] { color:var(--muted); font-size:.83rem; } [data-testid="stMetricValue"] { color:var(--navy); }
    .stButton>button { border-radius:9px; font-weight:650; min-height:2.7rem; } .stButton>button[kind="primary"] { background:var(--teal); border-color:var(--teal); }
    [data-testid="stAlert"] { border-radius:10px; }
    .note { color:var(--muted); font-size:.88rem; }
    </style>""", unsafe_allow_html=True)


def hero(eyebrow: str, title: str, copy: str) -> None:
    st.markdown(f"<section class='hero'><p class='eyebrow'>{eyebrow}</p><h2>{title}</h2><p>{copy}</p></section>", unsafe_allow_html=True)


def policy_from_form(value: float, profile: str, horizon: int, owner: str, acknowledged: bool,
                     equity: float | None, issuer: float | None, drawdown: float | None, review: int | None) -> ProductionPolicy:
    defaults = PROFILE_DEFAULTS.get(profile, {})
    return ProductionPolicy(
        policy_id=f"ui-proposal-{pd.Timestamp.now():%Y%m%d%H%M%S}", owner=owner, effective_date=date.today(),
        portfolio_value_brl=value, risk_profile=profile, horizon_years=horizon,
        maximum_equity_weight=equity if equity is not None else defaults.get("maximum_equity_weight"),
        maximum_asset_weight=issuer if issuer is not None else defaults.get("maximum_asset_weight"),
        maximum_drawdown_tolerance=drawdown if drawdown is not None else defaults.get("maximum_drawdown_tolerance"),
        review_interval_months=review if review is not None else defaults.get("review_interval_months"),
        maximum_rebalance_cost_brl=max(50.0, value * .005), acknowledged_not_investment_advice=acknowledged,
    )


def render_home() -> None:
    hero("Benevente Wealth System", "Uma decisão de carteira que você consegue explicar.",
         "Transforme perfil, horizonte e dados rastreáveis em uma proposta revisável — sem promessas, sem execução automática.")
    left, middle, right = st.columns(3)
    with left:
        st.markdown("<div class='soft-card'><h3>1. Construa</h3><p>Defina objetivo e tolerância a risco. Comece com uma demonstração em menos de três minutos.</p></div>", unsafe_allow_html=True)
    with middle:
        st.markdown("<div class='soft-card'><h3>2. Valide</h3><p>Teste a estratégia contra CDI, Ibovespa e, se desejar, um fundo ativo com cota CVM.</p></div>", unsafe_allow_html=True)
    with right:
        st.markdown("<div class='soft-card'><h3>3. Acompanhe</h3><p>Registre uma carteira-sombra. Cada resultado fica separado e rastreável.</p></div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    start, learn = st.columns([1, 2])
    with start:
        if st.button("Começar uma proposta", type="primary", width="stretch"):
            st.session_state["page"] = "Construir carteira"
            st.rerun()
    with learn:
        st.markdown("<p class='note'><b>O que está operante:</b> filtros de valor/qualidade, limites, custos e auditoria. A futura camada LLM será apenas explicativa: nunca altera pesos ou envia ordens.</p>", unsafe_allow_html=True)
    st.subheader("Princípios de confiança")
    st.markdown("<span class='badge'>Dados ponto-no-tempo</span><span class='badge'>Revisão humana obrigatória</span><span class='badge'>Custos Clear/B3 modelados</span><span class='badge'>Trilha de auditoria</span>", unsafe_allow_html=True)


def render_builder() -> None:
    hero("Construa", "Vamos montar uma proposta de médio ou longo prazo.",
         "Primeiro você define os limites. Depois o Benevente aplica os filtros e calcula pesos-alvo sujeitos à sua aprovação.")
    with st.form("portfolio_builder", border=False):
        st.subheader("1. Seu objetivo")
        a, b, c = st.columns(3)
        value = a.number_input("Patrimônio para análise (R$)", min_value=1_000.0, value=100_000.0, step=1_000.0, format="%.0f")
        profile = b.selectbox("Como você lida com oscilações?", ["conservative", "moderate", "growth", "aggressive", "custom"], index=1,
                              format_func=lambda x: {"conservative":"Conservador", "moderate":"Equilibrado", "growth":"Crescimento", "aggressive":"Arrojado", "custom":"Personalizado"}[x])
        horizon = c.selectbox("Quando este dinheiro pode ser usado?", [1, 2, 5, 10, 15], index=2, format_func=lambda x: f"Em {x} ano(s)")
        owner = st.text_input("Responsável pela revisão", value="Responsável da carteira", help="Aparece na política arquivada com esta proposta.")
        equity = issuer = drawdown = review = None
        if profile == "custom":
            st.caption("Personalize limites somente se eles já foram definidos na política do cliente.")
            d, e, f, g = st.columns(4)
            equity = d.slider("Máx. em renda variável", .10, .80, .60, .05)
            issuer = e.slider("Máx. por emissor", .05, min(.15, equity), min(.12, equity), .01)
            drawdown = f.slider("Queda tolerada", .05, .50, .30, .05)
            review = g.selectbox("Revisar a cada", [1, 3, 6, 12], index=2, format_func=lambda x: f"{x} meses")

        st.subheader("2. Dados para a decisão")
        mode = st.radio("Como deseja começar?", ["Demonstração guiada", "Meus dados auditáveis"], horizontal=True,
                        help="A demonstração usa dados sintéticos e não deve orientar investimentos.")
        prices_upload = fundamentals_upload = universe_upload = None
        decision_date = date.today()
        if mode == "Demonstração guiada":
            st.info("Você verá o produto funcionando com uma amostra sintética. Os resultados serão marcados como demonstração.")
        else:
            st.caption("Use este modo apenas com dados atribuídos e disponíveis na data de decisão.")
            d1, d2 = st.columns([1, 2])
            decision_date = d1.date_input("Data de decisão", value=date.today())
            d2.markdown("<p class='note'>Necessários: <b>histórico de preços</b> com <code>date</code>, tickers e <code>TITULO_CDI</code>; e <b>fundamentos</b> com data de disponibilidade e fonte.</p>", unsafe_allow_html=True)
            prices_upload = st.file_uploader("Histórico de preços (.csv)", type=["csv"])
            fundamentals_upload = st.file_uploader("Fundamentos ponto-no-tempo (.csv)", type=["csv"])
            universe_upload = st.file_uploader(
                "Universo B3 datado (.csv, opcional)", type=["csv"],
                help="Inclua ações, ETFs, BDRs, FIIs e renda fixa com classe, fonte e data. O sistema registra a cobertura; somente ações com fundamentos e preços completos podem entrar nesta versão do otimizador.",
            )
        acknowledged = st.checkbox("Entendo que a proposta é apoio à decisão, exige revisão humana e não é recomendação individual.")
        submitted = st.form_submit_button("Gerar proposta para revisão", type="primary", width="stretch")

    if submitted:
        if not acknowledged:
            st.error("Para continuar, confirme que a proposta precisa de revisão humana.")
            return
        try:
            policy = policy_from_form(value, profile, horizon, owner, acknowledged, equity, issuer, drawdown, review)
            if mode == "Demonstração guiada":
                decision = pd.Timestamp.today().normalize()
                prices = PointInTimeDataLoader(SystemConfig()).fetch_prices(str((decision - pd.DateOffset(years=6)).date()),
                                                                           str((decision + pd.Timedelta(days=1)).date()), offline=True)
                snapshots, data_mode = demo_snapshots(decision), "synthetic_demo"
            else:
                if prices_upload is None or fundamentals_upload is None:
                    raise ValueError("Envie o histórico de preços e os fundamentos antes de gerar a proposta.")
                decision = pd.Timestamp(decision_date)
                prices = pd.read_csv(prices_upload)
                snapshots = snapshots_from_frame(pd.read_csv(fundamentals_upload, parse_dates=["as_of_date", "available_date"]))
                if universe_upload is not None:
                    universe = load_universe_snapshot(pd.read_csv(universe_upload), decision)
                    snapshot_tickers = {item.ticker for item in snapshots}
                    unknown = snapshot_tickers - set(universe.ticker)
                    if unknown:
                        raise ValueError(f"Fundamentos contêm ativos fora do universo datado: {sorted(unknown)}")
                data_mode = "user_supplied_point_in_time"
            proposal, metrics = build_proposal(policy, decision, prices, snapshots)
            output = artifact_folder("portfolio_proposal")
            write_audit_bundle(output, policy, proposal, metrics, prices.set_index("date") if "date" in prices else prices, data_mode)
            st.session_state["proposal_output"] = str(output)
        except Exception as exc:
            st.error(f"Não foi possível gerar a proposta: {exc}")
    render_proposal_result()


def render_proposal_result() -> None:
    output_text = st.session_state.get("proposal_output")
    if not output_text:
        return
    output = Path(output_text)
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    metrics = summary["metrics"]
    screen = pd.read_csv(output / "eligibility_screen.csv")
    weights = pd.read_csv(output / "target_weights.csv").set_index("ticker")
    eligible = int(screen["eligible"].sum())
    st.divider()
    st.subheader("Proposta pronta para revisão")
    st.success(f"{eligible} ativo(s) passaram pelos filtros. Nenhuma ordem foi enviada.")
    a, b, c, d = st.columns(4)
    a.metric("Renda variável", percent(metrics["equity_weight"]))
    b.metric("Sharpe da amostra", f"{metrics['model_historical_sharpe']:.2f}")
    c.metric("Retorno anual na amostra", percent(metrics["model_historical_annual_return"]))
    d.metric("CDI na mesma amostra", percent(metrics["cdi_historical_annual_return"]))
    st.caption("As métricas descrevem somente a janela histórica usada pelo modelo; não são previsão, meta ou garantia de retorno.")
    left, right = st.columns([1.05, .95])
    with left:
        st.markdown("#### Alocação-alvo")
        st.bar_chart(weights, height=260)
    with right:
        st.markdown("#### Leitura rápida")
        cdi_weight = float(weights.loc["TITULO_CDI", "weight"]) if "TITULO_CDI" in weights.index else 0
        st.markdown(f"- **{percent(cdi_weight)}** permanece no componente CDI defensivo.\n- A concentração respeita a política escolhida.\n- Custo estimado para implementar: **R$ {metrics['estimated_rebalance_cost_brl']:,.2f}**.\n- Próximo passo: revisar os ativos elegíveis e, se aprovada, acompanhar em carteira-sombra.")
    with st.expander("Ver pesos e filtros usados"):
        st.dataframe(weights.style.format({"weight": "{:.2%}"}), width="stretch")
        columns = [c for c in ["ticker", "sector", "eligible", "value_quality_score", "rejection_reasons", "source"] if c in screen]
        st.dataframe(screen[columns], width="stretch", hide_index=True)
    memo = pd.read_csv(output / "candidate_memo.csv")
    st.markdown("#### Lâmina de decisão: ativos, motivo e próximo controle")
    st.caption("Elegibilidade é uma condição técnica para revisão. Não é uma recomendação individual nem uma ordem de compra.")
    show = st.multiselect("Mostrar linhas da lâmina", memo["ticker"].tolist(), default=memo.loc[memo.target_weight.gt(0), "ticker"].tolist(), key="memo_tickers")
    if show:
        st.dataframe(memo.loc[memo.ticker.isin(show)].style.format({"target_weight": "{:.2%}"}), width="stretch", hide_index=True)
    st.caption(f"Trilha de auditoria salva em: {output}")


def render_research() -> None:
    hero("Valide", "Teste a tese antes de confiar nela.", "Compare o método com CDI, Ibovespa e uma referência de gestão ativa. O comparativo é histórico e reproduzível.")
    with st.form("research_form", border=False):
        a, b, c = st.columns(3)
        window = a.selectbox("Janela de avaliação", ["Personalizada", "1 ano", "2 anos", "5 anos", "10 anos", "15 anos"], index=3)
        end = b.date_input("Fim da janela (exclusivo)", value=date(2026, 7, 1))
        if window == "Personalizada":
            start = c.date_input("Início da janela", value=date(2021, 7, 1))
        else:
            years = int(window.split()[0])
            start = (pd.Timestamp(end) - pd.DateOffset(years=years)).date()
            c.metric("Início calculado", start.strftime("%d/%m/%Y"))
        data_mode = st.radio("Fonte", ["Demonstração determinística", "Dados reais + fundo CVM"], horizontal=True)
        fund_cnpj = st.text_input("CNPJ do fundo/classe CVM", value=DEFAULT_FUND_CNPJ, disabled=data_mode.startswith("Demonstração"))
        fund_name = st.text_input("Nome da referência", value=DEFAULT_FUND_NAME, disabled=data_mode.startswith("Demonstração"))
        run = st.form_submit_button("Executar pesquisa", type="primary")
    if run:
        try:
            output = artifact_folder("research")
            with st.spinner("Reproduzindo a pesquisa e registrando os artefatos..."):
                evaluate(SystemConfig(), str(start), str(end), output, data_mode.startswith("Demonstração"),
                         None if data_mode.startswith("Demonstração") else fund_cnpj,
                         None if data_mode.startswith("Demonstração") else fund_name)
                st.session_state["research_validation"] = validate(output)
            st.session_state["research_output"] = str(output)
        except Exception as exc:
            st.error(f"A pesquisa não foi concluída: {exc}")
    output_text = st.session_state.get("research_output")
    if output_text:
        output = Path(output_text)
        st.success("Pesquisa concluída e validada.")
        st.dataframe(pd.read_csv(output / "performance_metrics.csv"), width="stretch", hide_index=True)
        curves = pd.read_csv(output / "equity_curves.csv", parse_dates=["date"])
        chart_curves = curves.set_index("date")
        if (output / "active_fund_comparison_metrics.csv").exists():
            st.subheader("Referência de fundo ativo na mesma janela")
            st.dataframe(pd.read_csv(output / "active_fund_comparison_metrics.csv"), width="stretch", hide_index=True)
            chart_curves = pd.read_csv(output / "active_fund_comparison_curves.csv", parse_dates=["date"]).set_index("date")
            st.caption("As curvas foram normalizadas em 100 na primeira data comum. A cota é a publicação oficial da CVM disponível em ou antes de cada data de comparação.")
        selected = st.multiselect("Linhas visíveis no gráfico", chart_curves.columns.tolist(), default=chart_curves.columns.tolist(), key="research_lines")
        if selected:
            st.line_chart(chart_curves[selected], height=360)
        else:
            st.info("Selecione ao menos uma série para exibir o gráfico.")
        st.caption("A janela é recalculada a cada execução. Para dados reais, o relatório arquiva fontes, custos modelados e os arquivos de entrada; um fundo não é benchmark oficial nem recomendação.")
        st.caption(f"Validação: {st.session_state['research_validation']['assessment']} · Artefatos: {output}")


def render_tracking() -> None:
    hero("Acompanhe", "Registre o que realmente aconteceu.", "A carteira-sombra é separada da pesquisa histórica e não transmite nenhuma ordem à corretora.")
    with st.form("tracking_form", border=False):
        a, b, c = st.columns(3)
        initial = a.number_input("Valor inicial (R$)", min_value=1_000.0, value=100_000.0, step=1_000.0, format="%.0f")
        profile = b.selectbox("Perfil registrado", ["conservative", "moderate", "growth", "aggressive"], index=1)
        horizon = c.selectbox("Horizonte", [1, 2, 5, 10, 15], index=2, format_func=lambda x: f"{x} ano(s)")
        effective = st.date_input("Data de início", value=date.today())
        nav_upload = st.file_uploader("Atualização de valores (.csv, opcional)", type=["csv"], help="date, portfolio_value_brl, cdi_value_brl, ibovespa_value_brl, notes")
        run = st.form_submit_button("Criar ou atualizar acompanhamento", type="primary")
    if run:
        try:
            policy = ProductionPolicy(policy_id=f"ui-shadow-{pd.Timestamp(effective):%Y%m%d}", owner="Usuário UI", effective_date=effective,
                                      portfolio_value_brl=initial, risk_profile=profile, horizon_years=horizon,
                                      maximum_rebalance_cost_brl=max(50.0, initial * .005))
            nav = pd.DataFrame([{"date": str(effective), "portfolio_value_brl": initial, "cdi_value_brl": initial, "ibovespa_value_brl": initial,
                                 "notes": "Linha de base criada pelo Benevente; nenhuma ordem enviada."}]) if nav_upload is None else pd.read_csv(nav_upload)
            performance, summary = build_performance(policy, nav)
            output = artifact_folder("shadow_portfolio")
            (output / "policy.json").write_text(policy.model_dump_json(indent=2), encoding="utf-8")
            performance.to_csv(output / "pilot_performance.csv", index=False)
            (output / "pilot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            st.session_state["pilot_output"] = str(output)
        except Exception as exc:
            st.error(f"O acompanhamento foi bloqueado: {exc}")
    output_text = st.session_state.get("pilot_output")
    if output_text:
        output = Path(output_text)
        summary = json.loads((output / "pilot_summary.json").read_text(encoding="utf-8"))
        a, b, c, d = st.columns(4)
        a.metric("Carteira", f"R$ {summary['latest_value_brl']:,.2f}", percent(summary["portfolio_return"]))
        b.metric("CDI", percent(summary["cdi_return"]))
        c.metric("Ibovespa", percent(summary["ibovespa_return"]))
        d.metric("Maior queda", percent(summary["maximum_drawdown"]))
        frame = pd.read_csv(output / "pilot_performance.csv", parse_dates=["date"])
        st.line_chart(frame.set_index("date")[["portfolio_value_brl", "cdi_value_brl", "ibovespa_value_brl"]], height=330)


def render_method() -> None:
    hero("Método", "Uma IA só é útil se for governável.", "O Benevente separa o que é regra, o que é evidência histórica e o que requer julgamento humano.")
    a, b = st.columns(2)
    with a:
        st.markdown("### O que o modelo faz\n- Rejeita dados sem origem, liquidez ou qualidade suficiente.\n- Respeita limites de concentração e risco.\n- Calcula pesos e custos de forma reproduzível.\n- Arquiva os insumos e resultados de cada execução.")
    with b:
        st.markdown("### O que o modelo não faz\n- Não promete bater CDI, Ibovespa ou fundos.\n- Não envia ordens nem substitui suitability.\n- Não usa uma LLM para burlar filtros ou definir pesos.\n- Não transforma demonstração sintética em evidência empírica.")
    st.subheader("Para o case IEEE 2027")
    st.markdown("A apresentação deve separar: (1) hipótese e desenho pré-especificado, (2) backtests por janelas, (3) custos e fontes, (4) avaliação prospectiva da carteira-sombra e (5) limitações. A interface registra os artefatos necessários para essa rastreabilidade.")


def main() -> None:
    st.set_page_config(page_title="Benevente", page_icon="◇", layout="wide", initial_sidebar_state="expanded")
    inject_style()
    pages = ["Visão geral", "Construir carteira", "Validar estratégia", "Acompanhar carteira", "Método e governança"]
    if "page" not in st.session_state:
        st.session_state["page"] = pages[0]
    with st.sidebar:
        st.markdown("## Benevente")
        st.caption("Wealth System")
        page = st.radio("Navegação", pages, key="page")
        st.divider()
        st.caption("Benevente Quant AI\nPesquisa acadêmica e reproduzível")
        st.caption("v0.2 · revisão humana obrigatória")
    if page == "Visão geral": render_home()
    elif page == "Construir carteira": render_builder()
    elif page == "Validar estratégia": render_research()
    elif page == "Acompanhar carteira": render_tracking()
    else: render_method()
    st.divider()
    st.caption("Ferramenta de pesquisa e apoio à decisão. Não é recomendação individual, promessa de retorno ou execução automática.")


if __name__ == "__main__":
    main()
