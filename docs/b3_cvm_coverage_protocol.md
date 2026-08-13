# Cobertura histórica B3–CVM

O arquivo COTAHIST da B3 identifica o instrumento negociado e a CVM identifica a companhia reportante por CNPJ. A ligação entre os dois não é um dado implícito: nomes abreviados, mudanças societárias, cancelamentos e mais de uma classe de ação tornam uma junção textual simples inadequada para um backtest.

## Regra de aceitação

`build_b3_cvm_mapping.py` aceita automaticamente apenas um nome normalizado exato ou um prefixo COTAHIST único e suficientemente discriminativo. Todo outro resultado recebe `review_required`. A promoção de uma linha exige um registro em `data/b3_cvm_manual_overrides_template.csv` copiado para uma tabela de trabalho com revisor, data e justificativa.

```powershell
.\.venv-benevente\Scripts\python.exe build_b3_cvm_mapping.py `
  --universe artifacts/b3_universe_2026-08-12.csv `
  --cvm-master work/cvm_company_master.csv `
  --manual-overrides data/b3_cvm_manual_overrides.csv `
  --output data/b3_cvm_ticker_map.csv `
  --coverage-report artifacts/b3_cvm_mapping_coverage.csv
```

O mapa é apenas o primeiro portão. Para cada janeiro histórico, o estudo ainda precisa: (1) universo COTAHIST daquele ano, para evitar viés de sobrevivência; (2) preços e liquidez anteriores à decisão; (3) capitalização datada; (4) ITR/DFP disponível até a data; (5) tratamento de sucessões, deslistagens, cisões e tickers substituídos. Linhas sem todos esses artefatos ficam bloqueadas, e não são preenchidas com dados atuais.

Portanto, o resultado inicial de 8 emissores não deve ser apresentado como cobertura integral da B3. O relatório de cobertura registra quanto do universo está apenas descoberto, mapeado, revisado e apto para ingestão contábil.
