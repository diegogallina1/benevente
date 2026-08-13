# Cobertura histórica B3–CVM

O arquivo COTAHIST da B3 identifica o instrumento negociado e a CVM identifica a companhia reportante por CNPJ. A ligação entre os dois não é um dado implícito: nomes abreviados, mudanças societárias, cancelamentos e mais de uma classe de ação tornam uma junção textual simples inadequada para um backtest.

## Universos anuais, não universo atual

Antes de mapear CNPJ, o estudo deve criar uma fotografia de cada janeiro a partir do COTAHIST daquele próprio ano. Isto evita usar a lista de 2026 para decidir 2013. O endpoint oficial da B3 é usado apenas para baixar o arquivo histórico; a rotina preserva o ZIP local e bloqueia o ano que não puder ser obtido.

```powershell
.\.venv-benevente\Scripts\python.exe build_historical_b3_universes.py `
  --start-year 2013 --end-year 2025 --download `
  --output data/b3_historical_universes.csv `
  --coverage-report artifacts/b3_historical_universe_coverage.csv
```

## Regra de aceitação

`build_b3_cvm_mapping.py` prioriza a ponte oficial da B3 entre ISIN e CNPJ, baixada na seção **Banco de Dados Completo** da página de códigos ISIN. Para ISIN que não constar no arquivo vigente, aceita somente um prefixo de emissor que seja único na mesma base oficial B3 e exista no cadastro CVM; por fim, aceita nome CVM normalizado exato ou prefixo COTAHIST único e suficientemente discriminativo. Todo outro resultado recebe `review_required`. A promoção de uma linha exige um registro em `data/b3_cvm_manual_overrides_template.csv` copiado para uma tabela de trabalho com revisor, data e justificativa.

```powershell
.\.venv-benevente\Scripts\python.exe build_b3_cvm_mapping.py `
  --universe artifacts/b3_universe_2026-08-12.csv `
  --cvm-master work/cvm_company_master.csv `
  --b3-isin-dir work/b3_isin_complete `
  --manual-overrides data/b3_cvm_manual_overrides.csv `
  --output data/b3_cvm_ticker_map.csv `
  --coverage-report artifacts/b3_cvm_mapping_coverage.csv
```

O mapa é apenas o segundo portão. Para cada janeiro histórico, o estudo ainda precisa: (1) preços e liquidez anteriores à decisão; (2) capitalização datada; (3) ITR/DFP disponível até a data; (4) tratamento de sucessões, deslistagens, cisões e tickers substituídos. Linhas sem todos esses artefatos ficam bloqueadas, e não são preenchidas com dados atuais.

## Painel fundamental B3--CVM completo

`build_full_b3_cvm_fundamentals.py` executa o terceiro portão para cada ação aceita: preço e liquidez no COTAHIST de janeiro, quantidade de ações no FRE cuja recepção seja anterior à decisão e ITR/DFP já publicado. A capitalização é `preço B3 × quantidade de ações FRE`; portanto, não há uso de capitalização atual nem de Yahoo Finance no painel completo. Unidades e classes preferenciais cuja quantidade não puder ser isolada no FRE ficam bloqueadas.

```powershell
.\.venv-benevente\Scripts\python.exe build_full_b3_cvm_fundamentals.py `
  --universe data/b3_historical_universes.csv `
  --mapping data/b3_historical_cvm_ticker_map.csv `
  --start-year 2013 --end-year 2025 `
  --cache-dir work/cvm_cache `
  --output data/fundamentals_b3_cvm_full.csv `
  --coverage-report artifacts/fundamentals_b3_cvm_full_coverage.csv
```

O relatório de cobertura é parte do resultado: somente as linhas `accepted` podem alimentar o estudo posterior. O construtor não roda o backtest, não escolhe pesos e não altera o modelo.

Ao processar por faixas, consolide os checkpoints e publique a tabela anual:

```powershell
.\.venv-benevente\Scripts\python.exe consolidate_b3_cvm_coverage.py `
  --panel data/fundamentals_b3_cvm_full_2013_2015.csv `
  --panel data/fundamentals_b3_cvm_full_2016_2018.csv `
  --panel data/fundamentals_b3_cvm_full_2019_2021.csv `
  --panel data/fundamentals_b3_cvm_full_2022_2024.csv `
  --panel data/fundamentals_b3_cvm_full_2025.csv `
  --coverage artifacts/fundamentals_b3_cvm_full_2013_2015_coverage.csv `
  --coverage artifacts/fundamentals_b3_cvm_full_2016_2018_coverage.csv `
  --coverage artifacts/fundamentals_b3_cvm_full_2019_2021_coverage.csv `
  --coverage artifacts/fundamentals_b3_cvm_full_2022_2024_coverage.csv `
  --coverage artifacts/fundamentals_b3_cvm_full_2025_coverage.csv `
  --universe data/b3_historical_universes.csv `
  --mapping data/b3_historical_cvm_ticker_map.csv
```

Portanto, o resultado inicial de 8 emissores não deve ser apresentado como cobertura integral da B3. O relatório de cobertura registra quanto do universo está apenas descoberto, mapeado, revisado e apto para ingestão contábil.
