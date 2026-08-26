# Protocolo — cadência de revisão e isenção mensal

Estado: **diagnóstico concluído**. Uma hipótese refutada, um padrão comercial
utilizável, nenhuma mudança de regra.

## Duas lacunas

O estudo de cadência comparava doze, três e um mês e nunca testou **seis**, que
é a cadência que um comitê de assessoria de fato quer. E todo número pós-imposto
do projeto cobrava 15% lisos sobre ganho realizado em ações, embora
`BrazilianTaxModel` já carregasse a isenção mensal de vendas e simplesmente
nunca a chamasse — `annual_tax_brl` era código morto.

A isenção é um **penhasco, não uma dedução**: vender até o limite mensal deixa o
ganho livre, vender um real acima tributa o ganho inteiro. O tamanho da venda
depende do saldo do cliente, então cadência não tem resposta única para todos.

## Hipótese testada

Que modelar a isenção transformasse "giro é ruim para o cliente" em "giro
fracionado é bom para o cliente pequeno", porque dividir a mesma venda anual em
mais revisões é justamente o que a coloca abaixo do limite.

## Resultado 1 — a isenção é real e pequena

Perfil equilibrado, por tamanho de carteira e cadência (CAGR pós-IR):

| Carteira | cadência | sem isenção | com isenção | ganho | revisões isentas |
|---|---|---:|---:|---:|---:|
| R$ 100 mil | anual | 13,32% | 13,35% | +0,03pp | 15% |
| R$ 100 mil | trimestral | 13,18% | 13,33% | +0,15pp | 71% |
| R$ 100 mil | mensal | 12,77% | 12,96% | **+0,19pp** | 90% |
| R$ 300 mil | mensal | 12,76% | 12,85% | +0,09pp | 59% |
| R$ 1 milhão | mensal | 12,76% | 12,76% | +0,00pp | 8% |
| R$ 5 milhões | qualquer | — | sem efeito | 0,00pp | 0% |

O mecanismo existe e funciona como previsto: quanto menor a carteira e mais
fracionada a venda, maior a parcela de revisões isentas. Mas o ganho máximo é de
0,19 ponto percentual ao ano, e ele **não inverte nada**. Mesmo com isenção
integral, a cadência mensal de uma carteira de R$ 100 mil rende 12,96% contra
13,35% da anual.

**Hipótese refutada.** A isenção não compra o giro.

## Resultado 2 — semestral não é melhor, é indistinguível

A primeira leitura sugeria que o semestral batia o anual. O teste pareado por
ano-calendário desmonta isso:

| Perfil | cadência | diferença média | vence em | p |
|---|---|---:|---:|---:|
| conservador | semestral | +0,16pp | 7 de 13 | 0,686 |
| equilibrado | semestral | +0,21pp | 6 de 13 | 0,799 |
| arrojado | semestral | −0,98pp | 5 de 13 | 0,539 |

A vantagem some no arrojado e nenhuma diferença chega perto de significância. O
semestral é **equivalente** ao anual, não superior.

## Resultado 3 — o que de fato é utilizável

O custo de acelerar a cadência cresce com o giro do perfil:

| Perfil | giro anual | trimestral vs anual | mensal vs anual |
|---|---:|---:|---:|
| conservador (12 nomes) | 0,43 | **+0,25pp** | −0,19pp |
| equilibrado (8 nomes) | 0,60 | −0,80pp | −1,18pp |
| arrojado (5 nomes) | 0,91 | −3,18pp | −4,02pp |

Nenhuma célula é significativa isoladamente (p entre 0,16 e 0,87), mas o padrão
é monótono nas duas direções: quanto mais concentrado o livro, mais caro é
revisá-lo com frequência. A cesta larga de baixo giro absorve revisão trimestral
a custo praticamente nulo; a concentrada não.

Isso fecha com os outros dois achados do projeto. O perfil conservador de doze
nomes gera **18,4 ordens por ano** contra 7,6 do arrojado, com a **menor** taxa
de giro. E agora se sabe que ele também suporta revisão trimestral sem cobrar do
cliente.

O produto defensável para o escritório é, portanto, cesta larga com revisão
trimestral no perfil conservador: quatro pontos de contato por ano, o maior
número de ordens da escada, e custo ao cliente indistinguível de zero. Não é
preciso girar mais para gerar atividade — é preciso diversificar mais.

## Limites

- A isenção cobre venda de ações à vista. Cota de ETF é tributada
  independentemente do tamanho, então um livro com a perna global recebe menos
  alívio do que esta tabela mostra.
- Cada revisão é assumida em um mês-calendário distinto e como a única venda de
  ações do cliente naquele mês. Um cliente que venda outra coisa no mesmo mês
  perde a isenção.
- O limite é parâmetro legal e muda; ele é lido de `BrazilianTaxModel`.
- Treze observações anuais, amostra de desenvolvimento, nenhum teste
  significativo.

## Reprodução

```powershell
.\.venv-benevente\Scripts\python.exe research_cadence_and_exemption.py
.\.venv-benevente\Scripts\python.exe -m pytest tests/test_annual_walk_forward.py -q
```

Saídas em `artifacts/cadence_exemption_v1/`. `apply_annual_taxes` ganhou o
parâmetro `apply_monthly_exemption`, desligado por padrão para que toda série
publicada continue reproduzível.
