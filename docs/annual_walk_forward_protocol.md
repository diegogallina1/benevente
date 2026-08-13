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
