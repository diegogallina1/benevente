# Protocolo — escada v2: as duas camadas juntas

Estado: **candidata medida, não registrada**. Este documento produz o número que
a v2 declararia; a decisão de registrar é separada.

## Por que a rodada precisava existir

Overlay intranual e perna global foram medidos cada um contra a escada
congelada. Somar os dois ganhos seria inventar um número: as duas camadas agem
sobre o mesmo livro ao mesmo tempo. O overlay desloca o sleeve de ações para o
CDI quando o Ibovespa entra em estresse — e a perna global faz parte desse
sleeve.

## Duas formas de combinar, e a diferença é política

**Dentro.** O overlay trata o livro inteiro. Quando o Ibovespa entra em
estresse, o fundo global é vendido junto com o resto. É o overlay registrado
aplicado sem alteração a um livro que por acaso tem o fundo.

**Fora.** O fundo é mantido numa fração declarada da carteira, rebalanceada
anualmente, e o overlay roda só sobre o resto. O raciocínio é que o fundo existe
justamente porque não segue o Ibovespa — correlação diária de 0,064 com o sleeve
doméstico — então cortá-lo por um sinal de estresse doméstico vende exatamente o
ativo a que o estresse não se aplica.

As duas variantes são **pareadas em risco**: o orçamento doméstico da variante
"fora" é resolvido para que a exposição total a ações e a fração no fundo caiam
exatamente onde a variante "dentro" as coloca. Sem isso, misturar o fundo na
carteira inteira diluiria também o resíduo em CDI, e a variante "fora" venceria
por carregar mais ação, não por ser melhor. A conferência está gravada em
`summary.json` e o script falha se as duas não baterem.

A fração usada é **20% do orçamento de ações**, número redondo fixado antes de
ler o resultado. A curva do estudo da perna global tinha máximo entre 20% e 30%;
escolher o argmax depois de ver a curva é o erro que custou 2,63 pontos ao ano
na busca de configurações.

## Resultado, decisões de 2015 a 2025

| Perfil | Regime | CAGR | vol | queda máx. | pior ano | Sharpe exc. |
|---|---|---:|---:|---:|---:|---:|
| Conservador | escada congelada | 12,72% | 8,9% | −19,23% | +0,92% | 0,408 |
| | + overlay | 11,66% | 7,0% | −9,78% | −1,10% | 0,328 |
| | + perna global | 13,10% | 7,7% | −16,79% | +4,35% | 0,512 |
| | ambos · global **dentro** | 12,31% | 5,9% | **−8,48%** | +1,33% | 0,482 |
| | ambos · global **fora** | 12,51% | 5,8% | −9,16% | +3,10% | **0,561** |
| Equilibrado | escada congelada | 15,38% | 15,2% | −29,77% | −4,90% | 0,432 |
| | + overlay | 14,38% | 12,5% | −18,94% | −1,97% | 0,406 |
| | + perna global | 15,86% | 13,1% | −26,84% | −4,90% | 0,507 |
| | ambos · global **dentro** | 15,13% | 10,7% | **−17,20%** | +1,06% | 0,511 |
| | ambos · global **fora** | 15,51% | 10,5% | −17,86% | +1,02% | **0,603** |
| Arrojado | escada congelada | 19,81% | 28,2% | −47,78% | −21,06% | 0,461 |
| | + overlay | 19,26% | 24,7% | −37,81% | −15,72% | 0,459 |
| | + perna global | 21,05% | 24,6% | −44,18% | −21,06% | 0,537 |
| | ambos · global **dentro** | 20,63% | 21,4% | −35,67% | −15,72% | 0,546 |
| | ambos · global **fora** | 20,74% | 20,4% | **−34,42%** | **−5,96%** | **0,617** |

## Leitura

**As camadas compõem.** Nenhuma anula a outra. A pilha completa melhora o Sharpe
do excesso sobre o CDI em relação à escada e em relação a cada camada isolada,
nos três perfis.

**Manter o fundo fora do overlay é melhor.** Pareado em risco, a variante "fora"
ganha em CAGR, em volatilidade e em Sharpe nos três perfis. A variante "dentro"
só entrega queda máxima um pouco menor no conservador e no equilibrado, e perde
até nisso no arrojado. A hipótese teórica se confirmou: vender o ativo não
correlacionado por causa de um sinal doméstico destrói parte do motivo de tê-lo.

**O ganho no arrojado é o mais expressivo.** O pior ano sai de −21,06% para
−5,96% e a queda máxima de −47,78% para −34,42%, com o CAGR **subindo** de
19,81% para 20,74%.

Contra a escada congelada, a pilha completa entrega:

| Perfil | Δ CAGR | Δ queda máxima | Δ Sharpe |
|---|---:|---:|---:|
| Conservador | −0,21 pp | **−10,1 pp** | +0,153 |
| Equilibrado | **+0,13 pp** | **−11,9 pp** | +0,171 |
| Arrojado | **+0,93 pp** | **−13,4 pp** | +0,156 |

Em dois dos três perfis o retorno sobe enquanto a queda máxima cai doze a treze
pontos. É o melhor resultado produzido por esta linha de pesquisa.

## Uma ressalva sobre o Sharpe

No conservador, o overlay **sozinho** reduz o Sharpe do excesso, de 0,408 para
0,328, ainda que corte a queda máxima pela metade. Isso não é contradição: o
Sharpe usa volatilidade, e o benefício do overlay está na cauda, não no desvio
padrão. Um perfil conservador avaliado só por Sharpe rejeitaria a proteção que
ele mais precisa. As duas métricas precisam aparecer juntas em qualquer tela.

## O que isto ainda não é

- **Retrospectivo.** As duas camadas foram desenhadas depois das crises presentes
  na amostra. O overlay reage com uma sessão de atraso e não previu a Covid-19.
- **Um terço do retorno do fundo veio do câmbio.** O IVVB11 rendeu 20,3% ao ano
  na janela enquanto o S&P 500 fez 11,8% em dólar e o dólar 6,6%. A perna é uma
  posição comprada em dólar sem hedge, e isso precisa estar escrito ao lado do
  número em qualquer tela.
- **O imposto intranual do overlay não é modelado.** Ele realiza ganho dentro do
  ano e isso ainda não é cobrado na série.
- **Escolher entre "dentro" e "fora" depois de ler esta tabela é uma seleção.**
  Ela precisa ser declarada como tal no registro da v2, com a contagem de
  tentativas atualizada — são duas variantes, não uma.

## Bloqueio remanescente

O `arrojado` da escada declara 95% em ações; o spec registrado em
`benevente_profile_risk_v1` declara 75%. As duas políticas registradas se
contradizem e uma delas precisa ser revogada explicitamente antes que a v2 possa
citar ambas.

## Reprodução

```powershell
.\.venv-benevente\Scripts\python.exe build_global_etf_panel.py
.\.venv-benevente\Scripts\python.exe profile_ladder.py --run
.\.venv-benevente\Scripts\python.exe research_ladder_v2.py
```

Saídas em `artifacts/ladder_v2_candidates/`.
