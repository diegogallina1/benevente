# Protocolo de carteira-sombra de R$ 100 mil

Este protocolo mede uma decisão aprovada para frente. Não é backtest, não é
integração com corretora e não envia ordens. A carteira somente pode ser chamada
de **ativa** depois de uma proposta ter sido revisada por uma pessoa nomeada.

## Fluxo operacional

1. Gere a proposta com dados datados, política e custos arquivados.
2. Revise os pesos, a lâmina de ativos, os riscos e as instruções de ordem.
3. Caso haja aprovação humana, congele a política e `proposed_orders.csv` em um
   manifesto com SHA-256. Opcionalmente informe um fundo ativo pelo CNPJ para a
   comparação prospectiva.
4. Lance as ordens manualmente em um simulador ou corretora. O Benevente não
   transmite ordens.
5. Concilie a nota/exportação de execução com a proposta e registre o NAV
   observado junto com CDI, Ibovespa e, se escolhido, fundo ativo.

```powershell
python activate_shadow_portfolio.py `
  --policy data/my_policy.json `
  --proposed-orders artifacts/live_proposals/YYYY-MM-DD/proposed_orders.csv `
  --approved-by "Nome do responsável" `
  --active-fund-cnpj "73.232.530/0001-39" `
  --active-fund-name "Nome do fundo" `
  --output artifacts/pilot_100k/shadow_portfolio_activation.json

python broker_note_reconciler.py `
  --proposed-orders artifacts/live_proposals/YYYY-MM-DD/proposed_orders.csv `
  --executions data/my_executions.csv `
  --output artifacts/pilot_100k/reconciliation.csv

python pilot_tracker.py `
  --policy data/my_policy.json `
  --activation artifacts/pilot_100k/shadow_portfolio_activation.json `
  --nav data/my_pilot_nav.csv `
  --output artifacts/pilot_100k
```

Para evitar digitar a referência do fundo manualmente, é possível preencher a
coluna `active_fund_value_brl` nas mesmas datas do NAV com a última cota CVM
publicada em ou antes de cada data:

```powershell
python enrich_shadow_fund_nav.py `
  --nav data/my_pilot_nav.csv `
  --fund-cnpj "73.232.530/0001-39" `
  --output data/my_pilot_nav_with_fund.csv
```

O primeiro NAV deve ser exatamente a data e o valor da política. A referência de
fundo é opcional e não transforma o fundo em benchmark oficial: mandato,
tributação, cotização, taxa e liquidez podem ser diferentes. Retornos só passam
a existir a partir da data de ativação; nenhum resultado histórico é incorporado
à carteira-sombra.
