# Benevente

**Benevente Quant AI** é o framework acadêmico de pesquisa. **Benevente Wealth
System** é a camada B2B de governança e explicação dessa pesquisa. O núcleo
publicado é uma seleção multifatorial anual, orientada por fundamentos: qualidade,
valor e momento ordenam o universo elegível; uma busca aninhada escolhe, usando
somente anos já encerrados, a configuração de fatores, número de posições e
parcela em ações; o CDI recebe o saldo.

O MVO não é o Benevente. Ele é um comparador quantitativo independente e um
alocador experimental. O modelo de linguagem também não escolhe ativos nem
pesos: transforma fatos já aprovados em tese, riscos e perguntas para revisão.

O sistema não promete superar CDI, Ibovespa ou qualquer benchmark; não emite
recomendação autônoma e não transmite ordens. Seu objetivo é tornar uma tese de
carteira de médio/longo prazo reproduzível, verificável e revisável por uma
pessoa responsável.

## Estado da evidência

**Toda a série 2015–2025 é amostra de desenvolvimento, não validação
prospectiva.** A busca aninhada avaliou 36 configurações. Em cada janeiro, a
configuração foi ranqueada pelo Sharpe do excesso sobre CDI nos anos anteriores;
o ano seguinte só foi usado depois para avaliação. Mesmo assim, fatores, grade e
restrições foram desenvolvidos com essa janela. Nenhum recálculo histórico desfaz
isso; só anos posteriores ao registro congelado testam a regra prospectivamente.

Números honestos do período, contra referências independentes, estão em
`artifacts/audit_evidence/`. A verificação estatística das 73 tentativas está em
`artifacts/inference_audit/`. O registro congelado está em
`artifacts/preregistration/`.

## Pacote final de artigos

- BTech 2026: fonte em `paper/fucape_btech_2026.md` e versões finais em
  `outputs/Benevente_Wealth_System_BTECH_Final.docx` e `.pdf`;
- IEEE SSCI/CIFEr 2027: fonte em `paper/ieee_cifer_2027.tex` e versões finais em
  `outputs/Benevente_Quant_AI_IEEE_Final.tex` e `.pdf`;
- fonte única dos números em `artifacts/paper_release/paper_evidence.json`;
- manifesto SHA-256 em `artifacts/paper_release/paper_release_manifest.json`;
- conferência editorial e tarefas dos autores em
  `docs/paper_submission_checklist.md`.

Regenere o pacote numérico com `python tools/build_paper_release.py` e os
arquivos editáveis com `python tools/build_article_documents.py`. Os dois textos
separam a estratégia canônica Benevente 1 da extensão experimental Benevente 2.

## O que já é executável

- Backtest reproduzível B3/CDI, com custos por liquidez e imposto de renda
  modelados;
- Painel de preços **sem viés de sobrevivência**: o universo de registro é o
  COTAHIST da B3, que mantém empresas deslistadas;
- Comparação contra CDI, um MVO neutro independente, o Ibovespa e o **BOVA11**,
  sempre na mesma janela;
- Janelas históricas pré-especificadas de 5, 10 e 15 anos;
- Cálculo TTM com ITR/DFP oficial da CVM, período acumulado e corte por data de
  recebimento;
- Filtros que rejeitam ativos sem liquidez, qualidade ou solvência comparável,
  com alavancagem e cobertura de juros derivadas das contas padronizadas;
- Proposta para carteira-sombra: pesos, quantidades, lotes, custo, participação
  no volume, caixa residual e arquivos de auditoria;
- Conciliação posterior entre a proposta e a nota de corretagem;
- Correção por múltiplas tentativas: Sharpe deflacionado e probabilidade de
  sobreajuste de backtest.

## Correções de metodologia (auditoria de 2026-08-15)

Sete defeitos foram encontrados e corrigidos. Cada um alterava os números na
direção de fazer a estratégia parecer melhor do que era.

