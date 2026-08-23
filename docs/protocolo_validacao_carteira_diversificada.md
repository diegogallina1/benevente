# Protocolo de validação — carteira diversificada de renda variável

## Hipótese

Uma cesta anual de emissores brasileiros independentes, selecionada por
qualidade, valor e comportamento de preço, pode superar CDI e MVO comparável
sem depender de concentração extrema em um único ativo.

## Dados e recortes

- Dados de decisão: universo B3 e demonstrações CVM disponíveis em cada janeiro.
- Retornos: preços ajustados de pesquisa e CDI diário do BCB.
- Treino: decisões de 2015 a 2020.
- Avaliação não vista: decisões de 2021 a 2025.
- Uma empresa com mais de uma classe de ação conta como um emissor.

## Candidatos pré-definidos

Todos usam o mesmo filtro de elegibilidade, o mesmo fator triplo e rebalanceamento anual:

| Candidato | Ações | Máximo por emissor |
|---|---:|---:|
| D8 | 100% | 12,5% | 
| D10 | 100% | 10,0% |
| D12 | 100% | 8,33% |

Não será escolhido nenhum parâmetro depois de olhar o período de avaliação.

## Critério de aprovação

O candidato escolhido no treino só avança se, no período de 2021 a 2025:

1. CAGR líquido superar CDI e MVO comparável.
2. Não houver concentração acima do limite declarado por emissor.
3. O pior retorno anual não for pior que o dobro da perda anual do MVO, salvo
   justificativa documentada e nova avaliação.
4. A conclusão permanecer válida sob custos de 10 e 20 bps por operação.

Se nenhum candidato passar, a hipótese é rejeitada. O site não recebe uma
estratégia "vencedora" por seleção retrospectiva.

## Resultado da primeira validação

A seleção no treino foi D10: 10 emissores, 10% máximo por emissor e 100%
em ações. Entre 2015 e 2020, D10 teve CAGR líquido de 20,27%, acima do MVO
comparável de 16,89% e do CDI de 8,51%.

No período não visto de 2021 a 2025, D10 teve CAGR de 8,34%, contra 4,02%
do MVO e 10,35% do CDI. O resultado permaneceu acima do MVO sob custos de
0, 10, 20 e 40 bps, mas ficou abaixo do CDI. Portanto a hipótese de superar
os dois referenciais de forma consistente foi rejeitada. A regra não deve
ser promovida para o site como estratégia recomendada.

A próxima rodada deve testar uma alocação entre ações e ativos defensivos,
com a exposição a ações decidida antes de cada ano por sinais de regime e
sem usar resultados futuros.
