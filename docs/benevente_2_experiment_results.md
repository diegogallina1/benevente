# Resultado experimental — Benevente 1 versus Benevente 2

Execução local, não publicada. Período completo: 2015–2025. A configuração candidata do Benevente 2 foi escolhida somente com 2015–2018 e congelada para a leitura retrospectiva de 2019–2025.

| Métrica, 2015–2025 | Benevente 1 | Benevente 2 candidato |
| --- | ---: | ---: |
| CAGR após custos modelados | 17,86% | 18,45% |
| Volatilidade anual | 22,93% | 18,58% |
| Sharpe do excesso sobre CDI | 0,438 | 0,518 |
| Queda máxima diária | -47,78% | -28,75% |
| Retorno acumulado | 509,83% | 543,77% |

No recorte 2019–2025, o CAGR foi 17,95% no Benevente 1 e 18,03% no Benevente 2. A diferença é pequena e não significativa no teste anual pareado (p = 0,964; sete anos). Portanto, não há evidência de retorno adicional. A redução de risco é a contribuição observada.

## Covid

A candidata entrou em alerta em 28/02/2020 e em estado grave em 10/03/2020. A exposição mínima a ações foi 35%. Ela não antecipou a pandemia: reagiu ao drawdown e à volatilidade conhecidos no fechamento anterior.

| 2020 | Benevente 1 | Benevente 2 | Ibovespa |
| --- | ---: | ---: | ---: |
| Retorno no ano | 1,78% | 4,35% | 0,62% |
| Queda máxima diária | -47,78% | -28,75% | -46,82% |

## Sensibilidade

Foram executadas 432 configurações. Todas reduziram o drawdown no recorte 2019–2025. Apenas 9,03% elevaram simultaneamente CAGR e drawdown em relação ao Benevente 1. O CAGR mediano foi 16,86%, abaixo da linha de base. Isso confirma que proteção é robusta, mas retorno adicional não é.

## Limitações

- A família de proteção foi concebida depois da Covid e possui viés retrospectivo conceitual.
- O treino contém apenas quatro anos e a avaliação apenas sete.
- O imposto sobre trocas intranuais ainda não foi modelado.
- Não existe ainda arquivo histórico de notícias com horário verificável; a LLM não participou.

Arquivos completos: `artifacts/benevente2_event_risk/summary.json`, `candidate_annual_comparison.csv`, `candidate_daily_comparison.csv` e `sensitivity_grid.csv`.