| Defeito | Efeito | Correção |
| --- | --- | --- |
| Benchmark MVO idêntico à estratégia em 11/11 anos | O gráfico comparava a curva com ela mesma | `unconstrained_long_only_mvo` constrói o comparador do universo elegível, sem compartilhar nenhuma etapa com a regra candidata |
| 139 de 497 emissores sem preço; 77 somem até 2020 | Viés de sobrevivência: CIEL3, AZUL4, BRML3, ALLL3 e BIDI4 desapareciam da amostra | `build_b3_total_return_panel.py` reconstrói o painel a partir do COTAHIST, com ações corporativas detectadas e auditadas |
| Deslistagem virava retorno zero, e `dropna()` truncava o ano inteiro | Perda de empresa que sai da bolsa não era contabilizada | `realised_returns_with_delisting` liquida no último preço observável e leva o caixa para o CDI |
| `debt_to_ebitda` e `interest_coverage` sempre nulos | 433 empresas não-financeiras reprovadas por falta de dado, não por qualidade; a carteira virava uma cesta de bancos | EBITDA, dívida líquida e cobertura derivados das contas padronizadas da CVM |
| Ponte TTM lia a linha trimestral ou a acumulada conforme a ordem do arquivo | Fundamentos errados a partir do 2º trimestre | `_accumulated_only` mantém só o período acumulado |
| Custo fixo de 15 bps, sem IR | Subestimava o custo de papéis ilíquidos e ignorava 15% sobre ganho realizado | Custo B3 por participação no volume e `BrazilianTaxModel` |
| `(1 + r @ w).prod()` | Rebalanceamento diário gratuito, impossível de executar | Buy and hold real dentro do ano |
| Ibovespa rotulado como "índice de preço" | A ressalva era falsa e favorecia a estratégia | O Ibovespa é índice de retorno total da B3; o BOVA11 entrou como referência investível |

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

## Reproduzir o resultado corrigido

Esta é a sequência que gera os números publicados. Cada etapa escreve manifesto
com SHA-256 dos arquivos que consumiu.

```powershell
# 1. Painel de preços sem viés de sobrevivência (COTAHIST + provedor)
python build_b3_total_return_panel.py
python build_b3_total_return_panel.py --no-imputation --output data/prices_b3_price_return_full_2013_2025.csv --manifest data/prices_b3_price_return_full_2013_2025_manifest.json --coverage-report artifacts/b3_price_return_full_coverage.csv --actions-report artifacts/b3_corporate_action_adjustments_bound.csv --detector-report artifacts/b3_split_detector_validation_bound.csv

# 2. Referências de mercado (Ibovespa e BOVA11)
python build_market_benchmarks.py

# 3. Fundamentos CVM com solvência derivada
python build_full_b3_cvm_fundamentals.py --universe data/b3_historical_universes.csv --mapping data/b3_historical_cvm_ticker_map.csv --start-year 2013 --end-year 2025 --output data/fundamentals_b3_cvm_full_2013_2025_v2.csv --coverage-report artifacts/fundamentals_b3_cvm_full_coverage_v2.csv

# 4. Walk-forward anual, um perfil por vez
python run_nested_configuration_search.py
python build_release_manifest.py
python build_release_manifest.py --verify

# 5. Placar honesto e verificação estatística
python build_audit_evidence.py --results artifacts/v2_mvo_moderado/annual_results.csv --output artifacts/audit_evidence
python audit_signal_grid_inference.py
python preregistration.py
```

O painel `--no-imputation` é o limite conservador: para os emissores que nenhum
provedor ainda serve, ele conta apenas retorno de preço, sem proventos. Rodar as
duas versões dá a banda de incerteza da imputação.

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

Para uma rota gratuita e reproduzível de pesquisa, use o
[painel Yahoo Finance ajustado + CDI BCB](docs/yahoo_total_return_research.md).
Ele é classificado como pesquisa até a reconciliação dos eventos corporativos
com registros B3/CVM ou um provedor licenciado.

### Estratégia multifatorial publicada

