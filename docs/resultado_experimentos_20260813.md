# Resultado da bateria de experimentos — 13/08/2026

## Objetivo e regra de rejeição

Foram avaliadas 19 regras anuais, sem usar a rentabilidade do ano de manutenção para formar a carteira: quatro sinais (valor e qualidade, três fatores, momento e baixa volatilidade), quatro limites de renda variável (35%, 55%, 80% e 100%) e três níveis de diversificação da carteira de três fatores. Em cada janeiro, somente preços anteriores, dados financeiros já divulgados, liquidez e os custos estimados são considerados.

O período de seleção foi 2015–2020 e a validação isolada foi 2021–2025. Uma regra só pode ser considerada aprovada se superar, em CAGR líquido, tanto o CDI quanto o MVO elegível durante a validação.

## Resultado selecionado corretamente

O critério declarado antes de abrir a validação escolheu a regra de três fatores, 100% em renda variável, até 10 ativos e peso máximo de 10% por ativo.

| Período | Benevente | MVO elegível | CDI | Veredito |
| --- | ---: | ---: | ---: | --- |
| Seleção 2015–2020 | 20,27% a.a. | 16,89% a.a. | 8,51% a.a. | melhor nos dados de seleção |
| Validação 2021–2025 | 8,34% a.a. | 4,02% a.a. | 10,35% a.a. | **reprovada contra o CDI** |

Ela não é elegível para uso como estratégia vencedora. O resultado elevado na primeira metade não se repetiu contra o CDI na segunda.

## Sinal promissor que ainda não é conclusão

A regra de **baixa volatilidade com 35% em renda variável**, até 10 ativos e 10% por ativo, superou os dois referenciais nos dois blocos:

| Período | Benevente | MVO elegível | CDI |
| --- | ---: | ---: | ---: |
| 2015–2020 | 9,59% a.a. | 8,50% a.a. | 8,51% a.a. |
| 2021–2025 | 15,10% a.a. | 14,86% a.a. | 10,35% a.a. |

Essa leitura surgiu dentro de uma grade com múltiplas tentativas. Embora passe os dois blocos, escolhê-la depois de observar a validação criaria viés de seleção. Ela fica marcada como candidata para uma terceira amostra, uma base externa ou acompanhamento prospectivo; não como comprovação de alfa.

## Teste adaptativo anual

Também foi testada uma política que, a cada janeiro, escolhe sinal e limite de renda variável somente pelo histórico de decisões anteriores. No bloco 2021–2025, ela entregou 8,42% a.a., contra 10,11% do MVO e 10,35% do CDI. Foi reprovada.

## Próxima evidência necessária

1. Congelar a regra de baixa volatilidade de 35% antes de novo teste.
2. Validá-la em período ainda não usado, idealmente com preços de fonte licenciada e proventos reconciliados.
3. Rodar custos em cenários explícitos de corretagem, emolumentos, spread e impacto de mercado.
4. Só então levar uma carteira-sombra prospectiva para acompanhamento.

Os arquivos reproduzíveis da grade estão em `artifacts/research_grid_20260813/`; o experimento adaptativo está em `artifacts/adaptive_policy_20260813/`.

## Robustez adicional

Uma segunda grade avaliou 16 combinações do sinal de baixa volatilidade,
com 15%, 25%, 35% e 45% de renda variável e limites de 5% ou 10% por
ativo. Doze combinações superaram CDI e MVO nos dois blocos agregados.
Isso sugere que a hipótese não depende exclusivamente do limite de 35%.

Por outro lado, a vantagem anual não é constante. Em três janelas móveis
de três anos, a variante com 15% em renda variável e 10% por ativo passou
ambos os referenciais em duas de três janelas; no bloco 2018–2020 ficou
0,23 ponto percentual ao ano abaixo do MVO. As demais variantes também
falharam ao menos uma das janelas contra um dos referenciais.

O teste de custos sobre a variante de 15% mostrou que a margem contra o
MVO é pequena: com quatro vezes o custo de rebalanceamento registrado, a
validação 2021–2025 passa de +0,12 para -0,01 ponto percentual ao ano
contra o MVO. Ela permanece acima do CDI, mas não cumpre a regra de
superar ambos. Portanto, o resultado é **promissor, porém não robusto o
suficiente para uma carteira real**.

