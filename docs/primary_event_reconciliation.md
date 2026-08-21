# Reconciliação de eventos societários da B3

Em 20/08/2026, o Benevente passou a arquivar diretamente dois registros públicos da B3: o histórico paginado de proventos em dinheiro e o cadastro suplementar da companhia, que contém desdobramentos, grupamentos, bonificações e subscrições. A coleta é executada por `b3_primary_events.py` e produz três arquivos versionados:

- `data/b3_primary_corporate_events_2011_2025.csv`;
- `data/b3_primary_event_coverage_2011_2025.csv`;
- `data/b3_primary_events_2011_2025_manifest.json`.

A primeira varredura consultou 389 emissores e 497 ativos presentes no painel de preços. Foram arquivados 18.190 eventos. A consulta atual da B3 forneceu cobertura completa para 475 ativos. Vinte e dois códigos ficaram sem cobertura, principalmente códigos antigos ou deslistados que já não são devolvidos pela página atual. O arquivo também registra 218 subscrições e 53 cisões, incorporações ou restituições em ações ainda sem resolução.

O arquivo não certifica retroativamente a série ajustada já usada no backtest. Para obter o nível `reconciled_primary_records`, o procedimento exige preço de fechamento bruto, cobertura completa para cada ticker e cada dia da janela, fonte oficial, ausência de duplicatas, resolução explícita de subscrições e conversões, aplicação de cada evento na primeira sessão negociada depois da data com direito e igualdade dos hashes do arquivo de eventos, do livro de cobertura e do relatório de aplicação. O adaptador bloqueia o selo se qualquer uma dessas condições falhar.

Execução:

```powershell
.\.venv-benevente\Scripts\python.exe b3_primary_events.py
.\.venv-benevente\Scripts\python.exe b3_primary_events.py --resume
```

O segundo comando consulta apenas os ativos cuja cobertura não foi concluída. Falha de consulta permanece no livro com o motivo e não é convertida em “nenhum evento”.