O núcleo combina qualidade primária (ROIC ou ROE), *earnings yield* e momento de
12 meses, sempre com informação conhecida no janeiro da decisão. Ausência de
uma métrica secundária de dívida não exclui, por si só, uma empresa; liquidez,
lucro positivo e qualidade continuam obrigatórios. As 36 configurações variam
a combinação fatorial, a quantidade de posições e a parcela em ações. Em cada
ano, apenas o histórico anterior pode escolher a configuração.

```powershell
python run_nested_configuration_search.py
```

Os perfis conservador, equilibrado e arrojado pertencem à política de uso do
Wealth System. Eles não geram três históricos publicados artificialmente. O
histórico canônico é uma única regra de pesquisa; qualquer adaptação por perfil
deve ser pré-registrada e avaliada separadamente antes de receber uma alegação de
desempenho.

Em especial, consulte `annual_holdings.csv` como a lâmina anual de decisão:
para cada ativo mantido ela contém peso anterior/novo, ação (entrada, manutenção,
aumento ou redução), score de valor/qualidade, sinal selecionado, retorno e
volatilidade de 12 meses **conhecidos no janeiro da decisão**, além do retorno
realizado separado ao fim daquele ano. `annual_benchmark_summary.csv` compara
o resultado anual com CDI e com MVO no mesmo universo elegível. Os pesos são
deixados derivar durante o ano antes de medir o giro da revisão seguinte.

### Regra de prontidão comercial

Uma estratégia só pode ser apresentada como candidata a alfa se, em um
holdout congelado e líquido de custos modelados, superar **CDI e o MVO de
referência**, mantiver Sharpe excedente ao CDI positivo, drawdown dentro do
limite e pelo menos 24 períodos mensais. Caso contrário, a saída é
obrigatoriamente `research_only`.

`build_audit_evidence.py` aplica essa regra e escreve o veredito. Hoje ele
retorna `research_only`, e o motivo não é o retorno: a janela 2015–2025 foi
usada para escolher regra, família de fatores e restrições, logo não existe
holdout congelado. Esse status só muda com anos avaliados **depois** do
registro em `artifacts/preregistration/`.

O que o período mostra, com referências independentes e após custos:

| Referência | CAGR da carteira | CAGR da referência | Anos vencidos |
| --- | --- | --- | --- |
| CDI | 17,86% | 9,61% | 6 de 11 |
| MVO de referência | 17,86% | 7,83% | 10 de 11 |
| Ibovespa | 17,86% | 11,77% | 7 de 11 |
| BOVA11 (investível) | 17,86% | 11,72% | 7 de 11 |
| CDI após IR | 16,03% | 7,94% | 6 de 11 |

Na amostra, a carteira supera as quatro referências no CAGR. Isso não autoriza
uma promessa: a queda máxima diária foi de 47,8%, a janela foi usada no
desenvolvimento e há somente onze observações anuais. O resultado após imposto
é uma simulação tributária, não uma declaração individual.

### Benevente 1 e Benevente 2

**Benevente 1** é a série canônica publicada: escolhe a cesta uma vez por ano e
mantém os ativos até a revisão seguinte. **Benevente 2** é uma extensão
experimental que preserva a mesma cesta, mas reduz temporariamente a exposição
a ações quando a queda e a volatilidade do Ibovespa, observadas até o fechamento
anterior, entram em estado de alerta ou severo. A LLM não participa desse teste.

Em 2015--2025, o Benevente 2 elevou o CAGR de 17,86% para 18,45% e reduziu a
queda máxima diária de 47,8% para 28,7%. No recorte temporal de 2019--2025, a
diferença de retorno foi pequena, 18,03% contra 17,95%, e não significativa
(p = 0,964). Portanto, a evidência é de redução de risco de cauda, não de alfa
adicional. O experimento cobra custo de giro, ainda não cobra o imposto gerado
pelas vendas dentro do ano e foi concebido depois da Covid-19. Ele permanece
retrospectivo e não substitui a série publicada.

