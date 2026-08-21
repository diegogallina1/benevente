# Benevente Wealth System: um artefato auditável para decisões de carteira

---

## Resumo

Decisões de carteira precisam continuar explicáveis depois de executadas. Este trabalho constrói e avalia o Benevente Wealth System, um artefato de apoio à decisão que reúne, no mesmo registro, os dados admitidos, a regra quantitativa, a carteira proposta, a explicação e a aprovação humana. A pesquisa segue design science e avalia o artefato por testes funcionais, auditoria adversarial e um diagnóstico histórico sequencial de onze decisões entre 2015 e 2025. A auditoria encontrou sete defeitos capazes de inflar resultados e revelou uma limitação material: 13,9% da exposição acumulada a ações selecionadas dependeu de séries com proventos imputados. Por isso, o retorno histórico é apresentado como diagnóstico de desenvolvimento, não como validação comercial. Uma reamostragem pareada indica estabilidade interna, mas os intervalos de 95% do excesso de retorno cruzam zero contra CDI, Ibovespa e BOVA11. O protocolo prospectivo foi congelado em 16 de agosto de 2026 e ainda não possui observações suficientes para conclusão. O modelo de linguagem não demonstrou ganho de retorno e permanece restrito à explicação. A contribuição comprovada é a separação verificável entre dado, cálculo, linguagem e responsabilidade.

Palavras-chave: governança de investimentos; alocação de carteira; trilha de auditoria; design science; pesquisa reprodutível.

---

## 1. Introdução: problema, objetivo e contribuição

Este trabalho parte de um problema operacional delimitado: a recomendação é produzida hoje, mas pode precisar ser defendida meses ou anos depois. Se a instituição não preserva o dado admitido, a versão da regra e a aprovação, a justificativa posterior pode incorporar informações que não existiam quando a decisão foi tomada. O Benevente foi construído para produzir a proposta e o registro que permitirá revisá-la. A existência desse problema no público-alvo, sua intensidade e a disposição a pagar pela solução ainda precisam ser medidas em piloto. O artigo não atribui ao artefato impacto regional, demanda comercial ou retenção de capital que não tenham sido observados.

O problema é concreto e tem data. Quando um cliente pergunta em 2026 por que determinada ação entrou na carteira em janeiro de 2023, o escritório precisa demonstrar três coisas simultaneamente.

1. Quais dados existiam naquela data. Um balanço republicado em 2024 não pode aparecer como se estivesse disponível em janeiro de 2023. Sem controle de data de recebimento, todo backtest e toda justificativa ficam contaminados por informação que ninguém tinha.
2. Qual regra foi aplicada. Não a regra que o escritório usa hoje, mas a que estava vigente naquele janeiro, com os limites que estavam vigentes.
3. Quem aprovou. Uma decisão de alocação sem responsável identificado não é auditável, e a automação sem aprovação humana desloca a responsabilidade para um sistema que não pode respondê-la.

Planilhas podem falhar nas três quando são usadas sem controle de versão: sobrescrevem o estado anterior, misturam regra e dado e não preservam autoria. Sistemas fechados podem entregar uma carteira sem evidenciar o critério aplicado. O requisito do artefato é permitir que uma pessoa independente refaça o caminho da decisão sem depender da memória de quem a produziu.

A questão que orienta este trabalho é, portanto, de engenharia e de governança antes de ser de finanças: como construir um artefato que produza recomendação e prova ao mesmo tempo, e cuja própria evidência de desempenho resista a auditoria hostil?

O objetivo é construir e avaliar um artefato B2B que transforme cada recomendação em um documento verificável. O método segue ciência do projeto, ou design science: identificar o problema, explicitar requisitos, construir o artefato e avaliá-lo por utilidade, qualidade e capacidade de produzir evidência (Hevner et al., 2004; Peffers et al., 2007). A avaliação combina testes de funcionamento, inspeção das fontes, tentativas deliberadas de encontrar erros e um diagnóstico financeiro histórico. A contribuição é dupla: um protocolo quantitativo que pode ser reexecutado e um fluxo de trabalho que preserva quem decidiu, com qual informação e sob qual política. O retorno passado é uma medida secundária de comportamento do protótipo, não a prova principal de utilidade nem uma promessa de desempenho futuro.

---

## 2. Problema prático e fundamentação

O público inicial do Benevente são escritórios de investimento, consultorias de valores mobiliários e estruturas de gestão patrimonial que precisam recomendar, revisar e defender carteiras. Nesse ambiente, a dificuldade não termina quando o peso de cada ativo é calculado. A instituição precisa preservar o contexto da decisão, demonstrar por que um ativo foi aceito ou recusado e comparar o resultado com alternativas reconhecíveis pelo cliente. O piloto comercial proposto poderá ser realizado no Espírito Santo por conveniência e aderência ao congresso, mas sua função será medir o problema e a utilidade do artefato, não confirmar antecipadamente um efeito sobre a economia local.

Três problemas metodológicos bem documentados na literatura de finanças quantitativas foram tratados como requisitos de projeto, não como ressalvas de rodapé.

Viés de sobrevivência. Painéis montados a partir de provedores públicos de preço ajustado servem as empresas que ainda existem. Reconstruir o universo a partir de um provedor desses apaga silenciosamente toda empresa deslistada, adquirida ou liquidada, justamente as que produziram os piores retornos. O efeito é sistemático e sempre favorável ao backtest.

Informação disponível na data. Fundamentos precisam ser lidos como estavam no momento da decisão, com data de recebimento pelo regulador, não com a versão consolidada e eventualmente republicada. Chamar isso de detalhe é subestimar o problema: a diferença aparece com sinal previsível, sempre a favor de quem testa.

Múltiplas tentativas. Quando se avaliam dezenas de configurações e se publica a melhor, o índice de Sharpe observado é enviesado para cima pela própria busca. Bailey e López de Prado formalizaram o problema com o Sharpe deflacionado, que corrige a estatística pelo número de tentativas e pelos momentos superiores da distribuição de retornos. Sem essa correção, qualquer busca suficientemente ampla produz um vencedor aparentemente significativo.

