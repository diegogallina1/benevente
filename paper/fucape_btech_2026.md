# Benevente Wealth System: um artefato de decisão e governança de carteira para escritórios de investimento do Espírito Santo

**Produção técnica. Fucape Business School, BTech 2026.**

---

## Resumo

Escritórios de investimento capixabas, entre multi-family offices, consultorias de valores mobiliários e assessorias, recomendam carteiras que precisam ser justificadas meses depois de montadas, diante do cliente, do compliance ou do regulador. Três perguntas voltam sempre: quais dados existiam na data da decisão, qual regra foi aplicada sobre eles, e quem aprovou. Planilha não responde nenhuma. Plataforma de terceiro responde a segunda de forma opaca. Este trabalho descreve o Benevente Wealth System, um artefato de software que produz a recomendação e a trilha de auditoria no mesmo ato. Cada decisão anual sai acompanhada da política vigente, dos fundamentos da CVM com data de recebimento, da tela de elegibilidade com o motivo de cada reprovação, dos pesos, das ordens propostas com lote e participação no volume, do custo estimado, e do SHA-256 de cada arquivo que gerou cada número. O artefato foi avaliado em uma janela de onze decisões anuais, de 2015 a 2025, sobre um painel da B3 construído a partir do arquivo histórico de cotações, que retém os 166 emissores deslistados no período. A carteira publicada rendeu 17,86% ao ano após custos, ou 16,03% após imposto de renda, contra 11,77% do Ibovespa, 9,61% do CDI e 7,83% de uma otimização média-variância independente sobre o mesmo universo elegível. Venceu o mercado em sete dos onze anos e a otimização neutra em dez. Reportamos também o que não funcionou: previsão anual de regime, realocação mensal e semanal, e o uso de um modelo de linguagem como fonte de retorno. As três hipóteses foram testadas com poder adequado e rejeitadas, e os resultados negativos são publicados junto com o positivo. A contribuição tecnológica não é a rentabilidade. É o conjunto de mecanismos que torna essa rentabilidade auditável, incluindo a medição explícita de quanto do resultado viria de escolher a regra depois de conhecer o desfecho: 0,65 ponto percentual ao ano.

**Palavras-chave:** governança de investimentos; trilha de auditoria; alocação de carteira; dados datados; viés de sobrevivência; pesquisa reprodutível.

---

## 1. Situação-problema

O Espírito Santo concentra patrimônio relevante e quase nenhuma infraestrutura de decisão de investimento. Famílias e empresas capixabas mandam capital para gestoras do Rio de Janeiro e de São Paulo, e o escritório local fica com o relacionamento e sem o processo. A causa não é falta de competência analítica. É falta de ferramenta que produza, no ato da recomendação, o registro que a recomendação vai exigir depois.

O problema é concreto e tem data. Quando um cliente pergunta em 2026 por que determinada ação entrou na carteira em janeiro de 2023, o escritório precisa demonstrar três coisas simultaneamente.

1. **Quais dados existiam naquela data.** Um balanço republicado em 2024 não pode aparecer como se estivesse disponível em janeiro de 2023. Sem controle de data de recebimento, todo backtest e toda justificativa ficam contaminados por informação que ninguém tinha.
2. **Qual regra foi aplicada.** Não a regra que o escritório usa hoje, mas a que estava vigente naquele janeiro, com os limites que estavam vigentes.
3. **Quem aprovou.** Uma decisão de alocação sem responsável identificado não é auditável, e a automação sem aprovação humana desloca a responsabilidade para um sistema que não pode respondê-la.

Planilhas falham nas três: sobrescrevem o estado anterior, misturam regra e dado, e não guardam autoria. Plataformas de terceiros costumam responder à segunda pergunta com uma caixa fechada, entregando ao escritório a carteira e não o critério. Nenhuma das duas alternativas serve a quem responde pela decisão.

