# Benevente

**Benevente Quant AI** é o framework acadêmico de pesquisa. **Benevente Wealth
System** é a solução B2B de apoio à decisão. Ambos compartilham o mesmo núcleo:
seleção determinística de valor e qualidade, alocação restrita, dados
ponto-no-tempo e uma trilha que permite revisar cada decisão.

O sistema não promete superar CDI, Ibovespa ou qualquer benchmark; não emite
recomendação autônoma e não transmite ordens. Seu objetivo é tornar uma tese de
carteira de médio/longo prazo reproduzível, verificável e revisável por uma
pessoa responsável.

## O que já é executável

- Backtest reproduzível B3/CDI, com custos e slippage modelados;
- Janelas históricas pré-especificadas de 5, 10 e 15 anos;
- Cálculo TTM com ITR/DFP oficial da CVM e corte por data de recebimento;
- Filtros que rejeitam ativos sem liquidez, qualidade ou dados de solvência
  comparáveis;
- Proposta para carteira-sombra: pesos, quantidades, lotes, custo, participação
  no volume, caixa residual e arquivos de auditoria;
- Conciliação posterior entre a proposta e a nota de corretagem.

## Instalação e teste

```powershell
python -m venv .venv-benevente
.\.venv-benevente\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest tests/test_pipeline.py tests/test_live_contracts.py -q
python main.py --offline
```

O modo `--offline` gera dados sintéticos determinísticos apenas para testar o
software. Ele não é evidência de retorno de mercado.

## Pesquisa histórica

```powershell
python research_runner.py --output artifacts/real_data
python validate_research.py --input artifacts/real_data
python horizon_evaluation.py --output artifacts/horizons
```

`research_runner.py` arquiva preços, dados macro, curvas, métricas e
comparativos com CDI, Ibovespa e MVO clássico. `validate_research.py` confere
datas, valores nulos e recomposição de patrimônio. Não escolha parâmetros depois
de observar uma janela: use `tune_hyperparameters.py` com uma separação temporal
explícita.

### Walk-forward anual: manter, revisar e justificar trocas

`annual_walk_forward.py` implementa o protocolo de revisão anual: em cada
primeiro pregão do ano, ele congela a política, os fundamentos disponíveis e os
pesos; mantém a carteira até a próxima revisão; e somente então calcula o
retorno realizado. `annual_transitions.csv` mostra cada entrada, saída ou ajuste
e seu motivo técnico. O retorno do ano avaliado nunca é usado para decidir a
carteira que o antecede.

```powershell
python annual_walk_forward.py --prices data/my_prices.csv --fundamentals data/my_fundamentals.csv --start-year 2012 --end-year 2026 --output artifacts/annual_walk_forward
```

Para a seleção adaptativa, o motor compara somente três hipóteses
pré-registradas — valor/qualidade, momentum de 12 meses e baixa volatilidade —
usando exclusivamente os anos já encerrados. Antes de cada ano novo, ele
congela o fator vencedor pelo critério retorno líquido, drawdown e giro;
depois avalia uma única vez o ano ainda desconhecido:

```powershell
python annual_walk_forward.py --prices data/my_prices.csv --fundamentals data/my_fundamentals.csv --start-year 2012 --end-year 2026 --adaptive-factors --output artifacts/annual_adaptive
```

Os arquivos `annual_results.csv`, `annual_transitions.csv`,
`annual_holdings.csv` e `adaptive_factor_choices.csv` são a evidência do
experimento. O processo não procura o maior retorno depois de observar o
futuro; isso seria sobreajuste, não uma estratégia utilizável.

Em especial, consulte `annual_holdings.csv` como a lâmina anual de decisão:
para cada ativo mantido ela contém peso anterior/novo, ação (entrada, manutenção,
aumento ou redução), score de valor/qualidade, sinal selecionado, retorno e
volatilidade de 12 meses **conhecidos no janeiro da decisão**, além do retorno
realizado separado ao fim daquele ano. `annual_benchmark_summary.csv` compara
o resultado anual com CDI e com MVO no mesmo universo elegível. Os pesos são
deixados derivar durante o ano antes de medir o giro da revisão seguinte.

### Regra de prontidão comercial

Uma estratégia só pode ser apresentada como candidata a alfa se, em um
holdout congelado e líquido de custos modelados, superar **CDI e MVO clássico**,
mantiver Sharpe excedente ao CDI positivo, drawdown dentro do limite e pelo
menos 24 períodos mensais. Caso contrário, a saída é obrigatoriamente
`research_only`: ela pode ser estudada, mas não é prova para uma alegação
comercial de retorno superior.