Quatro referências clássicas orientam a construção financeira do artefato. Markowitz (1952) mostrou que uma carteira precisa ser analisada pela interação entre retornos e covariâncias, e não pela atratividade isolada de cada ativo. A otimização média-variância, chamada neste artigo de MVO, estima a relação entre retorno esperado e risco conjunto e escolhe pesos sob restrições. No Benevente, ela funciona como comparação independente. A pergunta é simples: o que uma carteira guiada apenas por médias, covariâncias e limites teria produzido sobre o mesmo conjunto elegível? Isso evita atribuir ao filtro fundamental um ganho que possa vir apenas da diversificação. A ênfase em qualidade dialoga com Novy-Marx (2013), enquanto o uso conjunto de valor, qualidade e confirmação de mercado se aproxima da lógica multifatorial de Fama e French (2015), sem pretender reproduzir exatamente seus fatores.

Black e Litterman (1992) combinam equilíbrio de mercado e visões. O Benevente adota somente a separação conceitual: fatos e sinais geram o ranking, enquanto a linguagem explica a visão sem alterar a alocação. O modelo Black–Litterman não é implementado na carteira publicada.

DeMiguel, Garlappi e Uppal (2009) demonstram como erro de estimação pode eliminar, fora da amostra, a vantagem aparente de métodos sofisticados sobre uma diversificação simples. A resposta do projeto não é presumir que um otimizador sempre melhora o resultado. É publicar uma referência independente, impor um número mínimo de posições, limitar a interpretação das métricas e comparar decisões em sequência temporal. O resultado de 7,83% ao ano do MVO de referência nesta execução não prova que MVO é inferior em geral. Mostra somente que aquela implementação, com aquele universo elegível e aquelas estimativas disponíveis em cada janeiro, produziu esse caminho. Em outra amostra ou especificação, a ordem pode se inverter.

Novy-Marx e Velikov (2016) mostram que custos de negociação podem consumir anomalias documentadas. O diagnóstico deduz taxas e deslizamento estimado, mede giro e penaliza trocas. Como estimativa não é nota de corretagem, o produto prevê conciliação posterior com o custo observado.

Essas escolhas definem o tipo de evidência que o trabalho pode produzir. O backtest é um experimento histórico sobre um protocolo e não uma simulação da experiência individual de todo cliente. Suitability, necessidade de liquidez, tributação específica, ativos já detidos e restrições contratuais podem mudar a carteira implementável. Por isso, o artefato separa três objetos que costumam aparecer misturados: a regra acadêmica usada para medir o sinal; a política institucional que limita o risco; e o texto explicativo que ajuda uma pessoa a revisar a decisão. Uma boa curva não substitui nenhum dos três.

O posicionamento do artefato decorre desses três pontos. O Benevente não é apresentado como gerador comprovado de alfa. Seu diferencial verificável é manter unidos os insumos, a regra, a explicação e a aprovação. O diagnóstico histórico serve para pressionar essa arquitetura e revelar erros, inclusive quando a correção piora o resultado publicado.

---

## 3. O artefato

### 3.1 Visão geral

O Benevente Wealth System é um sistema de apoio à decisão que executa um protocolo anual. Em janeiro, monta a carteira usando exclusivamente dados disponíveis naquela data. Mantém a carteira pelo ano, já com custos de execução. Revisa no ciclo seguinte. O resultado do ano entra depois, apenas para avaliação, e nunca retroalimenta a decisão que o gerou.

O sistema é composto por cinco camadas.

| Camada | Função | Saída auditável |
|---|---|---|
| Base de dados | Universo, preços e fundamentos com data | Manifesto com SHA-256 por arquivo |
| Elegibilidade | Tela de aprovação por ativo | Motivo de cada reprovação |
| Seleção e alocação | Escore multifatorial e regra quantitativa com limites | Ranking, pesos e restrições ativas |
| Execução | Ordens com lote e participação no volume | Custo estimado por ordem |
| Governança | Aprovação humana e conciliação | Quem aprovou e diferença contra a nota de corretagem |

[[FIGURE:architecture]]

O fluxo da Figura 1 separa funções que costumam aparecer misturadas. Dados e fundamentos alimentam a validação. Somente os ativos aceitos seguem para o cálculo. O motor quantitativo devolve pesos válidos e custos estimados. A pessoa revisa a proposta antes da aprovação. O modelo de linguagem recebe apenas fatos já calculados e os converte em uma nota legível, sem caminho de retorno para alterar pesos. O dossiê registra cada uma dessas etapas.

### 3.2 Base de dados: o universo de registro é a bolsa, não o provedor

O universo de registro é o arquivo histórico de cotações da própria B3, não um feed de terceiro. A consequência é direta e mensurável. O painel construído cobre 514 emissores entre 2010 e 2025, dos quais 166 deixam de negociar antes de dezembro de 2025, 77 deles antes de 2020, e 58 já haviam perdido mais de 60% do próprio topo quando pararam de negociar. Um painel montado a partir de provedor público simplesmente não contém essas empresas. A diferença entre incluí-las e não incluí-las é a diferença entre medir a estratégia e medir a sorte de ter olhado só para os sobreviventes.

Preços deslistados exigem tratamento de eventos societários sem a ajuda do provedor. A primeira versão detectava razões de preço redondas e obteve precisão de 88,1%, mas recall de apenas 23,3% contra o arquivo de eventos disponível. Para retirar essa heurística da posição de fonte principal, uma nova rotina consultou diretamente os registros públicos da B3 e arquivou 18.190 dividendos, juros sobre capital próprio, desdobramentos, grupamentos, bonificações e eventos manuais. A consulta cobriu 475 de 497 ativos do painel. Vinte e dois códigos não foram devolvidos pela página atual e 271 eventos, entre eles 218 subscrições, ainda exigem resolução de direitos e conversões. A série publicada não foi requalificada: ela continua como dado de pesquisa até ser reconstruída desde o preço bruto, com cobertura integral e cada evento aplicado em relatório próprio.

Os fundamentos vêm dos formulários ITR e DFP da CVM, com a data de recebimento usada como porta: um documento só entra na decisão de janeiro do ano *t* se o regulador o recebeu antes daquela data. A ponte entre o ticker da B3 e o CNPJ da CVM é construída ano a ano, e sua cobertura é publicada em vez de suposta. Em 2012, primeiro ano da série, 266 de 314 ações tiveram ponte aceita e 171 tiveram fundamentos completos, porque a série do ITR começa em 2011 e 2012 é o primeiro ano em que a construção de doze meses tem os dois lados disponíveis.