A questão que orienta este trabalho é, portanto, de engenharia e de governança antes de ser de finanças: como construir um artefato que produza recomendação e prova ao mesmo tempo, e cuja própria evidência de desempenho resista a auditoria hostil?

---

## 2. Fundamentação e posicionamento

Três problemas metodológicos bem documentados na literatura de finanças quantitativas foram tratados como requisitos de projeto, não como ressalvas de rodapé.

**Viés de sobrevivência.** Painéis montados a partir de provedores públicos de preço ajustado servem as empresas que ainda existem. Reconstruir o universo a partir de um provedor desses apaga silenciosamente toda empresa deslistada, adquirida ou liquidada, justamente as que produziram os piores retornos. O efeito é sistemático e sempre favorável ao backtest.

**Informação disponível na data.** Fundamentos precisam ser lidos como estavam no momento da decisão, com data de recebimento pelo regulador, não com a versão consolidada e eventualmente republicada. Chamar isso de detalhe é subestimar o problema: a diferença aparece com sinal previsível, sempre a favor de quem testa.

**Múltiplas tentativas.** Quando se avaliam dezenas de configurações e se publica a melhor, o índice de Sharpe observado é enviesado para cima pela própria busca. Bailey e López de Prado formalizaram o problema com o Sharpe deflacionado, que corrige a estatística pelo número de tentativas e pelos momentos superiores da distribuição de retornos. Sem essa correção, qualquer busca suficientemente ampla produz um vencedor aparentemente significativo.

O posicionamento do artefato decorre desses três pontos. O Benevente não compete em promessa de retorno. Compete em verificabilidade. Qualquer concorrente exibe uma curva ascendente, e a pergunta que raramente é respondida é quanto daquela curva vem de ter escolhido a regra depois de ver o resultado. Este trabalho mede esse valor e o publica.

---

## 3. O artefato

### 3.1 Visão geral

O Benevente Wealth System é um sistema de apoio à decisão que executa um protocolo anual. Em janeiro, monta a carteira usando exclusivamente dados disponíveis naquela data. Mantém a carteira pelo ano, já com custos de execução. Revisa no ciclo seguinte. O resultado do ano entra depois, apenas para avaliação, e nunca retroalimenta a decisão que o gerou.

O sistema é composto por cinco camadas.

| Camada | Função | Saída auditável |
|---|---|---|
| Base de dados | Universo, preços e fundamentos com data | Manifesto com SHA-256 por arquivo |
| Elegibilidade | Tela de aprovação por ativo | Motivo de cada reprovação |
| Alocação | Otimização convexa com restrições | Pesos e restrições ativas |
| Execução | Ordens com lote e participação no volume | Custo estimado por ordem |
| Governança | Aprovação humana e conciliação | Quem aprovou e diferença contra a nota de corretagem |

### 3.2 Base de dados: o universo de registro é a bolsa, não o provedor

O universo de registro é o arquivo histórico de cotações da própria B3, não um feed de terceiro. A consequência é direta e mensurável. O painel construído cobre 514 emissores entre 2010 e 2025, dos quais 166 deixam de negociar antes de dezembro de 2025, 77 deles antes de 2020, e 58 já haviam perdido mais de 60% do próprio topo quando pararam de negociar. Um painel montado a partir de provedor público simplesmente não contém essas empresas. A diferença entre incluí-las e não incluí-las é a diferença entre medir a estratégia e medir a sorte de ter olhado só para os sobreviventes.

Preços deslistados exigem tratamento de eventos societários sem a ajuda do provedor, que já não serve esses papéis. O sistema detecta desdobramentos, grupamentos e bonificações grandes a partir de razões de preço redondas e persistentes no arquivo da bolsa. O detector foi validado contra o arquivo de eventos de um provedor, no subconjunto de papéis em que esse arquivo existe, e os dois lados da validação são publicados: precisão de 88,1%, com 340 de 386 ajustes aplicados coincidindo com um evento confirmado, e recall de 23,3%, com 103 de 443 eventos do provedor detectados. O recall baixo é uma limitação real e está declarada. O detector é conservador por construção, e prefere não ajustar a ajustar errado. Publicar apenas a precisão seria omitir metade do resultado.

