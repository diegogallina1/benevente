# Integração do ITR recente da CVM

## Fonte oficial

O arquivo anual compactado é publicado pela CVM em:

`https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/itr_cia_aberta_AAAA.zip`

O Benevente baixa o ZIP correspondente a `--itr-year`, guarda-o em `work/cvm_cache/` e lê os arquivos consolidados `DRE_con`, `BPA_con`, `BPP_con`, `DFC_MI_con` e o índice `itr_cia_aberta_AAAA.csv`. O índice fornece `DT_REFER`, `VERSAO` e `DT_RECEB`.

## Regra ponto-no-tempo

Para uma data de decisão $D$, por emissor, somente pode ser usado o ITR cuja `DT_RECEB <= D`. Entre as versões elegíveis, o sistema escolhe a maior `DT_REFER`, seguida pela maior versão. Portanto, empresas que ainda não entregaram o segundo trimestre continuam no primeiro trimestre; não há preenchimento artificial.

Para evitar tratar um trimestre como resultado anual, as rubricas de resultado e fluxo de caixa usam:

`TTM = DFP anual anterior + ITR atual (ÚLTIMO) − ITR comparativo (PENÚLTIMO)`.

O balanço usa o valor `ÚLTIMO` no `DT_REFER` do ITR. O arquivo final registra tanto `as_of_date` quanto `available_date` para auditoria e futuros testes ponto-no-tempo.

## Dados de mercado

O ITR não substitui a cotação e a liquidez de mercado. Antes da proposta, copie `data/market_snapshot_template.csv`, preencha os oito ativos com dados extraídos da B3, da nota/plataforma da corretora ou de fornecedor licenciado e indique a fonte. O snapshot precisa ser anterior ou igual à data de decisão, ter menos dias que o limite da política e é copiado para os artefatos da proposta.

## Comando

```powershell
Copy-Item data/pilot_100k_policy.json data/my_pilot_100k_policy.json
Copy-Item data/market_snapshot_template.csv data/my_market_snapshot.csv
# preencher o perfil, os campos avançados se desejado, a confirmação explícita e o snapshot
python live_proposal_runner.py --policy data/my_pilot_100k_policy.json --itr-year 2026 --market-snapshot data/my_market_snapshot.csv --decision-date 2026-08-12
```

A rotina cria uma proposta para revisão humana; não envia ordem. O ITR 2026 é disponibilizado publicamente pela CVM, com atualizações periódicas: <https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/>.