### 3.3 Elegibilidade, seleção e alocação

A tela de elegibilidade reprova ativos por liquidez insuficiente, ausência de fundamento na data, alavancagem ou cobertura de juros fora do aceitável. Cada reprovação é registrada com o motivo, o que permite ao escritório responder por que um papel conhecido não entrou, pergunta que aparece com a mesma frequência da inversa.

O foco econômico é uma análise fundamentalista multifatorial. Qualidade procura empresas capazes de remunerar o capital e sustentar a operação; valor procura um preço coerente com lucros, patrimônio ou geração de caixa; momento de doze meses funciona como confirmação de mercado e reduz a compra mecânica de uma empresa barata que continua deteriorando. Liquidez determina se a tese é executável. Bancos e empresas operacionais recebem métricas diferentes porque dívida e margem operacional não significam a mesma coisa nos dois balanços. O retorno histórico entra como fator complementar, não substitui os demonstrativos.

Depois da triagem, cada ativo recebe um escore comparável dentro do universo disponível naquele janeiro. A estratégia publicada faz um corte nos melhores emissores, mantém apenas uma classe por emissor e distribui o orçamento de renda variável proporcionalmente ao escore, sujeito ao número de posições e aos limites da configuração. O saldo fica no CDI. A configuração completa — família de fatores, número de posições e orçamento de ações — é escolhida anualmente pelo desempenho ajustado ao risco nos anos já encerrados. A otimização média-variância não define essa carteira. Ela é calculada de modo independente, sobre o mesmo universo elegível, para medir o que uma carteira puramente quantitativa de média e covariância teria produzido.

Essa separação também resolve a ambiguidade entre os nomes. Benevente Quant AI designa a pesquisa acadêmica, inclusive o experimento que combina um modelo de linguagem com um otimizador convexo. Benevente Wealth System designa o produto B2B de governança que entrega proposta, explicação e registro. A carteira histórica publicada é a regra multifatorial determinística. O modelo de linguagem não seleciona ativo e não escreve peso; seu papel é transformar fatos aprovados em tese, riscos e perguntas para revisão humana.

O método precisa ser compreensível sem reproduzir o código da aplicação. Primeiro, o sistema elimina ativos sem dados suficientes, sem liquidez compatível ou com lucro negativo. Depois, ordena os remanescentes por uma de quatro leituras: valor combinado a qualidade, valor combinado a qualidade e momento, somente momento ou baixa volatilidade. A versão multifatorial atribui 40% à qualidade, medida por retorno sobre o capital ou sobre o patrimônio, 40% ao lucro em relação ao preço e 20% ao comportamento do preço nos doze meses anteriores. Em seguida, escolhe uma cesta e distribui o orçamento de ações entre os melhores colocados. O saldo permanece no CDI.

Há três escolhas de orçamento de ações, 55%, 75% ou 95%, três tamanhos de cesta, 5, 8 ou 12 emissores, e quatro leituras de sinal. A combinação produz 36 políticas candidatas. O efeito de cada escolha é intuitivo: mais ações aumentam a exposição ao mercado; mais emissores reduzem a dependência de um papel; sinais distintos favorecem características diferentes. Em cada janeiro, somente os anos já encerrados podem ordenar essas políticas. O teto por emissor impede que a carteira pareça diversificada apenas no número de nomes. A configuração completa, a transformação de cada campo e os arquivos de entrada e saída recebem SHA-256 e permanecem disponíveis no pacote de reprodução.

### 3.4 Por que a decisão é anual

A cadência anual é uma hipótese coerente com a natureza do sinal e, neste estudo, uma escolha empiricamente testada. Qualidade, retorno sobre capital, alavancagem e geração de caixa são grandezas divulgadas em ciclos contábeis e cuja tese econômica precisa de tempo para aparecer no preço. Uma troca mensal baseada nelas pode vender uma empresa antes que a melhora operacional seja reconhecida e aumenta o número de decisões que precisam ser justificadas. A revisão em janeiro também cria uma fronteira operacional simples: tudo o que foi publicado até a data pode entrar; tudo o que veio depois pertence ao próximo ciclo.

Anual não significa que o sistema ignora o risco durante doze meses. Preços, concentração, liquidez e eventos materiais podem ser monitorados continuamente, e uma política institucional pode prever um gatilho extraordinário. Significa apenas que a reseleção sistemática da cesta acontece uma vez por ano. No teste de robustez, mantendo regra e dados constantes, a reseleção anual superou as versões trimestral e mensal antes mesmo dos custos. Com apenas onze anos pareados, isso não prova que a frequência anual seja universalmente ótima; mostra que não houve evidência para substituir a regra mais simples nesta amostra.

Notícias não entram no modelo atual. Esse limite é intencional: um estudo com notícias exige arquivo histórico licenciado, horário de publicação, deduplicação e uma data de corte verificável para o modelo de linguagem. Misturar notícias retrospectivamente ao protocolo anual criaria uma nova oportunidade de usar informação futura. O estudo futuro adequado é um braço separado, pré-registrado, com revisão trimestral ou por evento e notícias carimbadas no tempo, comparado à regra anual sem alterar esta última.

### 3.5 Custos, imposto e execução

Retorno bruto não é resultado. O sistema modela três parcelas.

- Taxas da B3 e corretagem por ordem.
- Deslizamento por participação no volume, proporcional ao tamanho da ordem relativo ao volume médio diário do papel. Uma ordem grande em papel ilíquido custa mais, como custa na prática.
- Imposto de renda brasileiro, com 15% sobre ganho realizado em renda variável e 17,5% sobre renda fixa na faixa de 361 a 720 dias, cobrado no ano em que a revisão seguinte efetivamente realiza o ganho, e com liquidação integral assumida no último ano avaliado. Essa é a hipótese terminal conservadora, em vez de um diferimento indefinido que embelezaria a série.

O sistema recusa, por regra, ordens que ultrapassem 5% do volume médio diário do papel. A ordem falha em vez de ser enviada.

### 3.6 Governança: o sistema propõe, a pessoa decide