O portal aberto da CVM disponibiliza DFP desde 2010 e ITR desde 2011. Portanto,
um estudo "fundamentalista ponto-no-tempo" de 20 anos iniciado em 2006 exige
uma fonte adicional de fundamentos históricos e um universo de constituintes
datado; o sistema não preenche 2006–2010 com informação posterior. Consulte o
[Portal de Dados Abertos da CVM](https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/) para a disponibilidade dos arquivos.

## Comparação com fundo de gestão ativa

O comparador aceita qualquer **CNPJ de fundo ou classe** com cotas no Informe
Diário da CVM. Ele baixa apenas as linhas necessárias da fonte oficial, guarda as
URLs dos arquivos usados e alinha a cota do fundo à última publicação disponível
em cada data do modelo. Todas as curvas passam a começar em 100 na primeira data
comum, o que evita comparar períodos diferentes.

O valor inicial sugerido na interface é o **Dynamo Cougar FIF**, CNPJ
`73.232.530/0001-39`, por ser um fundo de ações de longo histórico; é somente
uma referência editável, não indicação de investimento. Fundos têm taxas,
tributação, resgate, público-alvo e mandatos próprios, portanto a comparação não
mede uma escolha investível equivalente.

```powershell
python research_runner.py --start 2021-07-01 --end 2026-07-01 --fund-cnpj 73.232.530/0001-39 --fund-name "Dynamo Cougar FIF" --output artifacts/dynamo_comparison
python validate_research.py --input artifacts/dynamo_comparison
```

## Interface local

Há quatro áreas numa interface única:

- **Sugestão de carteira:** coleta perfil, horizonte de 1/2/5/10/15 anos e
  limites; bloqueia ativos que não passam em liquidez, valor, qualidade ou
  solvência; produz pesos restritos, custo estimado e uma trilha de auditoria.
  O modo de demonstração é inteiramente sintético e só testa o fluxo. Para uma
  proposta rastreável, o usuário carrega histórico de preços e fundamentos
  ponto-no-tempo com fonte e data de disponibilidade.
- **Pesquisa e fundo ativo:** executa o backtest, mostra CDI/Ibovespa/MVO e, no
  modo real, o comparativo do fundo CVM escolhido;
- **Carteira-sombra:** cria a linha-base ou importa um CSV de NAV observado para
  acompanhar carteira, CDI, Ibovespa e, opcionalmente, a cota CVM de um fundo
  ativo escolhido, sem transmitir ordens.
- **Como funciona:** apresenta os controles, a separação entre modelo e futura
  camada de LLM, e a obrigatoriedade de revisão humana.

```powershell
.\launch_ui.ps1
```

Abra `http://localhost:8501`. A interface grava todos os resultados em
`artifacts/ui/` e mantém os modos separados. Cada sugestão salva política,
preços usados, tela de elegibilidade, pesos e resumo de métricas. Ela não substitui o fluxo de
proposta com ITR/DFP, que continua sendo o caminho para uma revisão de carteira
real com dados de mercado atribuídos.

Se o PowerShell bloquear a execução de scripts, execute uma única vez na janela
atual e repita o comando: `Set-ExecutionPolicy -Scope Process Bypass`. Como
alternativa sem política de PowerShell, dê duplo clique em `launch_ui.cmd`.

Na primeira inicialização de uma versão anterior do lançador, o Streamlit podia
exibir uma pergunta opcional de e-mail; pressione `Enter` vazio para seguir. A
configuração atual do projeto desativa essa pergunta.

## Experiência web para apresentação

A pasta `web/` contém a experiência web estática do **Benevente Wealth
System**, desenhada para demonstrações e para o case de estudo. Ela explica o
método e permite explorar, de forma claramente identificada, como perfil e
horizonte alteram os limites ilustrativos de uma proposta. Não consulta dados
de mercado, não executa o motor Python e não deve ser tratada como recomendação
ou proposta investível.

Depois de autenticar o Vercel CLI, publique-a a partir da pasta `web/`:

```powershell
npx.cmd vercel login
cd web
npx.cmd vercel --prod --yes
```

O motor auditável continua sendo a interface Streamlit e os comandos de
proposta descritos neste README. Uma futura API deverá ligar a experiência web
ao mesmo núcleo Python, preservando a trilha de dados e aprovação humana.

