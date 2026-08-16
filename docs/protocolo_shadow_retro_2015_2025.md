# Shadow retrospectivo automatizado

## Finalidade

Este processo reproduz como a estratégia candidata teria sido operada: em cada janeiro, forma uma carteira somente com preços existentes até a data de decisão, registra seus pesos e a mantém até o janeiro seguinte. O retorno do período entra somente como avaliação posterior.

## Estratégia registrada

**Momentum Anual Diversificado Ajustado por Volatilidade**

- Universo: todos os instrumentos com 252 sessões anteriores observáveis.
- Sinal: ranking transversal do retorno total dos últimos 12 meses.
- Peso: ranking ao quadrado dividido pela volatilidade de 12 meses.
- Revisão: anual, no primeiro pregão de janeiro.
- Custo-base: 0,15% por unidade de giro.
- Sem filtro de qualidade, setor, emissor, limite de posição ou número máximo de ativos.

## Registros gerados

- `data/shadow_retro_momentum_2015_2025/annual_ledger.csv`: decisão, período, tamanho do universo, giro, custo, retorno da candidata, CDI e MVO.
- `data/shadow_retro_momentum_2015_2025/target_weights.csv`: todos os pesos congelados em cada decisão para a candidata e para o MVO comparável.
- `data/shadow_retro_momentum_2015_2025/shadow_manifest.json`: regra, hash do insumo de preços, custos, resumo e limitações.

## Resultado do processo retrospectivo

| Métrica, 2015–2025 | Resultado |
| --- | ---: |
| CAGR da candidata | 17,42% a.a. |
| CAGR do CDI | 9,63% a.a. |
| CAGR do MVO no mesmo universo | 28,48% a.a. |
| Anos acima do CDI | 6 de 11 |
| Anos acima do MVO | 4 de 11 |
| Anos acima de ambos | 3 de 11 |
| Pior ano da candidata | -8,31% |

Foi verificada também a grade integral de 73 regras livres. Nenhuma venceu CDI e MVO nos 11 anos; a melhor atingiu 5 de 11 anos contra ambos. Portanto, a exigência de vencer ambos todos os anos não é satisfeita pela evidência disponível e não deve ser declarada como característica do sistema.

## Como usar para a simulação futura

1. Fixar data de decisão, capital de referência e corretora simulada.
2. Salvar o arquivo de pesos antes de acompanhar o primeiro retorno.
3. Registrar custos e proventos efetivamente observados, sem substituir o arquivo de decisão.
4. Comparar mensal e anualmente com CDI, Ibovespa e MVO definidos antes da simulação.
5. Ao fim de 12 e 24 meses, avaliar retorno relativo líquido, giro, custos, perdas e qualidade dos dados. Não recalibrar a regra com os retornos do próprio período de teste.