Quatro mecanismos delimitam o que o software pode fazer. Eles transformam a prestação de contas algorítmica em propriedade do desenho, e não em explicação produzida depois do fato (Kroll et al., 2017). A aprovação humana e o enquadramento ao perfil também são coerentes com a Resolução CVM nº 30, enquanto qualquer uso como consultoria individualizada depende da estrutura autorizada prevista na Resolução CVM nº 19 (Comissão de Valores Mobiliários, 2021a, 2021b).

1. Aprovação humana obrigatória. Nenhuma ordem é transmitida, nem pode ser, porque a arquitetura não tem esse caminho.
2. Papel delimitado do modelo de linguagem. O modelo organiza tese e riscos a partir de fatos já aprovados. Ele não define peso, não altera limite e não aprova ativo. Isso é uma restrição de arquitetura verificável, não uma promessa de conduta, e a Seção 5.5 mostra o experimento que testou o que aconteceria se ela fosse relaxada.
3. Conciliação pós-operação. A nota de corretagem é confrontada linha a linha com a ordem proposta.
4. Limites explícitos e versionados. Teto de renda variável, teto por emissor e reserva em caixa ficam na política, registrados antes da seleção.

---

## 4. Método de avaliação

### 4.1 Sequência histórica de desenvolvimento

O artefato admite múltiplas políticas, combinando orçamento de renda variável, número de posições e família de fatores. Publicar a melhor delas medida sobre toda a amostra seria exatamente o erro que a Seção 2 descreve. Na sequência histórica, para decidir a política do ano *t*, o sistema ordena as 36 candidatas usando somente os anos encerrados antes de *t*, pelo índice de Sharpe do excesso sobre o CDI, e adota a primeira colocada. Trocar de política é tratado como operação real e cobra rebalanceamento integral.

O ranqueamento exige no mínimo três anos encerrados. Como o painel começa em 2012, os anos de 2012 a 2014 inicializam a escolha e 2015 a 2025 formam onze decisões anuais. A ordem temporal reduz o uso direto do retorno futuro em cada decisão, mas não cria uma amostra verdadeiramente externa: os dados, filtros e hipóteses foram examinados durante o desenvolvimento do projeto. Por isso, esta janela é chamada de diagnóstico retrospectivo sequencial, e não de teste fora da amostra. O teste prospectivo começa apenas depois do congelamento descrito na Seção 4.5.

### 4.2 Comparadores

Quatro referências foram calculadas de forma independente.

- CDI, série 12 do Banco Central, como custo de oportunidade do caixa.
- Ibovespa, índice de retorno total que incorpora os proventos da carteira teórica e, por isso, é comparável a uma carteira que os reinveste (B3, 2026b).
- BOVA11, ETF negociável que busca acompanhar o Ibovespa e permite observar uma implementação passiva sujeita a taxa, custos de negociação e diferença de aderência (BlackRock, 2026).
- Otimização média-variância sobre o mesmo universo elegível. Esse método estima retorno médio e covariância com dados anteriores e escolhe pesos que maximizam a relação entre retorno esperado e risco sob os mesmos limites de elegibilidade.

Esse último merece nota. Em uma versão anterior do sistema, a série rotulada como MVO de referência era numericamente idêntica à estratégia em todos os anos, ou seja, a estratégia estava sendo comparada a si mesma. O defeito foi encontrado na auditoria interna, corrigido com uma implementação independente, e o comparador passou a produzir resultados distintos, inclusive desfavoráveis à estratégia em um dos onze anos.

Ibovespa e BOVA11 não são duplicatas. O primeiro mede o retorno total de uma carteira teórica e estabelece a referência econômica do mercado. O segundo representa um caminho efetivamente negociável para buscar essa exposição. A pequena diferença entre as duas séries é informativa, pois reúne taxa, fricções operacionais e erro de aderência. Todos os comparadores usam as mesmas datas de início e fim da carteira.

### 4.3 Correção por múltiplas tentativas

Com 36 configurações avaliadas, o Sharpe da vencedora precisa ser deflacionado. Calculamos o Sharpe deflacionado com o número de tentativas, o número de observações e os momentos superiores da série de retornos.

Medimos também o prêmio de retrospectiva, que é a diferença entre o CAGR da configuração que teria vencido a amostra inteira, escolha impossível na prática porque usa os anos sobre os quais é medida, e o CAGR da escolha aninhada. Esse número quantifica exatamente o que um concorrente ganharia publicando o vencedor da busca como se fosse resultado obtenível.

### 4.4 Auditoria da qualidade dos dados e sensibilidade

A reconstrução de retorno total combina 497 séries. Em 139 delas, a distribuição de proventos precisou ser imputada porque não havia cobertura integral do provedor. Uma contagem por ticker seria insuficiente, pois uma série problemática pode nunca entrar na carteira. A auditoria cruzou, por ano, a política realmente escolhida, os pesos dos ativos e o tipo de reconstrução de cada série. A medida principal é a parcela da exposição acumulada a ações que dependeu de provento imputado.

Dois testes de sensibilidade complementam essa inspeção. O primeiro reamostra, em conjunto, os vetores anuais completos de retorno da estratégia e de cada comparador. Foram produzidas 100 mil amostras com semente registrada. O pareamento conserva a relação observada em cada ano e mede estabilidade interna, mas não cria crises novas nem corrige a fonte. O segundo aplica perdas hipotéticas de 10, 25, 50 e 100 pontos percentuais somente à parcela anual investida em séries imputadas. O objetivo é mostrar quanto o resultado depende dessa hipótese, e não adivinhar qual teria sido o provento correto.

### 4.5 Registro prospectivo

O protocolo prospectivo foi congelado em 16 de agosto de 2026, com hash e data registrados no repositório. A política precisa superar, após imposto, o CDI e o ETF investível de mercado, manter queda máxima inferior a 35% e acumular pelo menos três anos antes de uma conclusão. Não existe resultado prospectivo suficiente na data deste artigo. Essa ausência é um resultado de estágio do projeto, não uma lacuna a preencher com o histórico. A regra registrada não poderá ser alterada depois de observado um ano desfavorável sem que a mudança constitua um novo protocolo e uma nova contagem.

---

## 5. Resultados e discussão

### 5.1 Funcionamento e diagnóstico financeiro

