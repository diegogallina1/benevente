# Matriz metodológica por classe de ativo

Este documento separa o que o Benevente já calcula de regras que só poderão
entrar no motor depois da obtenção de dados comparáveis. O objetivo é aumentar
a diversificação sem misturar métricas incompatíveis ou transformar uma busca
histórica em promessa de retorno.

## Regras comuns a qualquer ativo

Todo ativo deve ter identificação, data de disponibilidade, histórico de
preço, liquidez e regra de saída verificáveis. A carteira não pode usar dado
publicado depois da data de decisão, não pode vender a descoberto e deve
descontar custos de negociação. Um ativo reprovado por informação incompleta
não recebe peso apenas para preencher uma meta de alocação.

## Ações brasileiras — implementado

1. A ação deve existir no universo B3 da data de decisão, ter ligação aceita
   com a companhia na CVM, ao menos 252 pregões anteriores e liquidez média
   mínima definida pela política.
2. Para não financeiras, o filtro exige fluxo de caixa livre positivo em
   relação ao valor de mercado, ROIC mínimo, dívida líquida/EBITDA controlada
   e cobertura de juros. Para financeiras, exige ROE mínimo e P/VP positivo.
3. Entre as aprovadas, o escore combina qualidade, earnings yield e retorno
   dos doze meses anteriores. A seleção é anual e não usa o retorno do ano
   seguinte.
4. Classes diferentes da mesma companhia são uma única exposição econômica.
   A classe de maior escore, com maior liquidez em caso de empate, prevalece.

O rebalanceamento anual reduz ou elimina uma posição quando ela deixa de
passar nos filtros, perde posição no ranking ou passa a ser menos atraente em
valor relativo. Um limite de giro deve evitar trocas por diferenças pequenas
de escore; esse limiar ainda será calibrado fora da amostra.

## ETFs — contrato de dados a implementar

ETF não deve receber métricas de empresa. A seleção precisa de: índice
replicado, classe de ativo, composição setorial/geográfica, taxa de
administração, patrimônio, volume, spread, método de replicação, tracking
difference e moeda de exposição.

O ranking sugerido combina baixo custo, liquidez, aderência ao índice,
diversificação incremental e baixa sobreposição com a carteira existente.
Dois ETFs que entregam quase a mesma exposição são tratados como uma única
fonte de risco. ETFs podem funcionar como núcleo diversificado da carteira,
mas não devem entrar apenas porque tiveram o maior retorno recente.

## BDRs — contrato de dados a implementar

BDR exige identificação do emissor estrangeiro, país, moeda, setor, razão de
conversão, liquidez local e no recibo, demonstrações da companhia de origem e
calendário de divulgação. A análise fundamental deve usar os dados do emissor
original, com conversão cambial registrada na data de decisão.

O score proposto conserva valor, qualidade e tendência, mas acrescenta risco
de moeda, concentração por país e sobreposição com ETFs globais. Sem esse
conjunto mínimo de dados, o BDR permanece visível no explorador, mas não é
elegível para uma recomendação.

## FIIs e Fiagros — contrato de dados a implementar

FIIs e Fiagros são veículos de renda e crédito, não companhias operacionais.
A análise deve considerar liquidez, P/VP, qualidade e concentração dos
ativos, vacância, prazo dos contratos, alavancagem, indexadores, duration,
concentração de locatários ou devedores e sustentabilidade dos rendimentos.

O ranking deve penalizar distribuições não recorrentes, concentração excessiva
e desconto que resulte de deterioração de crédito ou imóveis. Dividend yield
isolado não é sinal suficiente.

## Renda fixa e títulos

Para CDI, Tesouro, crédito privado e fundos de renda fixa, a decisão exige
indexador, duration, taxa de compra, liquidez, risco de crédito, emissor,
garantias e tributação. A alocação defensiva não é um "resto" sem análise:
ela é escolhida para atender necessidade de liquidez e limite de risco.

## Construção de carteira

O processo pretendido usa três níveis:

1. Seleção dentro de cada classe com a régua apropriada.
2. Controle de exposição por emissor, setor, país, moeda e fator de risco.
3. Alocação entre classes para a política escolhida, com custos e liquidez.

Uma versão 100% renda variável pode ser pesquisada, mas deve conter número
suficiente de emissores independentes e limites de setor. A política não deve
forçar 100% de risco quando a triagem não oferece ativos independentes e
líquidos suficientes.

## Estado atual

O motor anual e o backtest já implementam a régua de ações brasileiras,
diversificação por emissor na estratégia de três fatores e CDI. ETFs, BDRs,
FIIs/Fiagros e títulos estão inventariados no universo B3, mas os módulos de
dados e os escores próprios desta matriz ainda não estão integrados à
carteira. Eles não podem ser apresentados como elegíveis antes dessa etapa.