```powershell
python benevente2_event_risk.py
```

Os parâmetros, a divisão temporal, a grade de 432 sensibilidades e os arquivos
de saída estão documentados em
[Benevente 1 versus Benevente 2](docs/benevente_1_vs_2_protocol.md) e
[resultados do experimento](docs/benevente_2_experiment_results.md).

O portal aberto da CVM disponibiliza DFP desde 2010 e ITR desde 2011. Portanto,
um estudo fundamentalista de 20 anos iniciado em 2006 exige uma fonte adicional
de fundamentos históricos e um universo de constituintes datado; o sistema não
preenche 2006–2010 com informação posterior. Consulte o
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
  datados, com fonte e data de disponibilidade.
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

### Deploy: o teste de segurança vem antes e depois, sempre

`predeploy_security_check.py` é o portão. Ele sai com código diferente de zero
quando algo regride, então **encadeie com `&&` em vez de rodar solto** — assim o
deploy não acontece se a verificação falhar.

```powershell
python predeploy_security_check.py; if ($?) { cd web; npx.cmd vercel --prod --yes; cd .. }
```

E confirme no ambiente publicado, porque o que vale é o cabeçalho que chega ao
navegador, não o que está no arquivo de configuração:

```powershell
python predeploy_security_check.py --live-only --url https://benevente-wealth-system.vercel.app
```

O modo estático confere que nenhuma variável de servidor é alcançável pelo
cliente, que nenhum `.env` real está versionado, que cada função tem limite de
taxa e checagem de origem, que os seis cabeçalhos estão configurados, e sinaliza
interpolação em `innerHTML` sem escape. O modo publicado confirma que os
cabeçalhos chegam, que origem externa recebe 403, que método errado recebe 405 e
que ticker malformado recebe 400.

Avisos não bloqueiam: a heurística de `innerHTML` erra para o lado do ruído de
propósito. Falhas bloqueiam.

Na primeira vez, autentique o CLI:

```powershell
npx.cmd vercel login
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
python live_proposal_runner.py --policy data/my_policy.json --itr-year 2026 --market-snapshot data/my_market.csv --issuer-map data/my_live_issuer_map.csv --price-history data/my_prices.csv --price-history-source "B3/corretora, exportação YYYY-MM-DD" --quality-metrics data/my_quality.csv --decision-date YYYY-MM-DD
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

Antes de acompanhar uma proposta real ou em simulador, ative a
[carteira-sombra com aprovação humana](docs/shadow_portfolio_protocol.md). O
manifesto guarda hashes da política e das ordens, responsável, valor inicial e,
se aplicável, CNPJ do fundo ativo de comparação. A ativação não envia ordens.

## Limites importantes

- O LLM é opcional e só estrutura teses/riscos a partir de fatos aprovados;
  jamais define pontuações, limites, pesos ou envia ordens. Os sinais de
  alocação são determinísticos e versionados.
- Sharpe, retorno, CDI e comparações com fundos mostrados pelo sistema são
  medidas históricas e não meta, previsão ou garantia de superação. O Sharpe
  histórico da regra publicada não sobrevive à correção por 73 tentativas:
  veja `artifacts/inference_audit/`.
- A cobertura atual é Brasil/B3. ETFs globais negociados na B3 só entram depois
  de módulo próprio de transparência e dados datados.
- Custos Clear/B3 são estimativas versionadas e precisam ser confrontados com a
  nota de corretagem, inclusive em caso de alteração de tabela.
- Uso comercial, suitability, consultoria ou gestão exigem estrutura regulatória,
  contratual e controles adequados. Este repositório é pesquisa e apoio à
  decisão, não aconselhamento individual.

Consulte [a integração ITR](docs/itr_integration.md), a
[governança de produção](docs/production_governance.md) e o
[desenho de pesquisa](docs/value_quality_research_design.md) e o
[protocolo brapi + CDI BCB](docs/brapi_total_return_research.md).