O artefato produziu, para cada decisão anual, um registro com fontes, hashes, elegibilidade, ranking, pesos, custos estimados, comparadores e justificativa. Os testes de integridade recusaram arquivos alterados, pesos que não somavam 100%, ordens acima do limite de liquidez e fundamentos recebidos depois da decisão. A auditoria adversarial descrita na Seção 5.7 encontrou sete defeitos no próprio processo de pesquisa. Corrigi-los mudou as métricas, o que demonstra que o registro é capaz de contestar o resultado que o sistema produz.

A Tabela 2 apresenta o diagnóstico financeiro de onze decisões, de 2015 a 2025, líquido de custos estimados. Ele descreve o comportamento do protótipo durante o desenvolvimento. Não é validação prospectiva nem demonstração de que a carteira repetirá o desempenho.

| Série | Retorno anualizado | Valor final de R$ 100 mil | Anos vencidos | Queda máxima diária |
|---|---:|---:|:---:|---:|
| Benevente 1 | 17,86% | R$ 609.832 | | −47,8% |
| Benevente, após IR | 16,03% | R$ 513.052 | | |
| Ibovespa | 11,77% | R$ 340.068 | 7 de 11 | −47,0% |
| BOVA11 (ETF investível) | 11,72% | R$ 338.545 | 7 de 11 | −47,2% |
| CDI | 9,61% | R$ 274.368 | 6 de 11 | 0% |
| MVO neutra, mesmo universo | 7,83% | R$ 229.255 | 10 de 11 | |

A coluna em reais traduz a taxa anualizada em escala econômica. Sob as hipóteses do diagnóstico, R$ 100 mil teriam terminado em R$ 609.832 na carteira, R$ 340.068 no Ibovespa e R$ 274.368 no CDI. Esses valores dependem da qualidade da série reconstruída e devem ser lidos junto com a Seção 5.2.

Em janelas móveis, contra o CDI a carteira vence 8 de 9 janelas de três anos, 6 de 7 de cinco anos e 2 de 2 de dez anos. Contra a otimização de referência, vence todas as janelas de três, cinco e dez anos. Essas contagens não são observações independentes: as nove janelas de três anos contêm apenas três blocos sem sobreposição, e as de dez anos contêm apenas um. Elas descrevem a amostra, mas não aumentam artificialmente seu tamanho.

O retorno veio acompanhado de risco elevado. A queda máxima diária chegou a 47,8%, praticamente igual à do Ibovespa, 47,0%, e à do BOVA11, 47,2%. Entre 2018 e 2021, a política selecionada manteve 95% em ações e concentrou essa parcela em cinco ou seis emissores. O sistema não antecipou a Covid-19 e não protegeu o capital durante a queda. A carteira sofreu quase todo o recuo do mercado e recuperou-se depois. Portanto, o resultado é incompatível com a promessa de perfil conservador e não pode ser vendido como proteção de crise.

### 5.2 Qualidade dos dados e dependência de imputação

O painel contém 139 séries com proventos imputados, mas a carteira não as utilizou de modo uniforme. Somando somente a parcela de ações escolhida em cada ano, 13,9% da exposição acumulada dependeu de imputação. O caso mais relevante ocorreu em 2020: AZUL4 e MRFG3 representaram 50% da carteira total. Em cinco dos onze anos houve alguma exposição; nos demais, nenhuma série escolhida dependia desse procedimento.

| Ano | Peso total em séries imputadas | Séries selecionadas |
|---|---:|---|
| 2015 | 11,0% | CIEL3 |
| 2016 | 24,0% | ENBR3 |
| 2020 | 50,0% | AZUL4 e MRFG3 |
| 2021 | 25,0% | MRFG3 |
| 2025 | 5,0% | STBP3 |

Aplicar uma perda adicional de 10 pontos percentuais apenas à parcela imputada reduz o retorno anualizado da carteira de 17,86% para 16,78%. Com 25 pontos, ele cai para 15,11%; com 50, para 12,16%; e com 100, para 5,41%. A carteira deixa de superar o Ibovespa quando a penalização nessa parcela chega a aproximadamente 53 pontos percentuais e deixa de superar o CDI perto de 70 pontos. O teste mostra alguma margem econômica, mas não repara o dado. Como metade da carteira de 2020 dependeu de séries imputadas, o retorno histórico deve permanecer diagnóstico até a reconciliação dos eventos e proventos em fonte primária.

### 5.3 Incerteza da amostra

A reamostragem pareada preserva, em cada sorteio, o mesmo ano da estratégia e dos comparadores. Em 100 mil amostras, a probabilidade interna de excesso positivo foi alta, mas o intervalo de 95% ainda cruzou zero contra CDI, Ibovespa e BOVA11. Somente a comparação com a implementação específica de MVO permaneceu positiva em todo o intervalo. Isso não autoriza concluir que o Benevente supera esses referenciais na população; mostra apenas que a ordenação observada não dependeu de um único ano sorteado repetidamente.

| Comparador | Amostras com excesso positivo | Mediana do excesso anualizado | Intervalo de 95% |
|---|---:|---:|---:|
| CDI | 93,4% | +8,19 p.p. | −2,27 a +20,01 p.p. |
| MVO de referência | 100,0% | +10,06 p.p. | +4,73 a +15,29 p.p. |
| Ibovespa | 94,4% | +5,94 p.p. | −1,31 a +14,28 p.p. |
| BOVA11 | 94,3% | +5,98 p.p. | −1,34 a +14,41 p.p. |

O limite do procedimento é importante. Reamostrar onze anos não cria um mercado de baixa prolongado que não esteja na série, não produz novas trajetórias de inflação e juros e não transforma desenvolvimento em validação externa. A informação correta é que há estabilidade interna suficiente para continuar o teste prospectivo, não que a superioridade esteja comprovada.

### 5.4 Correção por múltiplas tentativas

| Estatística | Valor |
|---|---:|
| Sharpe observado do excesso sobre o CDI | 0,933 |
| Sharpe máximo esperado sob a hipótese nula, com 36 tentativas | 0,355 |
| Probabilidade do Sharpe deflacionado | 0,986 |
| Significante a 95% | sim |
| Prêmio de retrospectiva | 0,65 p.p. ao ano |

