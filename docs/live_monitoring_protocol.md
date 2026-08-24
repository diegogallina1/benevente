# Protocolo de acompanhamento diário 1.0.0

Registro: 23/08/2026

## Finalidade

Este protocolo acompanha a carteira decidida em 02/01/2026 sem modificar os
ativos escolhidos. Ele mede o Benevente 1, o Benevente 2, CDI, BOVA11 e
Ibovespa. O resultado é uma carteira-sombra e não uma validação prospectiva da
regra de seleção, que foi refinada durante 2026.

## Regra imutável durante o ciclo

- VIVA3: 17,60%
- CURY3: 16,6174385588229%
- CMIN3: 11,978639787599599%
- BBSE3: 6,51209233899438%
- LEVE3: 2,291829314583127%
- CDI: 45,00%

No Benevente 1 não há rebalanceamento intranual. Cada ação evolui pela razão entre o fechamento
ajustado da data e o fechamento ajustado inicial. O CDI evolui pelo produto das
taxas diárias oficiais. O valor da carteira é a soma das seis parcelas.

O Benevente 2 mantém os cinco ativos. Ele observa a queda do Ibovespa em relação
ao pico de 126 pregões e a volatilidade de 20 pregões. Um sinal conhecido no
fechamento só vale no pregão seguinte. Em alerta, definido por queda de 12% ou
volatilidade anualizada de 40%, a exposição a ações fica limitada a 50%. Em
estado severo, definido por queda de 22% ou volatilidade de 60%, fica limitada
a 35%. O retorno ao nível anterior exige dez pregões mais calmos. Cada alteração
de exposição recebe custo de 10 pontos-base por unidade movimentada.

A regra foi registrada em 20/08/2026. A trajetória do Benevente 2 entre janeiro
e essa data é reconstrução retrospectiva; somente as observações posteriores
compõem seu acompanhamento versionado.

## Fontes e frequência

A rotina roda de segunda a sexta-feira às 23h10 no fuso America/Sao_Paulo. Os
fechamentos ajustados das ações e do BOVA11 vêm da interface pública do Yahoo
Finance, uma fonte secundária. O Ibovespa da mesma interface é índice de preço.
O CDI vem da série 12 do Sistema Gerenciador de Séries Temporais do Banco
Central do Brasil.

## Auditoria e falha segura

Cada resposta bruta recebe SHA-256. O documento publicado recebe um hash de
conteúdo e um hash de registro ligado ao registro anterior. Se uma série estiver
ausente, os pesos não somarem 100% ou não houver data comum, a rotina falha e não
publica números parciais. Se não houver dado novo, nenhum commit é criado.

O histórico do Git preserva cada alteração. Como fechamentos ajustados podem ser
revistos pelo provedor após proventos ou eventos societários, os números são
provisórios até a conciliação integral com fontes primárias B3 e CVM.

## Limites

A rotina não seleciona ativos, não altera pesos, não envia ordens e não chama
modelo de linguagem. A atualização diária não transforma a decisão de janeiro
de 2026 em evidência prospectiva. Qualquer mudança neste protocolo exige nova
versão, novo hash e nova fronteira temporal.
