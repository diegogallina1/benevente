# Protocolo de acompanhamento diário 1.1.0

Registro: 02/09/2026. Substitui a versão 1.0.0, registrada em 23/08/2026
(SHA-256 15d6f7957c35baaf551f866e1f76998006d3443b908f8d2f6795846e0493f8cd),
que descrevia uma única carteira de cinco ações com 45% em CDI. O monitor
passou a seguir os quatro perfis da escada, e um protocolo que descreve outra
carteira não protege ninguém.

## Finalidade

Este protocolo marca a mercado, todo pregão, as quatro carteiras que a política
vigente (registro v4, 30/08/2026) teria montado em 02/01/2026 com os dados
daquele dia: ultraconservador, conservador, equilibrado e arrojado. Cada perfil
tem o seu arquivo de decisão (`web/current_decision_2026_<perfil>.json`) e a
sua série (`web/live_performance_<perfil>.json`). O arquivo
`web/live_performance.json` é o legado da carteira de janeiro e não representa
nenhum degrau da escada.

As quatro séries são reconstruções feitas em agosto de 2026: os três primeiros
perfis foram publicados pela primeira vez em 26/08/2026 e o quarto em
30/08/2026. Nenhum dado de 2026 escolheu ativo ou peso, mas nenhuma das
carteiras foi declarada antes do ano. O que este acompanhamento mede é o que a
regra teria feito, não o que alguém segurou.

## Regra imutável durante o ciclo

A cesta e os pesos de cada perfil estão no arquivo de decisão e não mudam até a
revisão anual. Cada carteira tem três pernas:

- **Doméstica**: ações da B3, avaliadas pela razão entre o fechamento ajustado
  da data e o fechamento ajustado de 02/01/2026.
- **Global**: a posição em IVVB11, marcada a mercado como qualquer outra, mas
  fora do alcance da camada de proteção (`overlay_exempt`).
- **Caixa**: evolui pelo produto das taxas diárias do CDI.

O Benevente 1 de cada perfil mantém os pesos de janeiro sem rebalanceamento. O
Benevente 2 aplica sobre a perna doméstica a camada de proteção registrada em
20/08/2026: queda do Ibovespa em relação ao pico de 126 pregões e volatilidade
de 20 pregões; alerta a 12% de queda ou 40% de volatilidade anualizada
(exposição doméstica limitada a 50% da base), severo a 22% ou 60% (limitada a
35%); sinal conhecido no fechamento só vale no pregão seguinte; dez pregões
mais calmos para voltar um nível; custo de 10 pontos-base por unidade
movimentada. O retorno diário do Benevente 2 é reconstruído por contribuição:
o CDI da sessão, mais o multiplicador vezes o excesso da perna doméstica sobre
o CDI, mais o excesso da perna global sobre o CDI, menos o custo do movimento.

O retorno publicado da perna de ações (`equity_sleeve_return`) divide o valor
das posições pelo peso somado das duas pernas que ele contém, doméstica e
global.

## Fontes e frequência

A rotina roda de segunda a sexta-feira às 23h10 no fuso America/Sao_Paulo. Os
fechamentos ajustados das ações, do IVVB11 e do BOVA11 vêm da interface pública
do Yahoo Finance, uma fonte secundária. O Ibovespa da mesma interface é índice
de preço. O CDI vem da série 12 do Sistema Gerenciador de Séries Temporais do
Banco Central do Brasil.

## Auditoria e falha segura

Cada resposta bruta recebe SHA-256. O documento publicado recebe um hash de
conteúdo e um hash de registro ligado ao registro anterior. Se uma série
estiver ausente, os pesos não somarem 100% ou não houver data comum, a rotina
falha e não publica números parciais. Se não houver dado novo, nenhum commit é
criado.

Um pregão em que algum papel não tem preço na fonte sai da série inteira. Isso
acontecia em silêncio; agora cada papel conta quantos pregões derrubou
(`data_quality.missing_tickers`) e o total de sessões perdidas vai junto
(`data_quality.dropped_sessions`). Zero é o esperado; qualquer outro número é
buraco no dado, não no mercado.

O histórico do Git preserva cada alteração. Como fechamentos ajustados podem
ser revistos pelo provedor após proventos ou eventos societários, os números
são provisórios até a conciliação integral com fontes primárias B3 e CVM.

## Limites

A rotina não seleciona ativos, não altera pesos, não envia ordens e não chama
modelo de linguagem. A atualização diária não transforma uma reconstrução de
agosto em evidência prospectiva: a primeira amostra confirmatória começa no
primeiro pregão de 2027, com a política declarada antes do ano. Qualquer
mudança neste protocolo exige nova versão, novo hash e nova fronteira temporal.