O prêmio de retrospectiva diz que escolher a política vencedora conhecendo toda a amostra teria rendido 0,65 ponto percentual a mais por ano do que a escolha sequencial. Em uma versão anterior, com um ano a menos de histórico inicial, esse prêmio era de 4,98 pontos. Ampliar a base reduziu a parcela do retorno explicada pela escolha posterior da regra. O Sharpe deflacionado também corrige múltiplas tentativas, mas não resolve a dependência de dados nem a ausência de teste prospectivo. Ele é uma defesa contra uma forma específica de sobreajuste, não um certificado geral de validade.

### 5.5 O que não funcionou

Cinco hipóteses foram testadas e nenhuma se sustentou de forma suficiente para substituir a política principal. Elas são publicadas porque um artefato que só reporta o que deu certo não é auditável.

Previsão anual de regime. Testamos se indicadores disponíveis em janeiro, entre prêmio de lucro sobre o CDI, nível do CDI, retorno e volatilidade do mercado nos doze meses anteriores e distância do topo, anteciparam se o ano seria de ações ou de caixa. Sobre 8 anos, o melhor preditor acertou 3 de 4 chamadas efetivas, com p de 0,31 contra cara-ou-coroa. Um acerto de 75% em quatro tentativas não distingue habilidade de sorte. O prêmio disponível para quem acertasse todas as chamadas era de 6,5 pontos percentuais ao ano, e permanece inalcançável. Sem sinal.

Realocação mensal e semanal. Em 118 períodos mensais e 521 semanais, nenhuma das sete regras contínuas superou de forma significativa o peso estático. A regra de média-variância foi significativamente pior. O prêmio por acertar o tempo existe, mas nenhum sinal testado o capturou.

Reseleção mais frequente da cesta. A objeção seguinte é diferente da anterior e precisa ser separada dela: não se a proporção entre ações e caixa deve mudar mais vezes, que é o que o parágrafo acima rejeita, mas se a própria cesta deveria ser retriada, reordenada e reotimizada mais vezes por ano. Testamos três cadências com a mesma regra, os mesmos limites e o mesmo painel, variando apenas as datas de decisão.

| Cadência | Decisões | CAGR bruto | Líquido de custo | Após IR | Giro no ano |
|---|---:|---:|---:|---:|---:|
| Anual | 11 | 18,58% | 18,51% | 17,09% | 62,1% |
| Trimestral | 44 | 16,37% | 16,25% | 15,60% | 116,0% |
| Mensal | 132 | 13,92% | 13,75% | 13,32% | 177,6% |

Nenhuma cadência mais rápida superou a anual. Pareando por ano-calendário, a trimestral fica 1,55 ponto percentual abaixo ao ano após imposto, com p de 0,376, e a mensal 3,27 pontos abaixo, com p de 0,306. A leitura correta é que não há evidência de que decidir mais vezes ajude, e não que esteja provado que atrapalhe: onze anos pareados não sustentam a afirmação mais forte.

A diferença surgiu antes dos custos: o retorno bruto caiu 4,66 pontos da cadência anual para a mensal. O sinal combina qualidade, valor e momento, grandezas de maturação lenta. O modelo tributário subestima o imposto do braço mensal ao não acompanhar o lote vendido; esse viés favorece a alternativa que mesmo assim não venceu.

Modelo de linguagem como fonte de retorno. Este é o teste que mais interessa à governança do produto, e está detalhado a seguir.

Proteção intranual concebida depois da Covid-19. O Benevente 2 reduz a exposição após estresse de queda e volatilidade do Ibovespa. No histórico, a queda máxima recuou de 47,8% para 28,7%, sem diferença detectável de retorno entre 2019 e 2025 (p = 0,964). Por perfil, a proteção reduziu a queda de 18,9% para 9,9% no conservador, de 28,1% para 17,9% no equilibrado e de 37,6% para 29,3% no arrojado, com pequena redução do CAGR. Em 5.000 reamostragens de blocos, o percentil adverso de 2,5% chegou a 14,2%, 27,7% e 49,1%. A regra foi registrada em 20 de agosto de 2026 para acompanhamento em 2027. Ela permanece retrospectiva, sem imposto intranual, e não integra o resultado principal.

### 5.6 O experimento com modelo de linguagem: três resultados nulos

O sistema usa um modelo de linguagem em papel deliberadamente restrito. Para verificar se essa restrição custa desempenho e se o modelo agrega algo, foram comparadas quatro versões sobre 13 anos, com o mesmo universo elegível.

- Nomeado: o modelo vê os nomes das empresas e devolve um escore limitado, que inclina o retorno esperado dentro do otimizador convexo.
- Anonimizado: idêntico, mas as empresas são identificadas apenas por números, de modo que o modelo vê os fundamentos e não as marcas.
- Determinístico: controle sem modelo algum, ordenando o mesmo universo pelo escore de fator pré-declarado.
- Monolítico: o contrafactual em que o modelo devolve pesos diretamente, sem otimizador e sem restrições.

| Comparação | Diferença anualizada | p |
|---|---:|---:|
| Nomeado menos anonimizado (contaminação temporal) | +0,38 p.p. | 0,905 |
| Anonimizado menos determinístico (valor agregado pelo modelo) | −0,05 p.p. | 0,989 |
| Anonimizado menos monolítico (valor do desacoplamento) | +0,81 p.p. | 0,777 |

Os três resultados estatísticos não permitem rejeitar a hipótese de ausência de diferença, e cada um responde a uma pergunta diferente.

1. Não houve diferença detectável entre identificar as empresas pelo nome e ocultar sua identidade. A amostra pequena, porém, não prova ausência de contaminação.
2. O modelo não agregou retorno. O braço anonimizado ficou 0,05 ponto percentual abaixo do controle determinístico, com p = 0,989.
3. Manter o modelo longe dos pesos não penalizou o resultado. Quando recebeu essa função, ele produziu vetores que não somavam 100% em 5 dos 13 anos e omitiu dezenas de ativos elegíveis sem sinalizar. O otimizador garante uma alocação válida antes da explicação.

A conclusão de produto é direta. O modelo de linguagem justifica-se no Benevente por organizar e explicar decisões, não por gerá-las. Vender IA como fonte de alfa, com base nestes dados, seria vender algo que medimos e não encontramos.

### 5.7 Defeitos encontrados na própria auditoria

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

