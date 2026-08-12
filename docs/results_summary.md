# Resultados empíricos — Benevente Quant AI

## Execução avaliada

- Janela de preços: 02/01/2023 a 30/06/2026.
- Rebalanceamento: aproximadamente mensal (21 pregões), com 252 pregões de histórico inicial.
- Dados: cotações ajustadas Yahoo Finance (`yfinance`), CDI/Meta Selic/IPCA do Banco Central do Brasil (SGS 12, 432 e 433).
- Custos modelados: 10 bps de transação e 5 bps de slippage por turnover executado.

## Resultado principal

| Estratégia | Retorno acumulado | CAGR | Volatilidade anual | Sharpe excedente CDI | Máx. drawdown | Turnover médio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Benevente Quant AI | 22,98% | 8,93% | 9,95% | -0,32 | -4,87% | 21,95% |
| MVO clássico | 20,00% | 7,84% | 13,74% | -0,28 | -7,30% | 22,66% |
| CDI | 34,23% | 12,95% | 0,50% | N/A | 0,00% | 0,00% |
| Ibovespa | 27,21% | 10,47% | 19,92% | -0,02 | -14,81% | 0,00% |

O Benevente Quant AI apresentou menor volatilidade e drawdown que MVO clássico e Ibovespa, mas não superou o CDI no período. Portanto, os resultados não sustentam alegação de alfa ou superioridade de retorno.

## Calibração temporal

Seleção em 12 períodos antes de 01/01/2025: gamma=1,0 e influência dos sinais=0,30. No holdout de 17 períodos, o retorno acumulado foi 15,46%, o CAGR foi 10,68%, o máximo drawdown foi -4,87% e o Sharpe excedente CDI foi -0,27. A amostra é pequena e não confirma geração de alfa.

## Integridade e limitações

`validation_report.json` verificou 871 linhas de preços, nenhuma data duplicada ou nula e recomposição independente das curvas dentro de tolerância numérica. Limitações: universo fixo de ações atuais (viés de sobrevivência), Yahoo Finance como fonte secundária e custos modelados, não custos observados. Não é recomendação de investimento.

## Extensão de horizonte

A avaliação fixa em 5, 10 e 15 anos está documentada em `docs/horizon_evaluation.md`. O Benevente Quant AI superou o CDI nas janelas de 10 e 15 anos, mas não na janela de 5 anos.
