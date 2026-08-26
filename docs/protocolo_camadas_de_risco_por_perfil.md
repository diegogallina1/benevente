# Protocolo — camadas de risco sobre a escada congelada

Estado: **diagnóstico concluído**. Uma camada é recomendada, a outra é
recomendada para remoção. Nada foi alterado na escada registrada.

## Problema

A escada `benevente_profile_ladder_v1` revisa uma vez por ano. Em 2013–2025 o
perfil conservador teve pior **ano-calendário** de +0,92% e pior **queda** de
−19,23%. O segundo número é o que o investidor vive, e nenhum protocolo anual o
melhora sozinho: a cesta está congelada durante o ano inteiro.

Duas camadas separadas poderiam agir. Elas foram medidas contra a mesma escada.

## Camada 1 — meta de volatilidade anual (janeiro)

Dimensiona o sleeve na decisão de janeiro, a partir da volatilidade observada
até ali. É a camada que comprimia os perfis publicados.

**Resultado: custo sem benefício.** No conservador ela reduziu o CAGR de 11,98%
para 10,86% e deixou a queda máxima **exatamente igual**, em −19,23%.

O motivo aparece na exposição decidida ano a ano:

| Janeiro | sem camada | com meta de vol | corte |
|---|---:|---:|---:|
| 2016 | 35,0% | 8,8% | −26,3pp |
| 2017 | 35,0% | 27,2% | −7,8pp |
| **2020** | **35,0%** | **35,0%** | **0,0pp** |
| 2021 | 35,0% | 20,8% | −14,2pp |
| 2022 | 35,0% | 25,7% | −9,3pp |
| 2025 | 35,0% | 19,3% | −15,8pp |

Ela cortou em 5 dos 13 anos, sempre **depois** de um episódio de estresse e
nunca antes de um. Em janeiro de 2020 o mercado estava calmo, a camada não
cortou nada, e a queda de março de 2020 atingiu o livro com exposição cheia. A
pior queda das duas séries acontece no mesmo dia, 23/03/2020, com o mesmo valor.

Em 2016 o corte foi de 35% para 8,8% num ano em que a estratégia rendeu +35%.
A camada não erra por acaso: volatilidade passada alta é justamente o que
costuma preceder um ano de recuperação.

## Camada 2 — overlay intranual

Observa o estresse do Ibovespa no fechamento anterior e desloca parte do sleeve
para o CDI, com uma sessão de atraso. Nunca troca um ativo dentro do ano.

| Perfil | regime | CAGR | vol | queda máxima |
|---|---|---:|---:|---:|
| conservador | escada | 11,98% | 8,7% | −19,23% |
| conservador | **+ overlay** | 10,98% | 6,6% | **−9,78%** |
| equilibrado | escada | 14,39% | 14,8% | −29,77% |
| equilibrado | **+ overlay** | 13,35% | 12,0% | **−18,94%** |
| arrojado | escada | 18,33% | 27,3% | −47,78% |
| arrojado | **+ overlay** | 17,71% | 23,7% | **−39,28%** |

A troca é boa nos três: de 8,5 a 10,8 pontos percentuais de queda a menos por
cerca de 1 ponto percentual de CAGR ao ano. Para comparação, o peso inverso à
volatilidade testado em `protocolo_esquema_de_peso.md` comprou 0,95 ponto de
queda por 2,11 pontos de retorno — dez vezes pior.

## Piso de exposição

`RiskProfileSpec.minimum_equity_fraction_of_cap` foi implementado: a meta de
volatilidade não pode cortar abaixo de uma fração do teto declarado, enquanto o
estresse observável continua podendo. Padrão zero, então a política registrada
`benevente_profile_risk_v1` não muda.

Com piso de 60% ele **não morde** na escada: a exposição média do conservador já
é 29,4%, acima do piso de 21%. A compressão que motivou o piso (54%, 65% e 78%
dos tetos) foi medida nos perfis antigos, de cinco nomes. A cesta larga da
escada já a resolveu em boa parte — o conservador de doze nomes mantém 83,9% do
teto, porque um sleeve mais diversificado tem volatilidade menor e a meta corta
menos. O piso permanece disponível e testado, mas o problema que ele resolvia
encolheu sozinho.

## Recomendação

Adotar o overlay intranual nos três perfis e **não** adotar a meta de
volatilidade anual. O piso deixa de ser necessário se a meta de vol não for
usada.

Isso exige nova versão do registro da escada, com a contagem de tentativas
atualizada. Nada foi alterado até aqui.

## Conflito de política a resolver

O `arrojado` da escada declara 95% em ações; o spec registrado em
`benevente_profile_risk_v1` declara 75%. As duas políticas não podem ser
combinadas sem decidir qual governa, então a medição da camada anual devolve
"não combinável" para esse perfil em vez de deixar uma sobrescrever a outra em
silêncio. O overlay não tem esse conflito: ele usa apenas os multiplicadores de
alerta e severo.

## Limites

Ambas as camadas foram desenhadas depois das crises presentes na amostra. O
overlay não previu a Covid-19 e reage com uma sessão de atraso; seu resultado em
2020 não é evidência prospectiva. O imposto sobre o ganho realizado pelo overlay
dentro do ano ainda não é modelado, e ele gira exposição — 10,3 a 12,2 unidades
de giro acumulado em treze anos, com custo de 10 bps por unidade já cobrado.

## Reprodução

```powershell
.\.venv-benevente\Scripts\python.exe profile_ladder.py --run
.\.venv-benevente\Scripts\python.exe research_profile_risk_layers.py
.\.venv-benevente\Scripts\python.exe -m pytest tests/test_portfolio_risk.py -q
```

Saídas em `artifacts/profile_risk_layers_v1/`.
