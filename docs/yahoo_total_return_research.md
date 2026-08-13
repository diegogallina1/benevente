# Pesquisa de retorno ajustado: Yahoo Finance + BCB

Esta rota viabiliza um experimento reproduzível sem BRAPI paga. Ela obtém o
`Adj Close` do Yahoo Finance via `yfinance`, arquiva a série bruta de cada
código, guarda os eventos de dividendos e desdobramentos retornados pelo
provedor e compõe a reserva defensiva com a série SGS 12 (CDI diário) do Banco
Central do Brasil.

O preço ajustado é um **proxy de retorno total para pesquisa**. O Yahoo não
separa JCP e não substitui a conciliação de eventos corporativos da B3/CVM.
Por isso, a fonte recebe `source_tier=public_reproducible_research`: ela pode
gerar resultados e hipóteses auditáveis, mas não libera o status comercial ou
uma promessa de rentabilidade.

## Construir ou retomar o painel

```powershell
.\.venv-benevente\Scripts\python.exe yahoo_total_return.py `
  --fundamentals data/fundamentals_b3_cvm_full_2013_2025.csv `
  --start 2013-01-01 --end 2025-12-31 `
  --output data/prices_yahoo_adjusted_total_return_2013_2025.csv `
  --manifest data/yahoo_adjusted_total_return_2013_2025_manifest.json `
  --coverage-report artifacts/yahoo_adjusted_total_return_coverage.csv
```

O comando pode ser interrompido e retomado: as respostas ficam em
`work/yahoo_total_return/`. `--download-limit 50` permite baixar somente um
lote de 50 códigos ainda não arquivados. O relatório de cobertura mantém cada
código bloqueado e seu motivo; ele não trata deslistagens como dado ausente
silencioso.

## Avaliar a hipótese anual

```powershell
.\.venv-benevente\Scripts\python.exe annual_walk_forward.py `
  --prices data/prices_yahoo_adjusted_total_return_2013_2025.csv `
  --total-return-manifest data/yahoo_adjusted_total_return_2013_2025_manifest.json `
  --fundamentals data/fundamentals_b3_cvm_full_2013_2025.csv `
  --start-year 2015 --end-year 2026 `
  --adaptive-factors --maximum-equity-weight 0.55 `
  --maximum-asset-weight 0.12 --top-assets 4 `
  --output artifacts/yahoo_walk_forward_adaptive
```

O primeiro ano de decisão é 2015 porque o painel inicia em 2013 e o protocolo
exige 252 sessões anteriores, sem completar artificialmente feriados ou
ausências de ativos. Em cada janeiro, a seleção de fator usa apenas anos já
encerrados; a carteira contínua mantém patrimônio, pesos que derivaram e
custos de rebalanceamento de uma revisão para a seguinte.

`annual_benchmark_summary.csv` compara Benevente, CDI e MVO neutro no mesmo
universo que passou o filtro pontual. `annual_holdings.csv` e
`annual_transitions.csv` preservam o porquê de cada posição e troca.

## Resultado de referência desta execução

Com a amostra 2018--2024 da seleção adaptativa e os limites moderados acima,
o resultado líquido foi 8,93% a.a., contra 6,91% a.a. do CDI e 8,94% a.a. do
MVO elegível. A estratégia superou o CDI, mas ficou marginalmente abaixo do
MVO; portanto seu status é **research only**. Não use esse número como
promessa, recomendação ou justificativa de venda.

## Próxima validação necessária

1. Conciliar uma amostra estratificada de dividendos, JCP, desdobramentos e
   deslistagens contra B3/CVM ou um provedor licenciado.
2. Promover o manifesto somente depois da reconciliação para
   `reconciled_primary_records` ou `official_or_licensed_verified`.
3. Rodar um holdout anual congelado. A aprovação exige superar CDI e MVO no
   holdout, líquido de custos, além dos limites de risco do protocolo.
