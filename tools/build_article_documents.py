"""Build the submission-ready Benevente manuscripts from the reviewed formats."""
from __future__ import annotations

from pathlib import Path
from shutil import copy2
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parents[1]
SOURCE_BTECH = Path(r"C:\Users\diego\Downloads\BTECH.docx")
OUTPUTS = ROOT / "outputs"
BTECH_OUTPUT = OUTPUTS / "Benevente_Wealth_System_BTECH.docx"
IEEE_SOURCE = ROOT / "paper" / "ieee_cifer_2027.tex"
IEEE_OUTPUT = OUTPUTS / "Benevente_Quant_AI_IEEE.tex"


def clear_body(document: Document) -> None:
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def add_paragraph(document: Document, text: str = "", style: str = "normal", *, bold_prefix: str | None = None) -> None:
    paragraph = document.add_paragraph(style=style)
    if bold_prefix and text.startswith(bold_prefix):
        paragraph.add_run(bold_prefix).bold = True
        paragraph.add_run(text[len(bold_prefix):])
    else:
        paragraph.add_run(text)
    paragraph.paragraph_format.space_after = document.styles["normal"].paragraph_format.space_after


def add_table(document: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    for cell, value in zip(table.rows[0].cells, headers):
        cell.text = value
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for values in rows:
        cells = table.add_row().cells
        for cell, value in zip(cells, values):
            cell.text = value


def build_btech() -> None:
    if SOURCE_BTECH.exists():
        copy2(SOURCE_BTECH, BTECH_OUTPUT)
    elif not BTECH_OUTPUT.exists():
        raise FileNotFoundError(f"BTECH template not found at {SOURCE_BTECH} or {BTECH_OUTPUT}")
    # The reviewed output preserves the original BTECH template when the
    # user-provided download is no longer available in this workspace.
    document = Document(BTECH_OUTPUT)
    clear_body(document)

    title = document.add_paragraph(style="Heading 1")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("Benevente Wealth System: Plataforma B2B de Apoio à Decisão para Carteiras de Médio e Longo Prazo")
    subtitle = document.add_paragraph(style="normal")
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("Manuscrito Tecnológico para o Business Tech Congress (Fucape Business School)")

    add_paragraph(document, "FICHA DE ENQUADRAMENTO DO PRODUTO TECNOLÓGICO", "Heading 2")
    add_paragraph(document, "Tipo de Produção Técnica (CAPES 2019): Produto Tecnológico - Software / Aplicativo e Processo ou Tecnologia Não Patenteável.")
    add_paragraph(document, "Trilha Temática: O Espírito Santo como Destino de Negócios.")
    add_paragraph(document, "Eixo Temático: Atração, Retenção e Reinvestimento de Capital.")
    add_paragraph(document, "Público-alvo: Multi-family offices, consultores e analistas devidamente habilitados, gestoras, bancos e plataformas de investimento que atuam no Espírito Santo e no Brasil.")
    add_paragraph(document, "Proposta prática: plataforma B2B de pesquisa, governança de dados e apoio à decisão para construção de carteiras B3/CDI de médio e longo prazo, sempre com aprovação humana.")

    add_paragraph(document, "RESUMO EXECUTIVO", "Heading 2")
    add_paragraph(document, "O Benevente Wealth System é uma solução B2B de apoio à decisão para instituições que precisam construir, documentar e acompanhar carteiras de ações brasileiras e renda fixa pós-fixada. A plataforma integra demonstrativos oficiais da CVM, dados macroeconômicos do Banco Central, filtros determinísticos de valor e qualidade, otimização de carteira com limites explícitos e uma camada opcional de linguagem natural para revisão de teses. O sistema não executa operações nem promete superar CDI ou Ibovespa. Seu diferencial é transformar uma decisão de carteira em um processo rastreável: cada dado possui data contábil e data de divulgação; cada proposta registra limites, custos estimados, fonte de mercado e aprovação humana; e cada execução pode ser conciliada posteriormente com a nota de corretagem. Os testes históricos reproduzíveis mostram evidência mista: a estratégia não superou o CDI na janela de cinco anos, mas superou o CDI nas janelas pré-especificadas de dez e quinze anos. Por isso, a etapa seguinte é um piloto prospectivo de R$100.000 em carteira-sombra, com monitoramento separado dos resultados históricos.")

    add_paragraph(document, "1. SITUAÇÃO-PROBLEMA E OPORTUNIDADE DE MERCADO", "Heading 2")
    add_paragraph(document, "1.1 Decisão de carteira sem trilha auditável", "Heading 3")
    add_paragraph(document, "Instituições de investimento e assessoria precisam combinar dados de mercado, demonstrações financeiras, custos e restrições de cada mandato. Em muitas operações, o racional da recomendação fica disperso entre planilhas, relatórios e mensagens, dificultando a verificação posterior do que era conhecido na data da decisão. O problema aumenta em horizontes de médio e longo prazo, nos quais disciplina de processo, concentração, liquidez, custos e atualização de fundamentos são mais relevantes do que reações pontuais a notícias.")
    add_paragraph(document, "1.2 Oportunidade para o ecossistema capixaba", "Heading 3")
    add_paragraph(document, "O Espírito Santo combina empresários, famílias patrimoniais, empresas exportadoras e intermediários financeiros que demandam serviços sofisticados de inteligência patrimonial. Uma solução B2B local pode apoiar a retenção de conhecimento financeiro e de relacionamentos de longo prazo no estado, sem substituir o dever fiduciário, a análise profissional ou a decisão do cliente. O valor econômico vem da padronização do processo e da redução de retrabalho, não de promessas de performance.")

    add_paragraph(document, "2. FUNDAMENTAÇÃO TEÓRICA E CONCEITUAL SUBJACENTE", "Heading 2")
    add_paragraph(document, "A plataforma parte da Teoria Moderna de Carteiras, que formaliza a relação entre retorno esperado, risco e diversificação, e de extensões que combinam visões qualitativas com regras quantitativas. Black e Litterman (1992) fundamentam a separação entre uma visão qualitativa e a alocação de equilíbrio; no Benevente, o modelo de linguagem pode estruturar uma tese e apontar riscos, mas não determina pesos. Os pesos são calculados por um otimizador convexo sujeito a limites de concentração, exposição a ações, liquidez, custos e reserva em CDI.")
    add_paragraph(document, "DeMiguel, Garlappi e Uppal (2009) alertam que erro de estimação pode anular o ganho teórico de otimização fora da amostra. Por isso, limites explícitos, uma referência simples e validação temporal congelada são controles de pesquisa, não ajustes para vencer retrospectivamente. Novy-Marx e Velikov (2016) reforçam que custos e turnover alteram materialmente o resultado líquido; o backtest reporta atritos modelados e o fluxo operacional concilia posteriormente a nota de corretagem.")
    add_paragraph(document, "A seleção de ativos é orientada por valor e qualidade. Para empresas não financeiras, a elegibilidade requer liquidez e capitalização mínimas, geração positiva de caixa, ROIC mínimo e filtros de endividamento e cobertura de juros. Para instituições financeiras, os critérios respeitam a taxonomia de seus demonstrativos, privilegiando ROE e preço sobre valor patrimonial. Ausência de dado comparável é motivo de reprovação, e não de inferência favorável.")

    add_paragraph(document, "3. DESCRIÇÃO DO PRODUTO TECNOLÓGICO", "Heading 2")
    add_paragraph(document, "3.1 Arquitetura e fontes", "Heading 3")
    add_paragraph(document, "A camada de dados usa séries de CDI, Selic e IPCA do Sistema Gerenciador de Séries Temporais do Banco Central. Para fundamentos correntes, utiliza o ITR trimestral e o DFP anual estruturados da CVM. O cálculo de métricas trailing-twelve-months segue a ponte: DFP anual anterior + ITR atual - ITR comparativo. A data de recebimento do documento limita sua disponibilidade; uma informação divulgada após a decisão não pode entrar na proposta.")
    add_paragraph(document, "3.2 Proposta de carteira", "Heading 3")
    add_paragraph(document, "O usuário institucional escolhe perfil de risco, horizonte de 1, 2, 5, 10 ou 15 anos, limites de renda variável, posição máxima, custo máximo de rebalanceamento, frequência de revisão, ativos excluídos e eventual exposição global via instrumentos negociados na B3. O sistema aplica padrões para perfis conservador, moderado, crescimento e agressivo, mas permite personalização avançada. Uma proposta só é emitida após a política ser explicitamente reconhecida e após a verificação de dados de mercado datados e atribuídos a B3, corretora ou fornecedor licenciado.")
    add_paragraph(document, "3.3 Controle operacional", "Heading 3")
    add_paragraph(document, "O Benevente Wealth System gera proposta e trilha de auditoria, não transmite ordens. Quando o usuário aprova uma proposta, a entrada da ordem ocorre manualmente na corretora. Preço, quantidade, custos estimados e custos realizados são conciliados a partir da nota de corretagem. Essa separação reduz risco operacional e mantém a responsabilidade decisória na instituição e no investidor.")

    add_paragraph(document, "4. PROPOSTA DE VALOR E MODELO DE MONETIZAÇÃO", "Heading 2")
    add_paragraph(document, "A plataforma entrega um núcleo de pesquisa e governança que pode ser incorporado aos processos de atendimento, comitê de investimentos e monitoramento de carteiras. O produto não depende de remuneração por distribuição de ativos e deve preservar a independência da análise. A estratégia comercial deve ser validada com pilotos B2B, contratos de licenciamento e métricas de adoção, evitando vincular faturamento a resultados de investimento.")
    add_table(document,
              ["Oferta", "Cliente", "Valor entregue", "Métrica de validação"],
              [["Research Workspace", "Consultorias e RIAs habilitados", "Triagem, propostas auditáveis e relatórios", "Tempo de análise e aderência ao processo"],
               ["Governance Suite", "Family offices e gestoras", "Políticas, comitê, carteira-sombra e conciliação", "Cobertura de auditoria e redução de retrabalho"],
               ["API de Pesquisa", "Fintechs e instituições", "Integração de telas, regras e relatórios", "Disponibilidade, rastreabilidade e uso mensal"]])

    add_paragraph(document, "5. VALIDAÇÃO EMPÍRICA E PILOTO PROSPECTIVO", "Heading 2")
    add_paragraph(document, "5.1 Evidência histórica reproduzível", "Heading 3")
    add_paragraph(document, "A avaliação arquivada utiliza preços ajustados de ações B3 e Ibovespa por meio de fonte secundária, além de CDI e variáveis macroeconômicas do Banco Central. As janelas de 5, 10 e 15 anos foram pré-especificadas, com um ano de dados anterior reservado para lookback. São deduzidos custos de transação e slippage modelados. Os resultados abaixo não constituem previsão nem prova de superioridade persistente.")
    add_table(document,
              ["Janela", "Estratégia", "Retorno acum.", "CAGR", "Volatilidade", "Máx. DD", "Leitura"],
              [["5 anos", "Benevente Quant AI", "69,87%", "11,38%", "8,69%", "-11,00%", "Não superou CDI (76,47%)"],
               ["10 anos", "Benevente Quant AI", "226,23%", "12,78%", "15,04%", "-29,59%", "Superou CDI (141,66%)"],
               ["15 anos", "Benevente Quant AI", "408,29%", "11,65%", "12,23%", "-18,93%", "Superou CDI (298,23%)"],
               ["15 anos", "MVO clássico", "413,78%", "11,73%", "12,24%", "-18,92%", "Levemente acima do Benevente"]])
    add_paragraph(document, "5.2 Protocolo prospectivo de R$100.000", "Heading 3")
    add_paragraph(document, "O piloto começa com uma carteira-sombra de R$100.000, perfil moderado e horizonte inicial de cinco anos. A linha de base registra R$100.000 para carteira, CDI e Ibovespa na data de início. A cada revisão, o sistema arquiva a política aplicável, ITR/DFP utilizado, snapshot de mercado, tela de elegibilidade, pesos propostos, custo estimado e NAV. Relatórios futuros devem separar resultados prospectivos dos testes históricos e informar retorno acumulado, drawdown, turnover, custos realizados e diferença para CDI e Ibovespa. Não há ordem automática nem promessa de retorno.")

    add_paragraph(document, "6. DESAFIOS DE IMPLEMENTAÇÃO, REGULAÇÃO E CONSIDERAÇÕES FINAIS", "Heading 2")
    add_paragraph(document, "6.1 Enquadramento regulatório", "Heading 3")
    add_paragraph(document, "A personalização de recomendações sobre valores mobiliários e a gestão de recursos são atividades submetidas a regras específicas da CVM. Sistemas automatizados não eliminam as responsabilidades do consultor ou gestor. Enquanto a estrutura regulatória, contratual e de controles não estiver estabelecida, o Benevente Wealth System deve operar como ferramenta B2B de pesquisa e apoio à decisão, com aprovação humana, documentação de riscos e sem execução autônoma.")
    add_paragraph(document, "6.2 Limitações e evolução", "Heading 3")
    add_paragraph(document, "O histórico atual possui universo fixo de ações e, portanto, risco de viés de sobrevivência. Os preços vêm de fonte secundária e os custos históricos são modelados. A próxima etapa científica é construir um painel histórico ponto-no-tempo de fundamentos da CVM para testar os filtros de valor e qualidade sem alterar regras após observar os resultados. A próxima etapa comercial é validar o fluxo B2B com usuários, segurança, governança de modelos e integração documental.")
    add_paragraph(document, "6.3 Considerações finais", "Heading 3")
    add_paragraph(document, "O Benevente Wealth System propõe uma infraestrutura verificável para decisões de investimento de médio e longo prazo: dados oficiais datados, regras determinísticas, otimização com restrições, explicação estruturada e trilha de auditoria. A plataforma pode fortalecer a capacidade analítica de instituições locais e nacionais, desde que seu uso preserve adequação ao perfil, responsabilidade profissional e transparência sobre incerteza e risco.")

    add_paragraph(document, "REFERÊNCIAS BIBLIOGRÁFICAS", "Heading 2")
    for reference in [
        "BANCO CENTRAL DO BRASIL. Sistema Gerenciador de Séries Temporais (SGS): séries CDI, Selic e IPCA. Disponível em: https://www.bcb.gov.br/estatisticas/sgs.",
        "COMISSÃO DE VALORES MOBILIÁRIOS. Formulário de Informações Trimestrais (ITR): dados abertos. Disponível em: https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/.",
        "COMISSÃO DE VALORES MOBILIÁRIOS. Resolução CVM n. 19, de 25 de fevereiro de 2021. Disponível em: https://conteudo.cvm.gov.br/legislacao/resolucoes/resol019.html.",
        "MARKOWITZ, H. Portfolio Selection. The Journal of Finance, v. 7, n. 1, p. 77-91, 1952.",
        "BLACK, F.; LITTERMAN, R. Global Portfolio Optimization. Financial Analysts Journal, v. 48, n. 5, p. 28-43, 1992. DOI: 10.2469/faj.v48.n5.28.",
        "DEMIGUEL, V.; GARLAPPI, L.; UPPAL, R. Optimal versus naive diversification: how inefficient is the 1/N portfolio strategy? The Review of Financial Studies, v. 22, n. 5, p. 1915-1953, 2009. DOI: 10.1093/rfs/hhm075.",
        "NOVY-MARX, R.; VELIKOV, M. A taxonomy of anomalies and their trading costs. The Review of Financial Studies, v. 29, n. 1, p. 104-147, 2016. DOI: 10.1093/rfs/hhv063.",
        "BENEVENTE WEALTH SYSTEM. Documentação técnica, repositório de dados e validação de horizontes. Repositório do projeto, 2026.",
    ]:
        add_paragraph(document, reference)

    for paragraph in document.paragraphs:
        if paragraph.text == "5. VALIDAÇÃO EMPÍRICA E PILOTO PROSPECTIVO":
            # The evaluation table is a single evidence unit; keeping its
            # heading and all rows together is more readable than a split row.
            paragraph.paragraph_format.page_break_before = True
        if paragraph.text == "REFERÊNCIAS BIBLIOGRÁFICAS":
            # Section 6 deliberately leaves enough room for the compact source
            # list; avoid creating an almost empty page before the references.
            paragraph.paragraph_format.page_break_before = False

    document.core_properties.author = ""
    document.core_properties.last_modified_by = ""
    document.core_properties.title = "Benevente Wealth System"
    document.save(BTECH_OUTPUT)


def build_ieee() -> None:
    text = IEEE_SOURCE.read_text(encoding="utf-8")
    if "\\documentclass[10pt,conference]{IEEEtran}" not in text:
        raise ValueError("IEEE manuscript is not using the conference template")
    IEEE_OUTPUT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    OUTPUTS.mkdir(exist_ok=True)
    build_btech()
    build_ieee()
    print(BTECH_OUTPUT)
    print(IEEE_OUTPUT)
