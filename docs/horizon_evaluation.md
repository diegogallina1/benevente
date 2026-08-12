# Avaliação auditável em 5, 10 e 15 anos — Benevente Quant AI

## Metodologia fixa

As janelas foram definidas antes da leitura dos resultados: avaliação iniciando em 01/07/2021 (5 anos), 01/07/2016 (10 anos) e 01/07/2011 (15 anos), todas encerradas em 30/06/2026. Cada janela inclui um ano anterior, separado, apenas para estimar os primeiros parâmetros; a carteira inicia após esse lookback. Em cada rebalanceamento mensal, todos os insumos usados pertencem a `T-1` ou antes.

Os snapshots arquivados usam preços ajustados B3 e Ibovespa de Yahoo Finance via `yfinance`; CDI, Selic e IPCA vêm do Banco Central do Brasil (SGS 12, 432 e 433). O backtest cobra 10 bps de transação e 5 bps de slippage por turnover executado.

## Comparação principal

| Janela | Estratégia | Retorno acumulado | CAGR | Volatilidade anual | Sharpe excedente CDI | Máx. drawdown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5 anos | Benevente Quant AI | 69,87% | 11,38% | 8,69% | -0,05 | -11,00% |
| 5 anos | CDI | 76,47% | 12,25% | 0,67% | N/A | 0,00% |
| 5 anos | Ibovespa | 38,09% | 6,78% | 16,78% | -0,22 | -20,43% |
| 10 anos | Benevente Quant AI | **226,23%** | **12,78%** | 15,04% | **0,29** | -29,59% |
| 10 anos | CDI | 141,66% | 9,39% | 1,13% | N/A | 0,00% |
| 10 anos | Ibovespa | 220,60% | 12,58% | 24,79% | 0,26 | -45,68% |
| 15 anos | Benevente Quant AI | **408,29%** | **11,65%** | 12,23% | **0,20** | -18,93% |
| 15 anos | CDI | 298,23% | 9,82% | 1,00% | N/A | 0,00% |
| 15 anos | Ibovespa | 174,10% | 7,08% | 23,39% | 0,01 | -40,77% |

## Conclusão suportada pelos dados

O Benevente Quant AI superou o CDI em retorno acumulado e CAGR nas janelas de 10 e 15 anos. Na janela de 10 anos, também obteve o maior retorno entre as estratégias comparadas. Na janela de 5 anos, não superou o CDI. O MVO clássico obteve retorno acumulado ligeiramente maior na janela de 15 anos (413,78% contra 408,29%), portanto não se deve afirmar que o Benevente foi o maior retorno em todas as janelas.

## Auditoria e limites

Os validadores em `artifacts/horizons/{5y,10y,15y}/validation_report.json` aprovaram a integridade dos três snapshots: 1.493, 2.737 e 3.974 linhas de preço, respectivamente; nenhum nulo ou data duplicada; e curvas de patrimônio recompostas de forma independente dentro de tolerância numérica.

Ainda há limitações relevantes: o universo fixo de ações atuais pode conter viés de sobrevivência; Yahoo Finance é fonte secundária; e os custos são parâmetros documentados, não registros de execução. Resultados históricos não são recomendação de investimento ou garantia de desempenho futuro.