Os fundamentos vêm dos formulários ITR e DFP da CVM, com a data de recebimento usada como porta: um documento só entra na decisão de janeiro do ano *t* se o regulador o recebeu antes daquela data. A ponte entre o ticker da B3 e o CNPJ da CVM é construída ano a ano, e sua cobertura é publicada em vez de suposta. Em 2012, primeiro ano da série, 266 de 314 ações tiveram ponte aceita e 171 tiveram fundamentos completos, porque a série do ITR começa em 2011 e 2012 é o primeiro ano em que a construção de doze meses tem os dois lados disponíveis.

### 3.3 Elegibilidade e alocação

A tela de elegibilidade reprova ativos por liquidez insuficiente, ausência de fundamento na data, alavancagem ou cobertura de juros fora do aceitável. Cada reprovação é registrada com o motivo, o que permite ao escritório responder por que um papel conhecido não entrou, pergunta que aparece com a mesma frequência da inversa.

A alocação é um problema de otimização convexa resolvido numericamente, com quatro restrições declaradas antes da seleção: teto de renda variável, teto por emissor, número mínimo de posições e penalização de giro. As restrições são parte da política versionada, não parâmetros ajustados depois de ver o resultado.

Os coeficientes do escore de seleção, os limiares da tela de elegibilidade, as constantes de aversão a risco e a grade de configurações não são publicados. Eles estão registrados de forma verificável, porque o registro congelado carrega o SHA-256 de cada arquivo de entrada e da própria configuração, de modo que a anterioridade é demonstrável sem que a implementação seja replicável por leitura. Essa é uma escolha comercial deliberada e está declarada aqui para que o leitor saiba exatamente o que está sendo e o que não está sendo divulgado.

### 3.4 Custos, imposto e execução

Retorno bruto não é resultado. O sistema modela três parcelas.

- **Taxas da B3** e corretagem por ordem.
- **Deslizamento por participação no volume**, proporcional ao tamanho da ordem relativo ao volume médio diário do papel. Uma ordem grande em papel ilíquido custa mais, como custa na prática.
- **Imposto de renda brasileiro**, com 15% sobre ganho realizado em renda variável e 17,5% sobre renda fixa na faixa de 361 a 720 dias, cobrado no ano em que a revisão seguinte efetivamente realiza o ganho, e com liquidação integral assumida no último ano avaliado. Essa é a hipótese terminal conservadora, em vez de um diferimento indefinido que embelezaria a série.

O sistema recusa, por regra, ordens que ultrapassem 5% do volume médio diário do papel. A ordem falha em vez de ser enviada.

### 3.5 Governança: o sistema propõe, a pessoa decide

Quatro mecanismos delimitam o que o software pode fazer.

1. **Aprovação humana obrigatória.** Nenhuma ordem é transmitida, nem pode ser, porque a arquitetura não tem esse caminho.
2. **Papel delimitado do modelo de linguagem.** O modelo organiza tese e riscos a partir de fatos já aprovados. Ele não define peso, não altera limite e não aprova ativo. Isso é uma restrição de arquitetura verificável, não uma promessa de conduta, e a Seção 5.4 mostra o experimento que testou o que aconteceria se ela fosse relaxada.
3. **Conciliação pós-operação.** A nota de corretagem é confrontada linha a linha com a ordem proposta.
4. **Limites explícitos e versionados.** Teto de renda variável, teto por emissor e reserva em caixa ficam na política, registrados antes da seleção.

---

## 4. Método de avaliação

### 4.1 Seleção aninhada: a janela que escolhe não é a janela que testa

