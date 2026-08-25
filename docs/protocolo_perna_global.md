# Protocolo — perna global declarada

Estado: **primeiro eixo com resultado positivo**. Recomendado para
pré-registro, não para publicação imediata.

## Por que este eixo e não mais ações brasileiras

Toda ampliação testada até aqui sorteava do mesmo ranking do mesmo mercado. Do
sexto ao vigésimo nome, a correlação com os cinco primeiros é 0,93: a cesta
larga compra variedade, não proteção. A pergunta era se existe alguma exposição
neste projeto que não seja outro sorteio desse ranking.

Existe, e a diferença é grande:

| Par | correlação diária | correlação anual |
|---|---:|---:|
| cesta B3 larga × cesta B3 concentrada | 0,93 | — |
| **sleeve B3 × IVVB11** | **0,064** | **−0,52** |

## Regra

O fundo é **declarado, nunca selecionado**. Não tem registro na CVM, logo não
tem snapshot fundamentalista e a triagem por fator não consegue alcançá-lo — ele
entra no painel como instrumento precificado sem ficha, que é justamente o que
impede o fator de escolhê-lo. Ele é recortado **de dentro** do orçamento de
ações, não somado a ele: a exposição declarada a renda variável não cresce
porque parte dela passou a ser mantida no exterior.

Antes de o fundo ter um ano completo de histórico na data da decisão, não há
coluna e o ano roda inteiramente doméstico. Na janela avaliada isso significa
que o sleeve foi efetivamente mantido em 10 dos 11 anos.

Apenas IVVB11 tem histórico suficiente. NASD11 e ACWI11 listaram em 2021 e não
podem informar uma decisão de 2016; estão registrados no manifesto com suas
datas para que a ausência seja uma data, e não uma opinião.

## Resultado, decisões de 2015 a 2025

| Perfil | global | CAGR | pós-IR | vol | queda | Sharpe exc. | giro |
|---|---:|---:|---:|---:|---:|---:|---:|
| conservador | 0% | 12,72% | 11,97% | 9,1% | −19,23% | 0,408 | 0,46 |
| conservador | 20% | 13,10% | 12,43% | 7,2% | −16,79% | 0,512 | 0,40 |
| conservador | 30% | 13,20% | 12,56% | 6,4% | −15,82% | 0,543 | 0,37 |
| equilibrado | 0% | 15,38% | 14,16% | 15,6% | −29,77% | 0,432 | 0,64 |
| equilibrado | 20% | 15,86% | 14,78% | 13,0% | −26,84% | 0,507 | 0,55 |
| equilibrado | 30% | 15,76% | 14,77% | 11,9% | −25,34% | 0,521 | 0,50 |
| arrojado | 0% | 19,81% | 17,61% | 28,4% | −47,78% | 0,461 | 0,97 |
| arrojado | 20% | 21,05% | 19,11% | 24,7% | −44,18% | 0,537 | 0,81 |
| arrojado | 30% | 20,73% | 18,97% | 23,1% | −43,37% | 0,542 | 0,73 |

Retorno sobe, volatilidade cai, queda máxima cai e o Sharpe do excesso sobe —
nos três perfis, em todas as frações testadas. É o único eixo testado neste
projeto que melhorou as duas pontas ao mesmo tempo. Os anos em que o perfil bate
o CDI passam de 7 para 8 de 11 nos três.

## A ressalva que decide a conversa com o cliente

O fundo é **sem hedge cambial**, e o período foi de desvalorização contínua do
real:

| Série | CAGR 2015–2025 |
|---|---:|
| S&P 500 (USD) | 11,82% |
| USD/BRL | 6,64% |
| **IVVB11 (BRL)** | **20,29%** |

O dólar saiu de R$ 2,70 para R$ 5,48 em onze anos. Cerca de **um terço** do
retorno do sleeve veio do câmbio, não do mercado americano. A correlação diária
do IVVB11 com o dólar é 0,493, quase tão alta quanto com o próprio S&P 500
(0,606).

Portanto a correlação anual de −0,52 contra a cesta B3 é, em boa parte, efeito
cambial: real fraco derruba a bolsa brasileira e levanta o ativo estrangeiro não
protegido. Isso é um hedge real e é uma exposição que o cliente pode querer —
mas é uma posição comprada em dólar, e precisa ser vendida como tal. Se o real
se valorizar na próxima década, a diversificação permanece e a contribuição de
retorno inverte.

## O que não fazer com esta tabela

A fração ótima aparenta estar entre 20% e 30%. Escolher o máximo da curva depois
de olhar a curva é exatamente o erro medido em `configuration_search`, onde
ampliar a grade de 36 para 256 candidatos custou 2,63 pontos percentuais ao ano.
A declaração correta é um número redondo fixado antes, com o registro dizendo
por que aquele número, e não o argmax da amostra.

## Limites

- Amostra de desenvolvimento; onze observações anuais e um único regime cambial.
- Preço de fechamento ajustado público, sem reconciliação primária própria; o
  painel herda o nível `public_reproducible_research` do painel pai.
- O custo de execução do sleeve usa o piso de liquidez do motor, porque o ETF
  não tem ficha com volume observado. Isso **superestima** seu custo.
- A taxa de administração do fundo já está dentro do preço cotado.
- O sleeve reduz o giro do livro (0,46 para 0,40 no conservador a 20%), o que
  reduz o número de ordens geradas — relevante para a receita transacional do
  escritório, na direção oposta ao que a cesta larga fez.

## Reprodução

```powershell
.\.venv-benevente\Scripts\python.exe build_global_etf_panel.py
.\.venv-benevente\Scripts\python.exe research_global_sleeve.py
.\.venv-benevente\Scripts\python.exe -m pytest tests/test_annual_walk_forward.py -q
```

Saídas em `artifacts/global_sleeve_v1/`. Painel em
`data/prices_b3_with_global_2011_2025.csv`, com manifesto que carrega o hash do
painel pai.
