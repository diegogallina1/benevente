# Protocolo anual ponto-no-tempo

## Pergunta testada

Em janeiro de cada ano, a informação disponível até aquela data consegue
formar uma carteira que sobreviva ao próximo ano? A resposta é avaliada sem
usar o preço, a cota, o resultado contábil ou a recomposição do universo que
ainda não eram públicos na data da decisão.

## Ciclo de uma decisão

1. Carregar preços, universo e fundamentos com datas de disponibilidade.
2. No primeiro pregão de `t`, rejeitar todo arquivo posterior àquela data.
3. Bloquear ativos que não passam liquidez, solvência, qualidade e limites da
   política.
4. Pontuar somente os ativos elegíveis; aplicar limites por emissor e o bloco
   defensivo em CDI.
5. Registrar pesos, custos estimados e justificativa de cada entrada, saída ou
   ajuste.
6. Manter a carteira até a primeira sessão de `t + 1` e só então calcular o
   retorno líquido realizado.

Por posição, `annual_holdings.csv` separa a **razão conhecida na decisão**
(elegibilidade, score, ação sobre o peso e restrições) do
`realised_next_year_return`, calculado depois. A coluna de retorno existe para
auditoria da tese; ela nunca entra na decisão daquele janeiro.

## Seleção adaptativa de fatores

Não existe fator que preveja com segurança o próximo ano. Para reduzir a
escolha arbitrária, o modo adaptativo compara um conjunto pequeno e declarado
antes do teste: `value_quality`, `momentum_12m` e `low_volatility`.

Para decidir o ano `t`, cada alternativa é avaliada apenas entre o começo da
amostra e `t - 1`. O placar é retorno líquido acumulado, com penalidades fixas
para drawdown e giro. O fator selecionado é congelado e usado uma vez em `t`.
O arquivo `adaptive_factor_choices.csv` mostra o fator, a data de corte e o
número de anos usados em cada decisão.

Isso não prova previsão; testa se uma regra pré-definida generaliza em anos
que não participaram da escolha. O resultado deve ser relatado junto a CAGR,
volatilidade, máximo drawdown, turnover, custos, benchmarks e subperíodos.

## Cobertura brasileira

O primeiro janeiro reproduzível exclusivamente com ITR público é **2012**:
em janeiro de 2011, o ITR de 2011 ainda não havia sido divulgado. O arquivo
de ITR começa em 2011, portanto uma janela anual de janeiro requer primeiro
montar as informações conhecidas em janeiro de 2012. Para gerar esse painel:

```powershell
python historic_snapshot_builder.py --market-panel data/my_market_snapshot_panel.csv --quality-panel data/my_quality_metrics_panel.csv --start-year 2012 --end-year 2025 --output data/fundamentals_cvm_january_panel.csv
```

Depois, rode a avaliação de 2012–2025:

```powershell
python annual_walk_forward.py --prices data/my_prices.csv --fundamentals data/fundamentals_cvm_january_panel.csv --start-year 2012 --end-year 2026 --adaptive-factors --output artifacts/annual_adaptive
```

O usuário precisa fornecer preços ajustados, CDI, composição de universo e
snapshots fundamentais datados. Sem esses arquivos vintage, o motor recusa
produzir uma conclusão histórica, em vez de preencher o passado com dados
atuais.

O arquivo `annual_benchmark_summary.csv` compara o Benevente com CDI e com um
MVO neutro no **mesmo universo elegível e com a mesma data de decisão**. Ele
evita a comparação injusta entre uma carteira filtrada e um MVO que recebe
ativos que a política teria bloqueado.

## Portão B3/CVM e retorno total

Além dos fundamentos, cada decisão deve ser cruzada com o universo B3 e o mapa
CVM **do mesmo janeiro**. O argumento `--universe` junto de `--mapping` ativa
esse portão e grava `decision_evidence_manifest.csv` no artefato anual.

```powershell
.\.venv-benevente\Scripts\python.exe annual_walk_forward.py `
  --prices data/precos_retorno_total_documentados.csv `
  --total-return-manifest data/manifesto_da_fonte_de_retorno_total.json `
  --fundamentals data/fundamentals_b3_cvm_full_2013_2025.csv `
  --universe data/b3_historical_universes.csv `
  --mapping data/b3_historical_cvm_ticker_map.csv `
  --start-year 2013 --end-year 2026 --factor triple_factor `
  --output artifacts/annual_b3_cvm
```

`build_b3_price_history.py` produz uma série de **preço** a partir do
COTAHIST, útil para formar o conjunto disponível e os sinais anteriores à
decisão. Ela é explicitamente `price_return_only`: dividendos, JCP e eventos
corporativos não são retorno total. Não use essa saída isolada para afirmar
performance, comparar CDI ou liberar a estratégia; para isso, anexe uma série
de retorno total com origem, data de extração e tratamento de eventos.

Antes de executar o experimento, rode o pré-teste. Ele registra tanto a
cobertura B3/CVM anual quanto a aptidão (ou bloqueio) da base de retorno:

```powershell
.\.venv-benevente\Scripts\python.exe preflight_annual_walk_forward.py `
  --prices data/prices_b3_cotahist_price_return_only_2011_2025.csv `
  --fundamentals data/fundamentals_b3_cvm_full_2013_2025.csv `
  --universe data/b3_historical_universes.csv `
  --mapping data/b3_historical_cvm_ticker_map.csv `
  --price-basis price_return_only `
  --output artifacts/annual_input_manifest.json
```

O retorno de saída `2` significa bloqueio esperado: substitua a fonte pelo
arquivo de retorno total documentado conforme
`data/total_return_source_manifest_template.json`. Só então use
`--price-basis total_return` para calcular performance.

O adaptador `total_return_adapter.py` aceita somente uma exportação cuja hash
SHA-256 confere com esse manifesto. A fonte deve declarar cobertura de
dividendos, JCP, bonificações, desdobramentos, subscrições e proventos de
deslistagem. A B3 informa que o COTAHIST não traz esses ajustes; a base
estruturada de eventos corporativos é fornecida separadamente no serviço de
dados da B3. Logo, não há combinação automática de fontes nem ajuste implícito
no Benevente.

## Validação treino--holdout

Depois de o experimento anual usar uma fonte de retorno total aprovada, a
validação separa os anos antes de `split-year` (treino) dos anos a partir dessa
data (holdout congelado). O relatório exige, no holdout, retorno líquido acima
de CDI **e** do MVO elegível, Sharpe excedente CDI não negativo, drawdown dentro
do limite e amostra mínima. Sem essas condições, o único status possível é
`research_only`.

```powershell
.\.venv-benevente\Scripts\python.exe validate_annual_holdout.py `
  --annual-results artifacts/annual_b3_cvm/annual_results.csv `
  --input-manifest artifacts/annual_b3_cvm/input_manifest.json `
  --split-year 2020 `
  --output artifacts/annual_b3_cvm/holdout_validation.json
```