O artefato admite múltiplas configurações de política, combinando teto de renda variável, número de posições e família de fatores. Publicar a melhor delas medida sobre toda a amostra seria exatamente o erro que a Seção 2 descreve. O protocolo adotado é uma seleção aninhada: para decidir a configuração do ano *t*, o sistema ordena as 36 configurações usando somente os anos já encerrados antes de *t*, e adota a primeira colocada. Trocar de configuração é uma operação real, e é cobrada como rebalanceamento integral.

O ranqueamento exige no mínimo três anos encerrados. Com o painel começando em 2012, isso torna 2012 a 2014 a janela de seleção e 2015 a 2025 a janela de avaliação, com onze decisões anuais, uma por ano. Os três anos de seleção aparecem nos gráficos, marcados como tal, e não entram em nenhuma métrica de manchete.

### 4.2 Comparadores

Quatro referências, todas calculadas de forma independente.

- **CDI**, série 12 do Banco Central, como custo de oportunidade do caixa.
- **Ibovespa**, que é um índice de retorno total e portanto comparável a uma carteira que reinveste proventos.
- **BOVA11**, o ETF efetivamente investível, para que a comparação não dependa de um índice não negociável.
- **Otimização média-variância neutra** sobre o mesmo universo elegível, um comparador independente e não uma cópia da carteira com outro nome.

Esse último merece nota. Em uma versão anterior do sistema, a série rotulada como MVO de referência era numericamente idêntica à estratégia em todos os anos, ou seja, a estratégia estava sendo comparada a si mesma. O defeito foi encontrado na auditoria interna, corrigido com uma implementação independente, e o comparador passou a produzir resultados distintos, inclusive desfavoráveis à estratégia em um dos onze anos.

### 4.3 Correção por múltiplas tentativas

Com 36 configurações avaliadas, o Sharpe da vencedora precisa ser deflacionado. Calculamos o Sharpe deflacionado com o número de tentativas, o número de observações e os momentos superiores da série de retornos.

Medimos também o prêmio de retrospectiva, que é a diferença entre o CAGR da configuração que teria vencido a amostra inteira, escolha impossível na prática porque usa os anos sobre os quais é medida, e o CAGR da escolha aninhada. Esse número quantifica exatamente o que um concorrente ganharia publicando o vencedor da busca como se fosse resultado obtenível.

---

## 5. Resultados

### 5.1 Desempenho da carteira publicada

Onze decisões anuais, de 2015 a 2025, líquidas de custos de execução.

| Série | CAGR | R$ 100 mil viram | Anos vencidos | Queda máxima diária |
|---|---:|---:|:---:|---:|
| **Benevente** | **17,86%** | **R$ 609.832** | | −47,8% |
| Benevente, após IR | 16,03% | R$ 513.052 | | |
| Ibovespa | 11,77% | R$ 340.068 | 7 de 11 | −47,0% |
| BOVA11 (ETF investível) | 11,72% | R$ 338.545 | 7 de 11 | |
| CDI | 9,61% | R$ 274.368 | 6 de 11 | 0% |
| MVO neutra, mesmo universo | 7,83% | R$ 229.255 | 10 de 11 | |

A coluna em reais existe porque percentual é fácil de aprovar com a cabeça e difícil de sentir. Cem mil reais aplicados em janeiro de 2015 e resgatados no fim de 2025 seriam R$ 609.832 na carteira publicada, R$ 340.068 no Ibovespa e R$ 274.368 no CDI, uma diferença de R$ 269.764 para o mercado e de R$ 335.464 para o caixa.

Em janelas móveis, contra o CDI a carteira vence 8 de 9 janelas de três anos, 6 de 7 de cinco anos e 2 de 2 de dez anos. Contra a otimização neutra, vence todas as janelas de três, cinco e dez anos. Registramos que janelas móveis se sobrepõem: as 9 janelas de três anos contêm apenas 3 blocos independentes, e as de dez anos, apenas 1. O número de janelas vencidas impressiona mais do que informa, e por isso publicamos os dois lados.

