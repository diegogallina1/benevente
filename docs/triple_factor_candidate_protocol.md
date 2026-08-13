# Estratégia multifatorial candidata — protocolo pré-registrado

## Objetivo

Investigar uma alternativa à linha de base conservadora sem transformar
retorno já observado em regra de investimento. Esta estratégia é pesquisa;
não é uma recomendação, promessa de retorno, nem política de carteira viva.

## Informação disponível na decisão anual

No primeiro pregão de janeiro, para cada emissor com demonstração CVM já
recebida e preço anterior à decisão, a estratégia exige:

- volume médio diário de pelo menos R$ 10 milhões;
- lucro positivo (P/L positivo);
- ROIC acima do limite para não financeiras ou ROE acima do limite para
  financeiras;
- retorno de preço dos 12 meses anteriores.

Métricas secundárias de dívida e cobertura de juros ficam registradas quando
existirem, mas ausência delas não é convertida em um sinal de risco nem em
aprovação. Isso evita excluir automaticamente empresas porque a taxonomia CVM
histórica não forneceu um campo comparável. A regra continua rejeitando falta
de liquidez, qualidade primária ou lucro positivo.

## Score

Entre os ativos elegíveis, o score é calculado transversalmente apenas com
dados disponíveis na data da decisão:

\[
S_i = 0,40 Z(Q_i) + 0,40 Z(E/P_i) + 0,20 Z(R_{12m,i})
\]

onde \(Q_i\) é ROIC para não financeiras e ROE para financeiras. Empates são
resolvidos pelo ticker, para que a regra seja determinística.

## Construção e perfil de risco

São selecionados os três ou quatro maiores scores. O teto de exposição em
ações vem da política do investidor; o teto por emissor nunca é relaxado.
Quando há poucos ativos elegíveis, o excedente fica em CDI — a estratégia não
inventa diversificação ou viola concentração para atingir uma exposição alvo.

| Perfil | Teto padrão de ações | Teto por emissor | Revisão |
|---|---:|---:|---|
| Conservador | 35% | 10% | trimestral |
| Moderado | 55% | 12% | trimestral |
| Crescimento | 70% | 15% | semestral |
| Arrojado | 80% | 15% | semestral |

Os tetos são limites, não uma previsão de retorno. Em um universo reduzido,
por exemplo, quatro ativos com máximo de 15% só permitem 60% em renda
variável, mesmo para perfil crescimento ou arrojado.

## Custos, comparação e validação

Cada revisão deduz custos do modelo Clear/B3 configurado no projeto. O MVO de
controle recebe o mesmo universo elegível, mesma data, mesmo teto de ações e
mesmo teto por emissor; CDI é o benchmark defensivo. A seleção de qualquer
configuração candidata deve ocorrer no período de treino e ser avaliada uma
vez no holdout congelado.

Na primeira reprodução com o painel público atual (2013–2025, oito emissores,
preços documentados), o cenário de quatro ativos, 60% máximo em ações e 15%
por emissor teve CAGR de 13,29% após custos, versus 9,51% do CDI e 12,50% do
MVO elegível sob as mesmas restrições. O moderado chega a 48% em ações (quatro
ativos vezes 12%) e registrou 12,73% a.a.; o conservador, 35%, registrou 12,10%
a.a. Esses números são uma descrição histórica, não uma promessa.

No holdout congelado 2020–2025, a configuração de 60% superou o CDI, mas ficou
abaixo do MVO elegível. Logo, o status correto permanece `research_only` até
passar os critérios de prontidão comercial em um holdout mais longo e um universo
de maior cobertura. A aplicação ajusta o **orçamento de risco** ao perfil do
investidor; ela não deve ajustar pesos usando retornos futuros nem prometer que
todo perfil superará todo benchmark.
