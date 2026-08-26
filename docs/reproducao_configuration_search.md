# Reprodução de `artifacts/configuration_search_2012/`

Este é o artefato que produz os números publicados no README e no artigo: CAGR
aninhado de 17,86%, Sharpe deflacionado de 0,9857 sobre 36 tentativas,
configuração final `eq55_n5_triple_factor`.

## O problema que este documento resolve

O artefato reproduz bit a bit, mas **só com a família de insumos certa**, e essa
família não estava escrita em lugar nenhum. A seção de reprodução do README
aponta para arquivos diferentes — `data/b3_historical_universes.csv`,
`data/fundamentals_b3_cvm_full_2013_2025_v2.csv`,
`data/prices_b3_total_return_full_2011_2025.csv` — que existem, rodam sem erro e
produzem um resultado **diferente e pior**: janela 2016–2025 em vez de
2015–2025, CAGR de 13,52% em vez de 17,86%.

Rodar com os arquivos errados não falha. Ele silenciosamente devolve outra coisa.
Foi exatamente assim que uma auditoria interna concluiu, por engano, que os
artefatos publicados não reproduziam.

O sintoma que denuncia a troca: o painel de preços que começa em 2011 não dá um
ano completo de janela anterior à decisão de janeiro de 2012, então a série
começa em 2013 em vez de 2012. **Se a primeira linha de
`configuration_annual_returns.csv` não for 2012, os insumos estão errados.**

## Comando que reproduz

```powershell
.\.venv-benevente\Scripts\python.exe research_configuration_search.py `
  --prices data/prices_b3_total_return_full_2010_2025.csv `
  --total-return-manifest data/prices_b3_total_return_full_2010_2025_manifest.json `
  --fundamentals data/fundamentals_b3_cvm_full_2012_2025.csv `
  --universe data/b3_historical_universes_2012_2025.csv `
  --mapping data/b3_historical_cvm_ticker_map_2012_2025.csv `
  --benchmarks data/benchmarks_market_2010_2025.csv `
  --start-year 2011 --end-year 2026 `
  --equity-budgets 0.55,0.75,0.95 `
  --asset-counts 5,8,12 `
  --factors value_quality,triple_factor,momentum_12m,low_volatility `
  --output artifacts/configuration_search_2012
```

Note `--start-year 2011`: a busca precisa de três anos encerrados antes de
escolher, então a primeira decisão avaliada é 2015 mesmo começando em 2011.

## Verificação feita em 25/08/2026

| Conferência | Resultado |
|---|---|
| Anos da série | 2012–2025, idênticos ao arquivado |
| Retornos anuais das 36 configurações | diferença máxima de 5,55 × 10⁻¹⁷ |
| `summary.json` | idêntico campo a campo |
| `nested_selection_annual.csv` | idêntico |

A diferença é precisão de ponto flutuante, não recálculo. **Os números
publicados são reprodutíveis.**

## O que ainda não é

Reprodutibilidade não é validação. A janela 2015–2025 continua sendo amostra de
desenvolvimento: a grade, a família de fatores e as restrições foram escolhidas
olhando para ela. Reproduzir o cálculo confirma que o software é determinístico e
que o artefato corresponde ao código — não que a regra funcione fora da amostra.

## Recomendação

O `build_release_manifest.py` confere o hash das **saídas**. Ele não confere que
as saídas venham das entradas declaradas, que é precisamente o furo por onde este
engano passou. Vale acrescentar ao manifesto o conjunto de insumos de cada
artefato, com os respectivos hashes, para que a reprodução seja verificável sem
adivinhação.