**O que esse resultado custa.** A queda máxima diária chegou a 47,8%, praticamente a mesma do Ibovespa no período, que foi de 47,0%, porque o protocolo aninhado elevou a parcela de renda variável a 95% entre 2018 e 2021. A carteira não é uma versão suavizada do mercado com retorno maior. É uma carteira concentrada que passou pelo mesmo tombo e se recuperou mais. Houve cinco trocas de configuração no período, e o orçamento de renda variável percorreu 55%, 75%, 95%, 75% e 55%.

### 5.2 O resultado sobrevive à correção por múltiplas tentativas?

| Estatística | Valor |
|---|---:|
| Sharpe observado do excesso sobre o CDI | 0,933 |
| Sharpe máximo esperado sob a hipótese nula, com 36 tentativas | 0,355 |
| **Sharpe deflacionado** | **0,986** |
| Significante a 95% | sim |
| **Prêmio de retrospectiva** | **0,65 p.p. ao ano** |

O prêmio de retrospectiva merece leitura cuidadosa, porque é a medida mais informativa do conjunto. Ele diz que escolher a configuração vencedora sabendo o desfecho teria rendido apenas 0,65 ponto percentual a mais por ano do que a escolha aninhada, que não sabia. Em uma versão anterior deste mesmo sistema, com um ano a menos de treino, esse prêmio era de 4,98 pontos, ou seja, a busca estava fazendo boa parte do trabalho. Estender a base de dados para permitir decisões desde 2012 reduziu o prêmio por um fator de sete e elevou o Sharpe deflacionado de 0,957 para 0,986. O ganho relevante da última iteração do artefato não foi retorno. Foi a redução da parcela do retorno atribuível à própria busca.

### 5.3 O que não funcionou

Três hipóteses foram testadas com poder estatístico adequado e rejeitadas. São publicadas com o mesmo destaque do resultado positivo, porque um artefato que só reporta o que deu certo não é auditável.

**Previsão anual de regime.** Testamos se indicadores disponíveis em janeiro, entre prêmio de lucro sobre o CDI, nível do CDI, retorno e volatilidade do mercado nos doze meses anteriores e distância do topo, anteciparam se o ano seria de ações ou de caixa. Sobre 8 anos, o melhor preditor acertou 3 de 4 chamadas efetivas, com p de 0,31 contra cara-ou-coroa. Um acerto de 75% em quatro tentativas não distingue habilidade de sorte. O prêmio disponível para quem acertasse todas as chamadas era de 6,5 pontos percentuais ao ano, e permanece inalcançável. Sem sinal.

**Realocação mensal e semanal.** Aumentamos as observações para responder à objeção de poder estatístico. Foram 118 períodos mensais e 521 períodos semanais, com sete regras de alocação contínua testadas em cada frequência. Nenhuma das sete regras superou o peso estático de forma estatisticamente significante em nenhuma das duas frequências, e uma delas, a de média-variância, foi significativamente pior. O oráculo, que conhece o futuro, teria feito 72,8% ao ano no mensal e 137,1% no semanal, contra 21,1% do estático. O prêmio por acertar o tempo é enorme, e nada que testamos consegue capturá-lo. Rejeitada.

**Modelo de linguagem como fonte de retorno.** Este é o teste que mais interessa à governança do produto, e está detalhado a seguir.

### 5.4 O experimento com modelo de linguagem: três nulos

O sistema usa um modelo de linguagem em papel deliberadamente restrito. Para verificar se essa restrição custa desempenho, e se o modelo agrega algo, montamos quatro braços sobre 13 anos, com o mesmo universo elegível.

- **Nomeado:** o modelo vê os nomes das empresas e devolve um escore limitado, que inclina o retorno esperado dentro do otimizador convexo.
- **Anonimizado:** idêntico, mas as empresas são identificadas apenas por números, de modo que o modelo vê os fundamentos e não as marcas.
- **Determinístico:** controle sem modelo algum, ordenando o mesmo universo pelo escore de fator pré-declarado.
- **Monolítico:** o contrafactual em que o modelo devolve pesos diretamente, sem otimizador e sem restrições.

