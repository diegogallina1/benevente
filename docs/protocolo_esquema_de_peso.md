# Protocolo — esquema de peso do sleeve de ações

Estado: **diagnóstico concluído, sem mudança de regra**. A hipótese foi
testada e rejeitada. A regra publicada permanece.

## Hipótese

Toda configuração já pesquisada neste repositório dimensionou o livro de uma
única forma: proporcional à confiança do fator (`score`). Isso nunca foi
comparado com alternativa nenhuma — era uma escolha, não um resultado.

A hipótese era que peso proporcional ao score prejudica a cesta larga, porque
coloca a maior posição no nome que o fator mais gosta sem olhar quanto esse
nome se move; e que peso inverso à volatilidade deveria ganhar justamente
onde há mais nomes para equilibrar.

## Desenho

Seleção mantida fixa. Só muda o dimensionamento, entre quatro esquemas:

- `score` — proporcional à confiança do fator (regra publicada);
- `equal` — pesos iguais;
- `inverse_volatility` — inverso da volatilidade anualizada de 12 meses,
  lida da mesma janela que a triagem já usa, encerrada antes da data de
  decisão;
- `inverse_volatility_score` — média geométrica dos dois.

Volatilidade ausente herda a maior observada, para que um dado faltante nunca
vire posição grande por omissão. Há piso de 5% ao ano na volatilidade: um papel
com movimento quase nulo em doze meses é artefato de dado, não ativo sem risco,
e sem o piso o inverso levaria o sleeve inteiro.

Oito configurações: os três perfis da escada congelada e cinco tamanhos de
cesta (5, 8, 12, 16, 20) a 55% em ações. Janela 2013–2025.

## Resultado

| Esquema | vence `score` em CAGR | em Sharpe | Δ CAGR médio | Δ Sharpe | Δ drawdown |
|---|---:|---:|---:|---:|---:|
| `equal` | 0 de 8 | 0 de 8 | −1,67% | −0,097 | −0,19pp |
| `inverse_volatility` | 0 de 8 | 0 de 8 | −2,11% | −0,112 | +0,95pp |
| `inverse_volatility_score` | 0 de 8 | 2 de 8 | −0,50% | −0,018 | +0,12pp |

**A hipótese foi rejeitada em todas as oito configurações.** O peso inverso à
volatilidade comprou 0,95 ponto percentual de drawdown ao custo de 2,11 pontos
percentuais de retorno ao ano. É uma troca ruim em qualquer perfil.

A previsão específica também falhou. O ganho deveria crescer com o tamanho da
cesta e ocorreu o contrário: a 5 nomes o inverso da volatilidade entrega 59%
do Sharpe do `score`, e a 20 nomes entrega 46%. Pior ainda, na cesta larga ele
**piora** o pior ano — em 16 nomes o pior ano vai de +0,50% para −3,10%, e em
20 nomes de −1,06% para −5,78%.

A leitura mais provável é que a confiança do fator triplo carrega informação de
retorno que o inverso da volatilidade descarta, e que descartá-la custa mais do
que o equilíbrio de risco devolve. O `low_volatility` como *fator* já havia
ficado em último lugar na busca de configurações (Sharpe 0,293 contra 0,645 do
fator triplo); este teste mostra que a volatilidade também não ajuda como
*dimensionador*.

## Consequência

Nenhuma. A escada `benevente_profile_ladder_v1` permanece como registrada, com
`weighting = "score"`. O valor deste experimento é negativo no resultado e
positivo no método: o dimensionamento deixou de ser suposição não testada.

Adotar qualquer esquema alternativo multiplicaria o espaço de candidatos por
quatro e exigiria novo registro com a contagem de tentativas atualizada. Como
nenhum venceu, isso não é necessário.

## Reprodução

```powershell
.\.venv-benevente\Scripts\python.exe research_weighting_scheme.py
.\.venv-benevente\Scripts\python.exe -m pytest tests/test_annual_walk_forward.py -q
```

Saídas em `artifacts/weighting_scheme_v1/`: `ladder_by_weighting.csv`,
`basket_size_by_weighting.csv`, `marginal_effect_vs_score.csv`.

## Limite

As oito configurações compartilham dados e boa parte das posições, então não
são amostras independentes: o placar de 8 a 0 descreve consistência, não
significância estatística. A janela inteira é amostra de desenvolvimento.