Arquivos: `artifacts/low_volatility_robustness_20260813/`,
`artifacts/rolling_validation_20260813/` e
`artifacts/cost_stress_20260813/`.

## Teste sem limites e sem filtros

Foi criada uma bateria permissiva que remove filtros de qualidade,
liquidez, emissor, setor, número de ativos e peso máximo. A única condição
mantida foi técnica: o instrumento precisava ter 252 sessões anteriores de
cotações, pois não existe como decidir por um ativo sem histórico observável.
Todas as ações elegíveis receberam peso positivo nas regras de pesos iguais,
inverso de volatilidade, momento e reversão. Também foi executado um MVO
long-only sem teto por posição nem limite de renda variável.

Os resultados agregados de 2015–2025 parecem altos, mas não se sustentam em
uma divisão temporal honesta. Por exemplo, o MVO irrestrito com aversão ao
risco 10 entregou 48,31% a.a. em 2015–2020 e 8,15% a.a. em 2021–2025,
contra CDI de 8,60% e 10,87% a.a., respectivamente. A carteira de pesos
iguais teve 40,99% a.a. no primeiro bloco e 6,85% a.a. no segundo.

O aparente ganho no período inteiro não é prova de estratégia. Ele é
compatível com dependência de regime e com viés de sobrevivência do painel
público, que não reconstrói separadamente todos os eventos de deslistagem.
Além disso, o MVO irrestrito apresentou turnover médio de 174% ao ano e uma
queda anual de 30,9%; no custo multiplicado por oito, o resultado recente
caiu para 6,06% a.a.

Assim, a hipótese sem limites foi **reprovada para uso prático**. Os dados e
o código estão em `research_unrestricted_universe.py` e
`artifacts/unrestricted_universe_20260813/`.

## Grade ampla sem filtros

Em seguida foram avaliadas 73 regras que mantêm todos os instrumentos com
histórico observável: momento e reversão com janelas de 21, 63, 126 e 252
sessões, três intensidades de ranking e três escalas por volatilidade. Não
há corte de qualidade, seleção dos primeiros colocados, teto por ativo ou
limite de renda variável.

A melhor regra escolhida apenas no treino foi reversão de 126 sessões com
ranking ao quadrado. Ela ilustra o perigo de procurar retorno histórico:
54,77% a.a. de 2015–2020, mas -0,49% a.a. de 2021–2025, frente a CDI de
10,87% a.a. no mesmo segundo bloco. Foi reprovada.

Treze regras superaram o CDI nos dois blocos. A mais forte nesse subconjunto
foi momento de 252 sessões, ranking de momento ao quadrado e divisão pela
volatilidade. Ela entregou 20,84% a.a. no treino e 13,44% a.a. na validação,
versus CDI de 8,60% e 10,87% a.a. Contudo, em cortes independentes ela
perdeu para o CDI em 2024–2025 (9,72% contra 12,48% a.a.). Isso invalida a
alegação de consistência universal, apesar de a hipótese merecer estudo
prospectivo como um sinal de momento.

Os arquivos ficam em `research_unrestricted_signal_grid.py`,
`research_unrestricted_momentum_validation.py`,
`artifacts/unrestricted_signal_grid_20260813/` e
`artifacts/unrestricted_momentum_validation_20260813/`.

## Seleção adaptativa de regime

Foi testado um meta-modelo que, a cada janeiro, escolhe uma das 73 regras
livres apenas pelas rentabilidades já realizadas até o janeiro anterior. Os
critérios testados foram retorno, excesso sobre CDI, taxa de acerto e razão de
informação, em janelas de dois, três, cinco anos e expansiva.

Para evitar uma nova escolha retrospectiva, o critério foi escolhido somente
em 2018–2020 e então congelado para 2021–2025. O vencedor de treino foi
retorno expansivo: 42,57% a.a. no treino, com 100% de anos acima do CDI. Na
validação, porém, entregou 3,39% a.a. contra CDI de 10,87% a.a., com apenas
40% de acerto e pior ano de -21,74%. A adaptação foi **reprovada**.

Arquivos: `research_unrestricted_regime_selection.py`,
`research_unrestricted_regime_holdout.py`,
`artifacts/unrestricted_regime_selection_20260813/` e
`artifacts/unrestricted_regime_holdout_20260813/`.
