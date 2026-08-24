# Reconciliação de eventos societários da B3

## Resultado da auditoria

Em 23/08/2026, a tentativa de reconciliação foi encerrada com status
`blocked_not_institutionally_reconciled`. Esse resultado é deliberado: a página
atual da B3 é uma fonte primária útil, mas uma resposta bem-sucedida não prova
que ela devolveu todo o histórico de eventos de uma ação.

A coleta consultou 389 emissores e 497 séries do painel de preços. A página
atual respondeu para 475 séries. Depois de excluir eventos anteriores ao
período efetivamente observado de cada código, o arquivo contém 9.772 registros
de proventos e alterações de capital, 127 subscrições e 153 eventos que exigem
tratamento manual. Vinte e dois códigos, sobretudo antigos ou deslistados, não
foram devolvidos pelo serviço atual.

O teste decisivo foi feito no escopo da estratégia publicada. O Benevente 1
possui 56 observações ativo-ano, formadas por 40 códigos distintos entre 2015 e
2025. Cinquenta e quatro puderam ser comparadas com uma reconstrução baseada em
fechamentos brutos do COTAHIST e nos eventos retornados pela página atual. Duas
observações de MRFG3 ficaram sem resposta do endpoint. Não houve subscrição,
cisão ou conversão manual durante os períodos em que os ativos estavam
efetivamente na carteira. Mesmo assim, sete das 54 comparações diferiram do
retorno ajustado publicado em mais de cinco pontos percentuais. A diferença
absoluta mediana foi de 0,14 ponto percentual, mas a média absoluta ponderada
pelo peso foi de 7,57 pontos percentuais, influenciada por eventos históricos
ausentes na resposta atual.

Esse resultado não demonstra que o provedor ajustado está correto em todos os
casos. Demonstra que o arquivo obtido na página atual da B3 não é suficiente
para certificá-lo retroativamente. Por isso, o painel permanece classificado
como dado público reproduzível para pesquisa, sem selo institucional de
reconciliação.

## Correção de um erro de contrato

A primeira versão do coletor chamava uma consulta respondida de cobertura
“completa”. Isso foi corrigido. O status atual é
`queried_current_endpoint`: ele registra que a página foi consultada, não que
todo o histórico foi recuperado. A rotina também deixou de deslocar para o
primeiro pregão do painel um evento ocorrido muitos anos antes. Esse erro
criava ajustes fictícios em códigos cujo histórico observado começava depois
do evento.

## Artefatos

- `data/b3_primary_corporate_events_2011_2025.csv`: eventos dentro do intervalo
  observado de cada série;
- `data/b3_primary_event_coverage_2011_2025.csv`: registro de resposta ou falha
  da página atual;
- `data/b3_primary_events_2011_2025_manifest.json`: hashes, contagens e estado
  do arquivo primário;
- `artifacts/primary_reconciliation/strategy_holding_year_audit.csv`: as 56
  comparações da estratégia publicada;
- `artifacts/primary_reconciliation/summary.json`: síntese e hashes de todas as
  entradas.

## O que seria necessário para um selo institucional

O nível `reconciled_primary_records` exige uma base histórica primária ou
licenciada que cubra todos os códigos e todo o período, inclusive eventos de
ações já deslistadas. Também exige o preço bruto, a resolução explícita de
direitos de subscrição e conversões, a aplicação de cada evento na primeira
sessão negociada depois da data com direito e um relatório que reconcilie cada
retorno. Enquanto qualquer uma dessas condições falhar, o adaptador deve
bloquear o selo.

Execução reproduzível:

```powershell
.\.venv-benevente\Scripts\python.exe b3_primary_events.py --resume
.\.venv-benevente\Scripts\python.exe tools/build_primary_reconciliation_audit.py
```
