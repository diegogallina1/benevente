"""Local, human-review-only UI for Benevente Quant AI and Wealth System."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json

import pandas as pd
import streamlit as st

from pilot_tracker import build_performance
from config import SystemConfig
from fund_comparator import CvmFundDailyClient, format_cnpj
from production_policy import ProductionPolicy
from research_runner import evaluate
from validate_research import validate


ROOT = Path(__file__).resolve().parent
UI_ARTIFACTS = ROOT / "artifacts" / "ui"
DEFAULT_FUND_CNPJ = "73.232.530/0001-39"
DEFAULT_FUND_NAME = "Dynamo Cougar FIF (comparação de gestão ativa)"


def artifact_folder(kind: str) -> Path:
    stamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    path = UI_ARTIFACTS / kind / stamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def percent(value: float) -> str:
    return f"{value:.2%}" if pd.notna(value) else "—"


def render_research() -> None:
    st.header("Pesquisa e comparação")
    st.write("Execute um backtest reproduzível e, no modo real, compare-o com a cota de um fundo de gestão ativa registrada na CVM.")
    with st.form("research_form"):
        first, second = st.columns(2)
        start = first.date_input("Início", value=date(2021, 7, 1))
        end = second.date_input("Fim exclusivo", value=date(2026, 7, 1))
        data_mode = st.radio("Dados", ["Teste determinístico (offline)", "Dados reais + comparação CVM"], horizontal=True)
        fund_cnpj = st.text_input("CNPJ do fundo/classe CVM", value=DEFAULT_FUND_CNPJ,
                                  disabled=data_mode.startswith("Teste"))
        fund_name = st.text_input("Nome exibido", value=DEFAULT_FUND_NAME,
                                  disabled=data_mode.startswith("Teste"))
        submitted = st.form_submit_button("Executar pesquisa", type="primary")

    if submitted:
        output = artifact_folder("research")
        try:
            with st.spinner("Calculando e arquivando os artefatos..."):
                evaluate(
                    config=SystemConfig(), start=str(start), end=str(end), output=output,
                    offline=data_mode.startswith("Teste"),
                    active_fund_cnpj=None if data_mode.startswith("Teste") else fund_cnpj,
                    active_fund_name=None if data_mode.startswith("Teste") else fund_name,
                )
                validation = validate(output)
            st.session_state["research_output"] = str(output)
            st.session_state["research_validation"] = validation
            st.success(f"Pesquisa concluída: {output.relative_to(ROOT)}")
        except Exception as exc:
            st.error(f"A pesquisa não foi concluída: {exc}")

    output_text = st.session_state.get("research_output")
    if output_text:
        output = Path(output_text)
        metrics = pd.read_csv(output / "performance_metrics.csv")
        st.subheader("Métricas do backtest")
        st.dataframe(metrics, use_container_width=True, hide_index=True)
        curves = pd.read_csv(output / "equity_curves.csv", parse_dates=["date"])
        st.line_chart(curves.set_index("date"), height=320)
        fund_metrics = output / "active_fund_comparison_metrics.csv"
        if fund_metrics.exists():
            st.subheader("Janela comum com o fundo ativo")
            st.caption("Todas as curvas abaixo começam em 100 na primeira data com cota CVM disponível para o fundo escolhido.")
            st.dataframe(pd.read_csv(fund_metrics), use_container_width=True, hide_index=True)
            fund_curves = pd.read_csv(output / "active_fund_comparison_curves.csv", parse_dates=["date"])
            st.line_chart(fund_curves.set_index("date"), height=320)
            metadata = json.loads((output / "active_fund_comparison_metadata.json").read_text(encoding="utf-8"))
            st.caption(f"CNPJ {metadata['fund_cnpj']} | {metadata['comparison_start']} a {metadata['comparison_end']} | "
                       f"{metadata['observations']} observações.")
        st.caption(f"Validação: {st.session_state['research_validation']['assessment']}. Arquivos completos: {output}")

    with st.expander("Como interpretar a comparação com fundo ativo"):
        st.write("A comparação usa a cota diária oficial informada à CVM e alinha cada ponto à última cota disponível até a data de decisão do modelo. Ela não elimina diferenças de mandato, taxa, tributação, prazo de resgate ou público-alvo. Um fundo é referência de gestão ativa, não uma recomendação de investimento.")


def render_shadow_portfolio() -> None:
    st.header("Carteira-sombra")
    st.write("Crie e acompanhe um piloto sem enviar ordens. Este modo registra a evolução observada contra CDI e Ibovespa.")
    with st.form("pilot_form"):
        first, second, third = st.columns(3)
        initial_value = first.number_input("Valor inicial (R$)", min_value=1_000.0, value=100_000.0, step=1_000.0)
        risk_profile = second.selectbox("Perfil", ["conservative", "moderate", "growth", "aggressive"])
        horizon = third.selectbox("Horizonte", [1, 2, 5, 10, 15], index=2)
        effective_date = st.date_input("Data de início", value=date.today())
        compare_active_fund = st.checkbox("Acompanhar também um fundo ativo CVM", value=True)
        fund_cnpj = st.text_input("CNPJ do fundo/classe para acompanhamento", value=DEFAULT_FUND_CNPJ,
                                  disabled=not compare_active_fund)
        fund_name = st.text_input("Nome do fundo acompanhado", value=DEFAULT_FUND_NAME,
                                  disabled=not compare_active_fund)
        nav_upload = st.file_uploader("Atualização de NAV (CSV opcional)", type=["csv"],
                                      help="Colunas: date, portfolio_value_brl, cdi_value_brl, ibovespa_value_brl, notes.")
        submitted = st.form_submit_button("Criar ou atualizar carteira-sombra", type="primary")

    if submitted:
        output = artifact_folder("shadow_portfolio")
        policy = ProductionPolicy(
            policy_id=f"ui-shadow-{pd.Timestamp(effective_date).strftime('%Y%m%d')}", owner="Usuário UI",
            effective_date=effective_date, portfolio_value_brl=initial_value, risk_profile=risk_profile,
            horizon_years=horizon, maximum_rebalance_cost_brl=max(50.0, initial_value * 0.005),
        )
        if nav_upload is None:
            nav = pd.DataFrame([{
                "date": str(effective_date), "portfolio_value_brl": initial_value,
                "cdi_value_brl": initial_value, "ibovespa_value_brl": initial_value,
                "notes": "Linha de base criada pela interface; nenhuma ordem enviada.",
            }])
        else:
            nav = pd.read_csv(nav_upload)
        try:
            fund_metadata = None
            if compare_active_fund:
                nav_dates = pd.to_datetime(nav["date"])
                quotes = CvmFundDailyClient().quotes(fund_cnpj, nav_dates.min(), nav_dates.max())
                aligned = quotes.quotes.reindex(nav_dates, method="ffill")
                if aligned.isna().any():
                    raise ValueError("O fundo não possui cota CVM disponível em ou antes de todas as datas de NAV.")
                nav["active_fund_value_brl"] = initial_value * aligned.to_numpy() / aligned.iloc[0]
                fund_metadata = {
                    "fund_cnpj": format_cnpj(fund_cnpj), "fund_name": fund_name,
                    "source_urls": list(quotes.source_urls),
                    "alignment": "Latest CVM quote on or before each NAV date.",
                }
            performance, summary = build_performance(policy, nav)
            (output / "policy.json").write_text(policy.model_dump_json(indent=2), encoding="utf-8")
            nav.to_csv(output / "nav_input.csv", index=False)
            performance.to_csv(output / "pilot_performance.csv", index=False)
            (output / "pilot_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            if fund_metadata:
                (output / "active_fund_tracking_metadata.json").write_text(
                    json.dumps(fund_metadata, indent=2), encoding="utf-8"
                )
            st.session_state["pilot_output"] = str(output)
            st.success(f"Carteira-sombra atualizada: {output.relative_to(ROOT)}")
        except Exception as exc:
            st.error(f"A atualização foi bloqueada: {exc}")

    output_text = st.session_state.get("pilot_output")
    if output_text:
        output = Path(output_text)
        summary = json.loads((output / "pilot_summary.json").read_text(encoding="utf-8"))
        first, second, third, fourth = st.columns(4)
        first.metric("Carteira", f"R$ {summary['latest_value_brl']:,.2f}", percent(summary["portfolio_return"]))
        second.metric("CDI", percent(summary["cdi_return"]))
        third.metric("Ibovespa", percent(summary["ibovespa_return"]))
        fourth.metric("Máx. drawdown", percent(summary["maximum_drawdown"]))
        frame = pd.read_csv(output / "pilot_performance.csv", parse_dates=["date"])
        tracking_columns = ["portfolio_value_brl", "cdi_value_brl", "ibovespa_value_brl"]
        if "active_fund_value_brl" in frame.columns:
            tracking_columns.append("active_fund_value_brl")
            st.metric("Fundo ativo", percent(summary["active_fund_return"]))
        st.line_chart(frame.set_index("date")[tracking_columns], height=320)
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.caption("Carteira-sombra: esta interface não envia, roteia ou aprova operações na corretora.")


def main() -> None:
    st.set_page_config(page_title="Benevente", page_icon="◆", layout="wide")
    st.markdown("""<style>
    .stApp { background: #f8fafc; } h1, h2, h3 { color: #102a43; }
    [data-testid='stMetricValue'] { color: #0f766e; }
    </style>""", unsafe_allow_html=True)
    st.title("Benevente")
    st.caption("Benevente Quant AI — pesquisa reproduzível | Benevente Wealth System — carteira-sombra e governança")
    research, shadow = st.tabs(["Pesquisa e fundo ativo", "Carteira-sombra"])
    with research:
        render_research()
    with shadow:
        render_shadow_portfolio()
    st.divider()
    st.caption("Ferramenta de pesquisa e apoio à decisão. Não é recomendação individual, garantia de retorno ou execução automática.")


if __name__ == "__main__":
    main()