| Comparação | Diferença anualizada | p |
|---|---:|---:|
| Nomeado menos anonimizado (contaminação temporal) | +0,38 p.p. | 0,905 |
| Anonimizado menos determinístico (valor agregado pelo modelo) | −0,05 p.p. | 0,989 |
| Anonimizado menos monolítico (valor do desacoplamento) | +0,81 p.p. | 0,777 |

Três nulos, e cada um significa algo diferente.

1. **Não há evidência de contaminação temporal.** O braço nomeado não lucrou por reconhecer empresas cujo destino o modelo poderia conhecer do treinamento. Essa era a objeção mais séria a qualquer uso de modelo de linguagem em backtest histórico, e ela não se sustentou nesta configuração.
2. **O modelo não agrega retorno.** Ele reproduz o ranqueamento determinístico em vez de acrescentar julgamento, com diferença de cinco centésimos de ponto percentual e sinal negativo. Isso é uma constatação desconfortável para o discurso de mercado sobre IA em investimentos, e é exatamente por isso que está publicada.
3. **O desacoplamento não custa desempenho.** Manter o modelo longe dos pesos não penalizou o resultado, e se algo o braço desacoplado foi melhor. O braço monolítico, que recebeu a caneta, violou restrições de política. O desacoplamento não é cerimônia. É o que impede a violação.

A conclusão de produto é direta. O modelo de linguagem justifica-se no Benevente por organizar e explicar decisões, não por gerá-las. Vender IA como fonte de alfa, com base nestes dados, seria vender algo que medimos e não encontramos.

### 5.5 Defeitos encontrados na própria auditoria

O artefato passou por auditoria interna adversarial. Sete defeitos foram encontrados e corrigidos, e todos inflavam o resultado.

| Defeito | Efeito | Correção |
|---|---|---|
| Comparador MVO idêntico à estratégia | Comparação da estratégia consigo mesma | Implementação independente |
| Painel de provedor descartava deslistadas | Viés de sobrevivência | Universo reconstruído do arquivo da B3 |
| Ano de deslistagem descartado inteiro | Perda truncava o ano | Liquidação da posição em CDI |
| Imposto ausente | Retorno superestimado | Modelo tributário brasileiro |
| Custo fixo ignorando liquidez | Ordem grande sem penalidade | Deslizamento por participação no volume |
| Rebalanceamento diário implícito | Artefato de vetorização | Trajetória de compra e manutenção |
| Filtro de sessões usando pico global | Anos legítimos descartados | Pico móvel local |

Depois da última correção, o CAGR publicado caiu, a queda máxima subiu de 30,4% para 47,8%, e o número foi publicado assim mesmo. Essa é a evidência de processo que o produto vende: não que o resultado seja bom, mas que ele é o resultado que sobrou depois de procurar defeitos com afinco.

---

## 6. Contribuição tecnológica e aderência ao mercado

**Para o escritório.** O sistema entrega, por decisão, um dossiê completo, com política aplicada, dados com data e hash, tela de elegibilidade com motivo de cada reprovação, pesos, ordens com lote e participação no volume, e custo estimado. O que antes era reconstruído a mão sob pressão passa a ser subproduto da própria operação.

**Para o cliente final.** A pergunta "por que este papel?" passa a ter resposta datada e verificável, e a pergunta simétrica, "por que não aquele?", também.

**Para o ecossistema capixaba.** O argumento comercial não é rendemos mais. É que o escritório local passa a ter um processo demonstrável, que é justamente o que hoje o obriga a terceirizar a gestão para fora do estado.