### Contato institucional do site

O site comercial tem um formulário de demonstração em `/api/demo-request`. A
rota só encaminha o lead depois que estas variáveis forem cadastradas na Vercel
para produção: `RESEND_API_KEY`, `BENEVENTE_FROM_EMAIL` e
`BENEVENTE_CONTACT_EMAIL`. Use `web/.env.example` apenas como referência e não
versione chaves. Sem as variáveis, a página informa de forma explícita que o
canal ainda não foi configurado; ela não guarda dados do visitante em arquivo
ou planilha local.

## Carteira-sombra real, sem ordem automática

Uma proposta operacional requer três insumos datados e atribuídos:

1. Política: copie `data/production_policy_template.json`, identifique o
   responsável e confirme o reconhecimento explícito.
2. Snapshot de mercado: copie `data/market_snapshot_template.csv` e preencha
   preço de fechamento, capitalização, liquidez, lote e fonte (B3, corretora ou
   fornecedor licenciado).
3. Histórico de preços: CSV de fonte identificada, com `date`, uma coluna para
   cada ticker `.SA` do snapshot e `TITULO_CDI`. Todas as linhas devem ser
   anteriores ou iguais à data de decisão. O histórico deve ter, no mínimo,
   253/505/757/1261 linhas para horizontes de 1/2/5/10–15 anos.

Para empresas não financeiras, ITR/DFP padronizado não fornece de forma segura
um EBITDA e cobertura de juros comparáveis. Se quiser que elas sejam elegíveis,
preencha também `data/quality_metrics_template.csv` com métricas verificadas e
fonte atribuída. Sem elas, o sistema rejeita o ativo em vez de inventar um dado.

```powershell
Copy-Item data/production_policy_template.json data/my_policy.json
Copy-Item data/market_snapshot_template.csv data/my_market.csv
Copy-Item data/quality_metrics_template.csv data/my_quality.csv
# preencher os CSVs e my_policy.json; o arquivo de preços é exportado da fonte escolhida
python production_readiness.py --policy data/my_policy.json --market-snapshot data/my_market.csv --price-history data/my_prices.csv
python live_proposal_runner.py --policy data/my_policy.json --itr-year 2026 --market-snapshot data/my_market.csv --price-history data/my_prices.csv --price-history-source "B3/corretora, exportação YYYY-MM-DD" --quality-metrics data/my_quality.csv --decision-date YYYY-MM-DD
```

O pacote em `artifacts/live_proposals/YYYY-MM-DD/` contém a política aplicada,
fundamentos CVM, histórico e snapshot arquivados, tela de elegibilidade, pesos,
`proposed_orders.csv`, resumo de caixa/custos e metadados. As instruções de
compra são arredondadas para o lote declarado e falham se excederem a
participação máxima de 5% do volume diário médio. A pessoa responsável revisa e
aprova cada linha antes de digitá-la manualmente na corretora.

Após receber a nota, copie `data/executions_template.csv`, preencha os dados
efetivos e concilie:

```powershell
python broker_note_reconciler.py --proposed-orders artifacts/live_proposals/YYYY-MM-DD/proposed_orders.csv --executions data/my_executions.csv --output artifacts/reconciliation.csv
```

Para o acompanhamento prospectivo de R$100 mil, preencha o NAV observado e
execute `pilot_tracker.py`. Acompanhamento prospectivo e backtest permanecem
separados.

## Limites importantes

- O LLM é opcional e só estrutura teses/riscos a partir de fatos aprovados;
  jamais define pontuações, limites, pesos ou envia ordens. Os sinais de
  alocação são determinísticos e versionados.
- Sharpe, retorno, CDI e comparações com fundos mostrados pelo sistema são
  medidas históricas e não meta, previsão ou garantia de superação.
- A cobertura atual é Brasil/B3. ETFs globais negociados na B3 só entram depois
  de módulo próprio de transparência e dados ponto-no-tempo.
- Custos Clear/B3 são estimativas versionadas e precisam ser confrontados com a
  nota de corretagem, inclusive em caso de alteração de tabela.
- Uso comercial, suitability, consultoria ou gestão exigem estrutura regulatória,
  contratual e controles adequados. Este repositório é pesquisa e apoio à
  decisão, não aconselhamento individual.

Consulte [a integração ITR](docs/itr_integration.md), a
[governança de produção](docs/production_governance.md) e o
[desenho de pesquisa](docs/value_quality_research_design.md).
