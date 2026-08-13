# Retorno total público reproduzível: brapi + CDI BCB

O Benevente baixa `adjustedClose` da brapi para pesquisa e arquiva, por ticker,
a resposta bruta de preços e eventos: dividendos, JCP, bonificações,
desdobramentos, grupamentos e subscrições. O CDI vem da série 12 do SGS do
Banco Central do Brasil e também é arquivado. O processo grava CSV, relatório
de cobertura e manifesto com SHA-256.

## Chave da brapi

O modo público da brapi permite somente PETR4, VALE3, ITUB4 e MGLU3. Para a
cobertura completa do painel B3, crie uma chave no dashboard da brapi e
acrescente esta linha em `.env.local` (arquivo já ignorado pelo Git):

```text
BRAPI_TOKEN=cole_a_chave_aqui
```

Não coloque a chave no código, em CSV, em `data/`, no site ou em commits. A
requisição envia o token apenas no header `Authorization`.

## Construção e uso

```powershell
.\.venv-benevente\Scripts\python.exe brapi_total_return.py `
  --fundamentals data/fundamentals_b3_cvm_full_2013_2025.csv `
  --start 2013-01-01 --end 2025-12-31 `
  --output data/prices_brapi_adjusted_total_return_2013_2025.csv `
  --manifest data/brapi_adjusted_total_return_2013_2025_manifest.json `
  --coverage-report artifacts/brapi_adjusted_total_return_coverage.csv

.\.venv-benevente\Scripts\python.exe annual_walk_forward.py `
  --prices data/prices_brapi_adjusted_total_return_2013_2025.csv `
  --total-return-manifest data/brapi_adjusted_total_return_2013_2025_manifest.json `
  --fundamentals data/fundamentals_b3_cvm_full_2013_2025.csv `
  --universe data/b3_historical_universes.csv `
  --mapping data/b3_historical_cvm_ticker_map.csv `
  --start-year 2013 --end-year 2026 --price-basis total_return `
  --adaptive-factors --risk-profile moderado `
  --output artifacts/annual_brapi_2013_2025
```

## Limite de interpretação

Esta fonte é **pública e reproduzível**, não uma certificação B3. O manifesto
marca essa condição e guarda o diretório de respostas brutas. Antes de usar o
resultado em alegação institucional, comercial ou no artigo como evidência
definitiva, concilie uma amostra de eventos com registros primários B3/CVM e
documente a diferença, se houver.
