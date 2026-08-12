# Comparação com fundos de gestão ativa

O Benevente permite comparar o resultado de pesquisa ou a carteira-sombra com
um fundo/classe específico pelo CNPJ informado pelo usuário. A fonte é o
**Informe Diário de Fundos** da CVM: cada registro contém a data de competência,
o valor da cota, patrimônio líquido, aplicações e resgates. A CVM mantém dados
recentes em arquivos mensais e histórico desde 2000.

## Regra de comparação

1. O usuário escolhe o CNPJ e um nome de exibição; a interface sugere, de forma
   editável, Dynamo Cougar FIF (`73.232.530/0001-39`).
2. O programa baixa e arquiva os ZIPs oficiais necessários, mas conserva apenas
   as linhas do CNPJ solicitado.
3. Para cada data de rebalanceamento do modelo, usa a última cota CVM publicada
   em ou antes daquela data.
4. A comparação começa somente na primeira data comum com cota válida e todas as
   séries são normalizadas para 100. Retorno acumulado, CAGR, volatilidade mensal
   anualizada e drawdown são recalculados nessa mesma janela.
5. URLs dos arquivos CVM, CNPJ, período e quantidade de observações entram nos
   metadados do artefato.

## Limites de interpretação

O fundo não é ``benchmark oficial'' nem recomendação. Um fundo pode possuir
taxa de administração/performance, carência, cotização, tributação, público-alvo
e mandato diferentes. A comparação mostra o desempenho histórico líquido da
cota publicada, mas não comprova replicabilidade nem prevê retorno futuro.

Fontes: [Informe Diário da CVM](https://dados.cvm.gov.br/dataset/fi-doc-inf_diario) e
[histórico de arquivos da CVM](https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/).