**Maturidade.** O artefato está em estágio de pesquisa reprodutível, não de produto validado institucionalmente. A janela de 2015 a 2025 foi usada para desenvolver e escolher a regra, e portanto descreve a amostra e não prevê o futuro. A avaliação prospectiva começa a partir do registro congelado, cujo hash está versionado no repositório com data carimbada por terceiro. Um registro pré-especificado que exista apenas no disco de quem o escreveu não demonstra anterioridade nenhuma.

---

## 7. Limitações

Declaradas sem atenuação, porque uma limitação omitida vira defeito descoberto pelo avaliador.

1. **A janela avaliada é a janela de desenvolvimento.** Onze anos avaliados não são onze anos de validação prospectiva. O prêmio de retrospectiva de 0,65 p.p. limita o problema, mas não o elimina.
2. **O detector de eventos societários tem recall de 23,3%.** Ele é conservador, e proventos, juros sobre capital próprio e eventos de papéis deslistados ainda exigem reconciliação contra registro primário da B3 ou da CVM antes de qualquer afirmação comercial de desempenho.
3. **Distribuições imputadas.** Papéis sem cobertura de provedor recebem o rendimento mediano da seção transversal do ano. É uma aproximação, e os papéis afetados estão listados no relatório de cobertura.
4. **A queda máxima é grande.** Quase 48% em base diária. Nenhuma suitability razoável coloca um cliente conservador nessa carteira.
5. **Onze observações anuais são poucas.** O Sharpe deflacionado corrige o viés de busca, não o tamanho da amostra.
6. **Uso comercial exige estrutura regulatória própria.** O sistema é apoio à decisão e trilha de auditoria. Não é recomendação individual, gestão discricionária, nem promessa de superar referências.

---

## 8. Agenda

- Acumular anos avaliados depois do registro congelado, que é a única evidência capaz de mudar o estatuto do artefato de pesquisa para validado.
- Reconciliar eventos societários e proventos contra registro primário, elevando o recall do detector.
- Repetir o experimento de contaminação em modelos com datas de corte de treinamento distintas, para separar contaminação de capacidade.
- Instrumentar o piloto em escritório capixaba, medindo tempo de produção do dossiê e taxa de divergência na conciliação de notas.

---

## 9. Disponibilidade

O sistema publicado, com o dossiê anual navegável, a comparação interativa contra referências e ativos escolhidos pelo leitor, e as páginas de método, está em https://benevente-wealth-system.vercel.app.

---

## Referências

*A completar conforme as normas do periódico.* Núcleo mínimo:

- BAILEY, D. H.; LÓPEZ DE PRADO, M. The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality. *Journal of Portfolio Management*, 2014.
- BAILEY, D. H. et al. The Probability of Backtest Overfitting. *Journal of Computational Finance*, 2016.
- LÓPEZ DE PRADO, M. *Advances in Financial Machine Learning*. Wiley, 2018.
- HARVEY, C. R.; LIU, Y.; ZHU, H. …and the Cross-Section of Expected Returns. *Review of Financial Studies*, 2016.
- BRASIL. Comissão de Valores Mobiliários. Formulários ITR e DFP.
- BANCO CENTRAL DO BRASIL. Sistema Gerenciador de Séries Temporais, série 12 (CDI).
- B3. Arquivo histórico de cotações (COTAHIST).

---

### Nota sobre a origem dos números

Todos os valores deste texto foram extraídos dos artefatos de execução do sistema, não transcritos de versões anteriores do material. As fontes primárias são `artifacts/published_nested/annual_results.csv` para a série anual publicada, `artifacts/audit_evidence/audit_evidence.json` para o placar anual e as janelas móveis, `artifacts/configuration_search_2012/summary.json` para a busca de configuração, o Sharpe deflacionado e o prêmio de retrospectiva, `artifacts/alloc_monthly/` e `artifacts/alloc_weekly/` para a realocação, `artifacts/allocation_regime/` para o regime anual, `artifacts/llm_contamination/summary.json` para o experimento com modelo de linguagem, e o manifesto do painel de preços, que carrega o SHA-256 do arquivo que gerou cada série.