Depois da última correção, o retorno anualizado publicado caiu e a queda máxima subiu de 30,4% para 47,8%. Essa mudança é uma evidência de funcionamento do processo de controle: a auditoria foi capaz de piorar a narrativa quando os dados assim exigiram. Ela não prova que todos os defeitos foram encontrados.

---

## 6. Aplicabilidade, implantação e modelo de uso

### 6.1 Público e proposta de valor

O produto foi concebido para escritórios de investimento, consultorias de valores mobiliários, gestores patrimoniais e escritórios multifamiliares. Para a instituição, o Benevente transforma a documentação em consequência do próprio trabalho: a política aplicada, os dados e seus hashes, a elegibilidade, os pesos, as ordens, o custo estimado e a aprovação permanecem ligados à mesma decisão. Para o profissional, isso reduz o tempo gasto reconstruindo uma recomendação. Para o cliente, permite responder tanto por que um papel entrou quanto por que outro ficou de fora.

O benefício comercial não deve ser apresentado como promessa de superar o mercado. O valor a testar está na consistência do processo, na comparação explícita com alternativas e na capacidade de revisão. O retorno continua sendo medido, acompanhado e discutido, sem se tornar garantia ou substituto da adequação ao perfil do cliente.

### 6.2 Fluxo operacional

O uso começa pela política da instituição. Depois de escolher o perfil e aceitar seus limites, o usuário vê quais arquivos e demonstrações estavam disponíveis e quais passaram na validação. A triagem mostra aprovados e reprovados com o respectivo motivo. A carteira candidata apresenta pesos, parcela defensiva, custo e comparação com CDI, Ibovespa, BOVA11 e MVO. Em seguida, o profissional revisa a tese em linguagem natural, registra riscos, aprova ou rejeita a proposta e informa a justificativa. O dossiê final reúne esse percurso e a versão da regra. Laboratório e documento de decisão são, portanto, duas vistas do mesmo registro, e não etapas desconectadas.

### 6.3 Implantação e piloto comercial

Uma implantação mínima pode ser dividida em três etapas. Na preparação, a instituição define fontes, políticas, perfis de acesso e responsáveis por aprovação. No piloto, o sistema acompanha uma política e um grupo pequeno de carteiras sem enviar ordens, enquanto o escritório confronta os dossiês com o processo que já utiliza. Na operação assistida, a conciliação de custos e posições passa a fechar o ciclo entre proposta e execução. Integração com corretora, custódia, identidade corporativa e arquivo documental pertence a essa última etapa e não precisa bloquear o teste inicial.

A oferta a validar combina licença institucional e implantação. O piloto deve medir tempo de produção, completude da evidência, revisões, diferença entre custo estimado e executado e disposição a pagar. Um teste no Espírito Santo atende ao recorte do congresso, mas não permite presumir retenção de capital ou geração de negócios no estado. Esse efeito exigiria pesquisa econômica própria.

O produto permanece em estágio de protótipo reprodutível. A janela de 2015 a 2025 foi usada no desenvolvimento e descreve a amostra, não o futuro. A avaliação prospectiva começa no registro congelado, cujo hash foi versionado e recebeu data carimbada por terceiro. Essa separação entre diagnóstico e acompanhamento futuro é parte do produto, não apenas uma ressalva acadêmica.

### 6.4 Matriz de evidências

A Tabela 9 delimita o que pode ser afirmado na data da submissão. Ela também serve como contrato de comunicação para a demonstração do produto.

| Afirmação | Evidência disponível | Situação |
|---|---|---|
| O artefato preserva dados, regra, pesos e aprovação | Testes funcionais, hashes e dossiês reproduzíveis | Demonstrada no protótipo |
| A auditoria encontra erros que alteram métricas | Sete defeitos reproduzidos e corrigidos | Demonstrada no desenvolvimento |
| A regra superou comparadores entre 2015 e 2025 | Diagnóstico sequencial e reamostragem interna | Observada, não prospectiva |
| A série histórica tem qualidade institucional | 13,9% da exposição a ações dependeu de imputação | Não demonstrada |
| O modelo de linguagem gera retorno adicional | Diferença de −0,05 p.p. e p = 0,989 | Não demonstrada |
| Há demanda e disposição a pagar | Piloto ainda não executado | Não demonstrada |
| A regra funciona em dados futuros | Registro de 16/08/2026, mínimo de três anos | Em acompanhamento |

---

## 7. Limitações e recomendações

### 7.1 Limitações

A primeira limitação é temporal. Onze decisões anuais são poucas, e a janela avaliada também serviu ao desenvolvimento. O prêmio de retrospectiva de 0,65 ponto percentual e o Sharpe deflacionado tratam parte do risco de múltiplas tentativas, mas não equivalem a validação prospectiva. A reamostragem também não cria regimes que a história não contém.

A segunda limitação está nos dados. A coleta primária avançou para 18.190 eventos e 95,6% dos ativos do painel, mas 22 códigos e 271 eventos manuais ainda bloqueiam a reconciliação integral. Papéis sem cobertura completa recebem, em casos identificados, uma distribuição imputada pela mediana transversal do ano. Essa fragilidade atingiu 13,9% da exposição acumulada a ações e 50% da carteira total em 2020. O novo arquivo melhora a auditabilidade, mas o resultado só poderá ser recalculado e comparado quando o preço bruto, o evento e a conversão estiverem ligados sem lacunas.

A terceira é econômica. A queda máxima diária chegou a 47,8%, nível incompatível com um perfil conservador e ligeiramente pior que os 47,0% do Ibovespa. O protótipo não demonstrou proteção de capital. A extensão de controle de risco concebida depois da Covid-19 é retrospectiva, não tem imposto intranual conciliado e não demonstrou retorno adicional.

Por fim, o produto não elimina responsabilidade profissional. Uso comercial exige enquadramento regulatório, política de suitability, segurança, contrato de fontes e aprovação humana. O modelo de linguagem não antecipou a Covid-19, não seleciona ativos e não define pesos. Notícias também não entram no protocolo atual porque não há, neste experimento, um arquivo histórico com horário de publicação e corte verificável.

### 7.2 Recomendações de pesquisa e implantação

