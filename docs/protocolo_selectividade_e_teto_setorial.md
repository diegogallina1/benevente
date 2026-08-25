# Protocolo — seletividade proporcional e teto por setor

Estado: **pesquisa**. As duas regras abaixo existem no motor, têm teste e são
reprodutíveis, mas não foram pré-registradas antes de olhar a janela
2013–2025. Nenhuma delas pode receber alegação de desempenho enquanto não
houver anos avaliados depois de um registro congelado.

## Problema

`top_assets` era uma contagem fixa. Uma cesta de vinte emissores era 74% de
tudo que passou na triagem de janeiro de 2016 e 21% da de 2025. Um número
constante, portanto, muda silenciosamente *o que a regra é* ao longo da
amostra: no começo ela compra quase o universo elegível e no fim ela seleciona
de verdade. Comparar os dois extremos como se fossem a mesma estratégia não é
comparável.

O segundo problema é de exposição. O ranking do fator triplo não sabe o que é
setor. Em 2022 a cesta proporcional colocou cinco dos treze nomes no mesmo
setor da CVM. Isso é uma aposta setorial que ninguém declarou.

## Regras

**Seletividade proporcional.** Quando `top_assets_universe_fraction` está
definida, o número de posições da decisão de janeiro é

    N = clip(round(fraction x elegíveis), top_assets_minimum, top_assets)

O total de elegíveis vem da triagem datada daquele mesmo janeiro, antes do teto
setorial remover qualquer nome — senão o teto encolheria a contagem e a
contagem encolheria a cesta duas vezes pelo mesmo motivo. `top_assets` passa a
ser o teto e `top_assets_minimum` o piso. Com a fração ausente o motor
reproduz a contagem fixa publicada, byte a byte; há teste para isso.

**Teto por setor.** `maximum_names_per_sector` limita quantos emissores da
cesta podem vir de um setor da CVM. O corte respeita o ranking: só sai o pior
colocado de um setor já cheio, e a vaga vai para o melhor colocado de um setor
com espaço. O tamanho da cesta não muda.

O rótulo setorial da CVM tem duas formas para a mesma exposição econômica — a
operacional e a holding que a controla (`Emp. Adm. Part. - Energia Elétrica`).
`sector_group` remove o prefixo e reconcilia as duas abreviações divergentes,
reduzindo 49 rótulos observados a 29 setores. `Sem Setor Principal` não é um
setor: é o registro se recusando a classificar. Cada emissor não classificado
fica com um balde próprio e é contado em `unclassified_sector_positions`, em
vez de ser tratado como diversificação que ninguém verificou.

## Observado em 2013–2025 (fator triplo, 55% em ações)

| Regra | CAGR | pior ano | giro médio | posições 2013 → 2025 | setores 2025 |
|---|---:|---:|---:|---:|---:|
| n5 publicada | 16,35% | −7,87% | 0,59 | 5 → 5 | 5 |
| n5 + teto setorial 3 | 16,35% | −7,87% | 0,59 | 5 → 5 | 5 |
| f15 proporcional | 15,11% | −8,49% | 0,57 | 5 → 14 | 10 |
| f15 + teto setorial 3 | 14,98% | −8,49% | 0,57 | 5 → 14 | 10 |

Leitura honesta: a cesta proporcional quase triplicou o número de emissores e
dobrou o número de setores **sem aumentar o giro**, e cobrou 1,24 ponto
percentual de CAGR por isso. Ela não melhorou o pior ano nesta janela — a
diversificação comprou variedade, não proteção. O teto setorial só se tornou
ativo na cesta larga (2022 e 2023) e custou mais 0,13 ponto percentual.

Nenhum desses números é evidência prospectiva. A janela inteira é amostra de
desenvolvimento.

## Alcance da mudança

As duas regras atuam na seleção do fator triplo. Os fatores `value_quality`,
`momentum_12m` e `low_volatility` seguem pelo otimizador convexo, onde a
contagem de posições nunca foi um parâmetro explícito — nesses caminhos o
número de nomes é consequência do teto por emissor. Uma cesta proporcional
para eles exigiria mudar o alocador, não a seleção.

## Reprodução

```powershell
.\.venv-benevente\Scripts\python.exe -m pytest tests/test_annual_walk_forward.py -q
```

Campos de protocolo: `top_assets_universe_fraction`, `top_assets_minimum`,
`maximum_names_per_sector`. Colunas novas em `annual_results.csv`:
`equity_positions`, `distinct_sectors`, `largest_sector_positions`,
`unclassified_sector_positions`.