O passo científico prioritário é acumular decisões depois do registro congelado. Em paralelo, a pesquisa deve completar os 22 códigos e resolver os 271 eventos manuais antes de reconstruir o retorno. A reamostragem em blocos já mede dependência serial curta; testes seguintes devem acrescentar trajetórias sintéticas com regimes de baixa prolongada que não estejam limitadas à ordem histórica. Simulação não substitui observação futura. Um estudo com notícias deve ser registrado como braço separado, com frequência trimestral ou orientada a eventos e horário verificável. O passo de produto é um piloto silencioso, sem execução automática, capaz de medir tempo, completude documental, divergência de custos, compreensão do usuário e disposição a pagar.

---

## 8. Conclusão

O Benevente Wealth System foi construído para resolver uma falha operacional específica: carteiras são propostas em um momento e justificadas em outro, enquanto os dados, a regra e a aprovação podem se separar. O protótipo mostrou que é possível produzir a alocação e a evidência da decisão no mesmo fluxo, com fundamentos admitidos pela data de recebimento, regra quantitativa separada da explicação em linguagem natural, custos, imposto e comparadores independentes.

No diagnóstico de 2015 a 2025, a carteira apresentou retorno anualizado superior aos comparadores e queda máxima semelhante à do mercado. A incerteza da amostra e a dependência parcial de séries imputadas impedem tratar essa diferença como superioridade comprovada. Os testes negativos são informativos: a frequência anual não perdeu para reseleções mais rápidas, o modelo de linguagem não acrescentou retorno e a alocação direta por texto produziu carteiras aritmeticamente inconsistentes em parte dos anos. Esses achados justificam um sistema em que a matemática calcula a alocação, a linguagem ajuda a compreendê-la e uma pessoa conserva a responsabilidade final.

A conclusão comprovada é mais estreita e mais defensável que a versão anterior do artigo: o artefato cria uma cadeia auditável e usa essa cadeia para descobrir erros que mudam o próprio resultado. A viabilidade comercial será confirmada somente se um piloto mostrar ganho de tempo, completude documental, compreensão e disposição a pagar. A validade financeira exigirá completar a reconciliação primária e acumular dados posteriores ao registro; a política de risco começa sua amostra confirmatória em 2027. Até lá, o desempenho histórico permanece diagnóstico de desenvolvimento.

---

## 9. Disponibilidade

A versão submetida inclui um pacote suplementar anônimo com o código de reprodução, os artefatos de avaliação e o manifesto criptográfico. Os endereços públicos do sistema e do repositório foram omitidos para preservar a avaliação cega. Após o aceite, a versão para publicação deverá restaurar esses endereços e indicar o arquivo permanente com DOI.

---

## Referências

Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance, 20*(4), 39–69. https://doi.org/10.21314/JCF.2016.322

Bailey, D. H., & López de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. *Journal of Portfolio Management, 40*(5), 94–107. https://doi.org/10.3905/jpm.2014.40.5.094

Banco Central do Brasil. (2026). *Sistema Gerenciador de Séries Temporais: série 12, taxa de juros CDI*. https://www3.bcb.gov.br/sgspub/

B3 S.A. – Brasil, Bolsa, Balcão. (2026a). *Cotações históricas: série histórica de preços dos títulos negociados na Bolsa*. https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/

B3 S.A. – Brasil, Bolsa, Balcão. (2026b). *Ibovespa B3*. https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa.htm

Benevente Wealth System. (2026). *Documentação técnica, repositório de dados e validação de horizontes*. Repositório anônimo de avaliação.

Black, F., & Litterman, R. (1992). Global portfolio optimization. *Financial Analysts Journal, 48*(5), 28–43. https://doi.org/10.2469/faj.v48.n5.28

BlackRock. (2026). *iShares Ibovespa Fundo de Índice (BOVA11): factsheet*. https://www.blackrock.com/br/literature/fact-sheet/bova11-ishares-ibovespa-fundo-de-ndice-fund-fact-sheet-pt-lm.pdf

Comissão de Valores Mobiliários. (2021a). *Resolução CVM nº 19, de 25 de fevereiro de 2021: atividade de consultoria de valores mobiliários* (texto consolidado). https://conteudo.cvm.gov.br/legislacao/resolucoes/resol019.html

Comissão de Valores Mobiliários. (2021b). *Resolução CVM nº 30, de 11 de maio de 2021: adequação dos produtos, serviços e operações ao perfil do cliente* (texto consolidado). https://conteudo.cvm.gov.br/legislacao/resolucoes/resol030.html

Comissão de Valores Mobiliários. (2026a). *Demonstrações Financeiras Padronizadas (DFP): dados abertos*. https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp

Comissão de Valores Mobiliários. (2026b). *Formulário de Informações Trimestrais (ITR): dados abertos*. https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/

DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? *Review of Financial Studies, 22*(5), 1915–1953. https://doi.org/10.1093/rfs/hhm075

Fama, E. F., & French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial Economics, 116*(1), 1–22. https://doi.org/10.1016/j.jfineco.2014.10.010

Harvey, C. R., Liu, Y., & Zhu, H. (2016). … and the cross-section of expected returns. *Review of Financial Studies, 29*(1), 5–68. https://doi.org/10.1093/rfs/hhv059

Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly, 28*(1), 75–105. https://doi.org/10.2307/25148625

Kroll, J. A., Huey, J., Barocas, S., Felten, E. W., Reidenberg, J. R., Robinson, D. G., & Yu, H. (2017). Accountable algorithms. *University of Pennsylvania Law Review, 165*(3), 633–705.

López de Prado, M. (2018). *Advances in financial machine learning*. Wiley.

Markowitz, H. (1952). Portfolio selection. *Journal of Finance, 7*(1), 77–91. https://doi.org/10.2307/2975974

Novy-Marx, R. (2013). The other side of value: The gross profitability premium. *Journal of Financial Economics, 108*(1), 1–28. https://doi.org/10.1016/j.jfineco.2013.01.003

Novy-Marx, R., & Velikov, M. (2016). A taxonomy of anomalies and their trading costs. *Review of Financial Studies, 29*(1), 104–147. https://doi.org/10.1093/rfs/hhv063

Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2007). A design science research methodology for information systems research. *Journal of Management Information Systems, 24*(3), 45–77. https://doi.org/10.2753/MIS0742-1222240302
