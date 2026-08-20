# Benevente Wealth System: um artefato de decisão e governança de carteira para escritórios de investimento do Espírito Santo

**Produção técnica. Fucape Business School, BTech 2026.**

---

## Resumo

Escritórios de investimento capixabas, entre multi-family offices, consultorias de valores mobiliários e assessorias, recomendam carteiras que precisam ser justificadas meses depois de montadas, diante do cliente, do compliance ou do regulador. Três perguntas voltam sempre: quais dados existiam na data da decisão, qual regra foi aplicada sobre eles, e quem aprovou. Planilha não responde nenhuma. Plataforma de terceiro responde a segunda de forma opaca. Este trabalho descreve o Benevente Wealth System, um artefato de software que produz a recomendação e a trilha de auditoria no mesmo ato. Cada decisão anual sai acompanhada da política vigente, dos fundamentos da CVM com data de recebimento, da tela de elegibilidade com o motivo de cada reprovação, dos pesos, das ordens propostas com lote e participação no volume, do custo estimado, e do SHA-256 de cada arquivo que gerou cada número. O artefato foi avaliado em uma janela de onze decisões anuais, de 2015 a 2025, sobre um painel da B3 construído a partir do arquivo histórico de cotações, que retém os 166 emissores deslistados no período. A carteira publicada, agora denominada Benevente 1, rendeu 17,86% ao ano após custos, ou 16,03% após imposto de renda, contra 11,77% do Ibovespa, 9,61% do CDI e 7,83% de uma otimização média-variância independente sobre o mesmo universo elegível. Venceu o mercado em sete dos onze anos e a otimização neutra em dez. Uma extensão experimental, Benevente 2, preserva a seleção anual e reduz temporariamente a exposição quando queda e volatilidade observadas no fechamento anterior ultrapassam limiares registrados. Na amostra completa ela reduziu a queda máxima de 47,8% para 28,7%, mas no recorte temporal de 2019 a 2025 não demonstrou retorno adicional (p = 0,964). Reportamos também o que não funcionou: previsão anual de regime, realocação mensal e semanal da proporção entre ações e caixa, reseleção mais frequente da própria cesta, e o uso de um modelo de linguagem como fonte de retorno. A contribuição tecnológica não é uma promessa de rentabilidade. É o conjunto de mecanismos que torna o resultado auditável, inclusive quando uma melhoria protege o capital sem comprovar alfa.

**Palavras-chave:** governança de investimentos; trilha de auditoria; alocação de carteira; dados datados; viés de sobrevivência; pesquisa reprodutível.

---

## 1. Situação-problema

Este trabalho parte de uma hipótese de mercado a ser validada no piloto: escritórios do Espírito Santo que mantêm o relacionamento com famílias e empresas locais podem depender de infraestrutura de decisão produzida fora do estado. O problema proposto não é falta de competência analítica. É a ausência de uma ferramenta que produza, no ato da recomendação, o registro que a recomendação vai exigir depois. A pesquisa ainda não mede o tamanho desse mercado, a disposição a pagar ou a taxa de adoção. Portanto, retenção de capital e geração de negócios no estado são resultados esperados do produto, não resultados já comprovados.

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

Quatro referências clássicas orientam a construção financeira do artefato. Markowitz (1952) mostrou que uma carteira precisa ser analisada pela interação entre retornos e covariâncias, e não pela atratividade isolada de cada ativo. No Benevente, essa contribuição aparece de duas formas. A primeira é a exigência de uma cesta, em vez de uma aposta única no maior escore. A segunda é o comparador MVO, que pergunta quanto uma alocação baseada apenas em média, covariância e limites teria produzido sobre o mesmo universo. O comparador não serve para validar automaticamente a estratégia; serve para impedir que um ganho atribuído ao filtro fundamental seja apenas efeito de diversificação quantitativa.

Black e Litterman (1992) tratam da combinação entre equilíbrio de mercado e visões. A arquitetura do Benevente adota a separação conceitual, mas não implementa o modelo Black–Litterman como carteira publicada. Fatos fundamentais e sinais de mercado geram um ranking determinístico. A linguagem natural pode explicar a visão, registrar riscos e formular perguntas, porém não altera a matemática da alocação. Essa fronteira permite testar a camada de linguagem sem conceder a ela poder para mudar restrições ou reconstruir retrospectivamente a tese.

DeMiguel, Garlappi e Uppal (2009) demonstram como erro de estimação pode eliminar, fora da amostra, a vantagem aparente de métodos sofisticados sobre uma diversificação simples. A resposta do projeto não é presumir que um otimizador sempre melhora o resultado. É publicar uma referência independente, impor um número mínimo de posições, limitar a interpretação das métricas e comparar decisões em sequência temporal. O resultado de 7,83% ao ano do MVO de referência nesta execução não prova que MVO é inferior em geral. Mostra somente que aquela implementação, com aquele universo elegível e aquelas estimativas disponíveis em cada janeiro, produziu esse caminho. Em outra amostra ou especificação, a ordem pode se inverter.

Novy-Marx e Velikov (2016) mostram que custos de negociação podem consumir anomalias documentadas. Por isso, o retorno usado na manchete já deduz taxas e deslizamento modelado, e a busca penaliza trocas de configuração. O sistema mede giro, participação no volume e realização tributável, em vez de tratar toda mudança de peso como gratuita. Ainda assim, uma estimativa não é uma nota de corretagem. O produto prevê conciliação posterior exatamente porque o custo observado depende do tamanho, do horário, da liquidez e da qualidade de execução de cada instituição.

Essas escolhas definem o tipo de evidência que o trabalho pode produzir. O backtest é um experimento histórico sobre um protocolo e não uma simulação da experiência individual de todo cliente. Suitability, necessidade de liquidez, tributação específica, ativos já detidos e restrições contratuais podem mudar a carteira implementável. Por isso, o artefato separa três objetos que costumam aparecer misturados: a regra acadêmica usada para medir o sinal; a política institucional que limita o risco; e o texto explicativo que ajuda uma pessoa a revisar a decisão. Uma boa curva não substitui nenhum dos três.

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
| Seleção e alocação | Escore multifatorial e regra quantitativa com limites | Ranking, pesos e restrições ativas |
| Execução | Ordens com lote e participação no volume | Custo estimado por ordem |
| Governança | Aprovação humana e conciliação | Quem aprovou e diferença contra a nota de corretagem |

### 3.2 Base de dados: o universo de registro é a bolsa, não o provedor

O universo de registro é o arquivo histórico de cotações da própria B3, não um feed de terceiro. A consequência é direta e mensurável. O painel construído cobre 514 emissores entre 2010 e 2025, dos quais 166 deixam de negociar antes de dezembro de 2025, 77 deles antes de 2020, e 58 já haviam perdido mais de 60% do próprio topo quando pararam de negociar. Um painel montado a partir de provedor público simplesmente não contém essas empresas. A diferença entre incluí-las e não incluí-las é a diferença entre medir a estratégia e medir a sorte de ter olhado só para os sobreviventes.

Preços deslistados exigem tratamento de eventos societários sem a ajuda do provedor, que já não serve esses papéis. O sistema detecta desdobramentos, grupamentos e bonificações grandes a partir de razões de preço redondas e persistentes no arquivo da bolsa. O detector foi validado contra o arquivo de eventos de um provedor, no subconjunto de papéis em que esse arquivo existe, e os dois lados da validação são publicados: precisão de 88,1%, com 340 de 386 ajustes aplicados coincidindo com um evento confirmado, e recall de 23,3%, com 103 de 443 eventos do provedor detectados. O recall baixo é uma limitação real e está declarada. O detector é conservador por construção, e prefere não ajustar a ajustar errado. Publicar apenas a precisão seria omitir metade do resultado.

Os fundamentos vêm dos formulários ITR e DFP da CVM, com a data de recebimento usada como porta: um documento só entra na decisão de janeiro do ano *t* se o regulador o recebeu antes daquela data. A ponte entre o ticker da B3 e o CNPJ da CVM é construída ano a ano, e sua cobertura é publicada em vez de suposta. Em 2012, primeiro ano da série, 266 de 314 ações tiveram ponte aceita e 171 tiveram fundamentos completos, porque a série do ITR começa em 2011 e 2012 é o primeiro ano em que a construção de doze meses tem os dois lados disponíveis.

### 3.3 Elegibilidade, seleção e alocação

A tela de elegibilidade reprova ativos por liquidez insuficiente, ausência de fundamento na data, alavancagem ou cobertura de juros fora do aceitável. Cada reprovação é registrada com o motivo, o que permite ao escritório responder por que um papel conhecido não entrou, pergunta que aparece com a mesma frequência da inversa.

O foco econômico é **análise fundamentalista multifatorial**. Qualidade procura empresas capazes de remunerar o capital e sustentar a operação; valor procura um preço coerente com lucros, patrimônio ou geração de caixa; momento de doze meses funciona como confirmação de mercado e reduz a compra mecânica de uma empresa barata que continua deteriorando. Liquidez determina se a tese é executável. Bancos e empresas operacionais recebem métricas diferentes porque dívida e margem operacional não significam a mesma coisa nos dois balanços. O retorno histórico entra como fator complementar, não substitui os demonstrativos.

Depois da triagem, cada ativo recebe um escore comparável dentro do universo disponível naquele janeiro. A estratégia publicada faz um corte nos melhores emissores, mantém apenas uma classe por emissor e distribui o orçamento de renda variável proporcionalmente ao escore, sujeito ao número de posições e aos limites da configuração. O saldo fica no CDI. A configuração completa — família de fatores, número de posições e orçamento de ações — é escolhida anualmente pelo desempenho ajustado ao risco nos anos já encerrados. A otimização média-variância não define essa carteira. Ela é calculada de modo independente, sobre o mesmo universo elegível, para medir o que uma carteira puramente quantitativa de média e covariância teria produzido.

Essa separação também resolve a ambiguidade entre os nomes. **Benevente Quant AI** designa a pesquisa acadêmica, inclusive o experimento que combina um modelo de linguagem com um solver convexo. **Benevente Wealth System** designa o produto B2B de governança que entrega proposta, explicação e registro. A carteira histórica publicada é a regra multifatorial determinística. O modelo de linguagem não seleciona ativo e não escreve peso; seu papel é transformar fatos aprovados em tese, riscos e perguntas para revisão humana.

Os coeficientes do escore de seleção, os limiares da tela de elegibilidade, as constantes de aversão a risco e a grade de configurações não são publicados. Eles estão registrados de forma verificável, porque o registro congelado carrega o SHA-256 de cada arquivo de entrada e da própria configuração, de modo que a anterioridade é demonstrável sem que a implementação seja replicável por leitura. Essa é uma escolha comercial deliberada e está declarada aqui para que o leitor saiba exatamente o que está sendo e o que não está sendo divulgado.

### 3.4 Por que a decisão é anual

A cadência anual é uma hipótese coerente com a natureza do sinal e, neste estudo, uma escolha empiricamente testada. Qualidade, retorno sobre capital, alavancagem e geração de caixa são grandezas divulgadas em ciclos contábeis e cuja tese econômica precisa de tempo para aparecer no preço. Uma troca mensal baseada nelas pode vender uma empresa antes que a melhora operacional seja reconhecida e aumenta o número de decisões que precisam ser justificadas. A revisão em janeiro também cria uma fronteira operacional simples: tudo o que foi publicado até a data pode entrar; tudo o que veio depois pertence ao próximo ciclo.

Anual não significa que o sistema ignora o risco durante doze meses. Preços, concentração, liquidez e eventos materiais podem ser monitorados continuamente, e uma política institucional pode prever um gatilho extraordinário. Significa apenas que a **reseleção sistemática** da cesta acontece uma vez por ano. No teste de robustez, mantendo regra e dados constantes, a reseleção anual superou as versões trimestral e mensal antes mesmo dos custos. Com apenas onze anos pareados, isso não prova que a frequência anual seja universalmente ótima; mostra que não houve evidência para substituir a regra mais simples nesta amostra.

Notícias não entram no modelo atual. Esse limite é intencional: um estudo com notícias exige arquivo histórico licenciado, horário de publicação, deduplicação e uma data de corte verificável para o modelo de linguagem. Misturar notícias retrospectivamente ao protocolo anual criaria uma nova oportunidade de usar informação futura. O estudo futuro adequado é um braço separado, pré-registrado, com revisão trimestral ou por evento e notícias carimbadas no tempo, comparado à regra anual sem alterar esta última.

### 3.5 Custos, imposto e execução

Retorno bruto não é resultado. O sistema modela três parcelas.

- **Taxas da B3** e corretagem por ordem.
- **Deslizamento por participação no volume**, proporcional ao tamanho da ordem relativo ao volume médio diário do papel. Uma ordem grande em papel ilíquido custa mais, como custa na prática.
- **Imposto de renda brasileiro**, com 15% sobre ganho realizado em renda variável e 17,5% sobre renda fixa na faixa de 361 a 720 dias, cobrado no ano em que a revisão seguinte efetivamente realiza o ganho, e com liquidação integral assumida no último ano avaliado. Essa é a hipótese terminal conservadora, em vez de um diferimento indefinido que embelezaria a série.

O sistema recusa, por regra, ordens que ultrapassem 5% do volume médio diário do papel. A ordem falha em vez de ser enviada.

### 3.6 Governança: o sistema propõe, a pessoa decide

Quatro mecanismos delimitam o que o software pode fazer.

1. **Aprovação humana obrigatória.** Nenhuma ordem é transmitida, nem pode ser, porque a arquitetura não tem esse caminho.
2. **Papel delimitado do modelo de linguagem.** O modelo organiza tese e riscos a partir de fatos já aprovados. Ele não define peso, não altera limite e não aprova ativo. Isso é uma restrição de arquitetura verificável, não uma promessa de conduta, e a Seção 5.5 mostra o experimento que testou o que aconteceria se ela fosse relaxada.
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

### 4.4 Benevente 2: proteção intranual sem trocar a tese anual

O Benevente 1 continua sendo a estratégia publicada: a cesta e o orçamento de risco são definidos na revisão anual e os ativos são mantidos até a revisão seguinte. O Benevente 2 é uma extensão experimental que não escolhe ações novas e não usa notícias. Ele observa somente a queda do Ibovespa em relação ao pico móvel de 126 sessões e a volatilidade realizada em 20 sessões, sempre deslocadas em um pregão. Assim, a decisão de hoje usa apenas o fechamento de ontem.

A configuração candidata foi escolhida somente em 2015--2018. Um alerta é acionado com queda de 12% ou volatilidade anualizada de 40%, limitando a exposição a ações a 50%. O estado severo usa 22% e 60%, respectivamente, e limita a exposição a 35%. A saída exige dez sessões de recuperação, para reduzir idas e vindas. O saldo migra para CDI e cada mudança paga 0,10% por unidade de giro. O período de 2019--2025 é lido separadamente como avaliação retrospectiva. A extensão foi concebida depois da Covid-19, portanto essa separação temporal não elimina o viés conceitual e não equivale a validação prospectiva.

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

### 5.2 Benevente 2: o que melhorou e o que não foi provado

| Série | CAGR 2015--2025 | Queda máxima diária | CAGR 2019--2025 |
|---|---:|---:|---:|
| Benevente 1 | 17,86% | −47,8% | 17,95% |
| **Benevente 2, experimental** | **18,45%** | **−28,7%** | **18,03%** |

Na crise de 2020, o primeiro alerta ocorreu em 28/02/2020 e o estado severo em 10/03/2020. A exposição mínima ficou em 35%. O Benevente 1 terminou o ano com 1,78%, o Benevente 2 com 4,35% e o Ibovespa com 0,62%. A queda máxima caiu de 47,8% para 28,7%, enquanto a do índice foi de 46,8%.

O resultado de retorno exige contenção. No recorte 2019--2025 a diferença de CAGR entre as versões foi de apenas 0,09 ponto percentual e o teste pareado anual produziu p = 0,964. Portanto, não há evidência de alfa adicional. Numa grade de sensibilidade com 432 configurações, todas reduziram a queda máxima, mas apenas 9,03% melhoraram simultaneamente CAGR e queda no recorte de avaliação. A conclusão sustentada é **redução robusta de risco de cauda**, não aumento comprovado de rentabilidade. Os números do Benevente 2 incluem custo de giro do controle intranual, mas ainda não o imposto gerado por vendas dentro do ano. Por isso ele permanece experimental e não substitui a série canônica.

### 5.3 O resultado sobrevive à correção por múltiplas tentativas?

| Estatística | Valor |
|---|---:|
| Sharpe observado do excesso sobre o CDI | 0,933 |
| Sharpe máximo esperado sob a hipótese nula, com 36 tentativas | 0,355 |
| **Sharpe deflacionado** | **0,986** |
| Significante a 95% | sim |
| **Prêmio de retrospectiva** | **0,65 p.p. ao ano** |

O prêmio de retrospectiva merece leitura cuidadosa, porque é a medida mais informativa do conjunto. Ele diz que escolher a configuração vencedora sabendo o desfecho teria rendido apenas 0,65 ponto percentual a mais por ano do que a escolha aninhada, que não sabia. Em uma versão anterior deste mesmo sistema, com um ano a menos de treino, esse prêmio era de 4,98 pontos, ou seja, a busca estava fazendo boa parte do trabalho. Estender a base de dados para permitir decisões desde 2012 reduziu o prêmio por um fator de sete e elevou o Sharpe deflacionado de 0,957 para 0,986. O ganho relevante da última iteração do artefato não foi retorno. Foi a redução da parcela do retorno atribuível à própria busca.

### 5.4 O que não funcionou

Quatro hipóteses foram testadas e nenhuma se sustentou. São publicadas com o mesmo destaque do resultado positivo, porque um artefato que só reporta o que deu certo não é auditável.

**Previsão anual de regime.** Testamos se indicadores disponíveis em janeiro, entre prêmio de lucro sobre o CDI, nível do CDI, retorno e volatilidade do mercado nos doze meses anteriores e distância do topo, anteciparam se o ano seria de ações ou de caixa. Sobre 8 anos, o melhor preditor acertou 3 de 4 chamadas efetivas, com p de 0,31 contra cara-ou-coroa. Um acerto de 75% em quatro tentativas não distingue habilidade de sorte. O prêmio disponível para quem acertasse todas as chamadas era de 6,5 pontos percentuais ao ano, e permanece inalcançável. Sem sinal.

**Realocação mensal e semanal.** Aumentamos as observações para responder à objeção de poder estatístico. Foram 118 períodos mensais e 521 períodos semanais, com sete regras de alocação contínua testadas em cada frequência. Nenhuma das sete regras superou o peso estático de forma estatisticamente significante em nenhuma das duas frequências, e uma delas, a de média-variância, foi significativamente pior. O oráculo, que conhece o futuro, teria feito 72,8% ao ano no mensal e 137,1% no semanal, contra 21,1% do estático. O prêmio por acertar o tempo é enorme, e nada que testamos consegue capturá-lo. Rejeitada.

**Reseleção mais frequente da cesta.** A objeção seguinte é diferente da anterior e precisa ser separada dela: não se a proporção entre ações e caixa deve mudar mais vezes, que é o que o parágrafo acima rejeita, mas se a própria cesta deveria ser retriada, reordenada e reotimizada mais vezes por ano. Testamos três cadências com a mesma regra, os mesmos limites e o mesmo painel, variando apenas as datas de decisão.

| Cadência | Decisões | CAGR bruto | Líquido de custo | Após IR | Giro no ano |
|---|---:|---:|---:|---:|---:|
| **Anual** | 11 | **18,58%** | **18,51%** | **17,09%** | 62,1% |
| Trimestral | 44 | 16,37% | 16,25% | 15,60% | 116,0% |
| Mensal | 132 | 13,92% | 13,75% | 13,32% | 177,6% |

Nenhuma cadência mais rápida superou a anual. Pareando por ano-calendário, a trimestral fica 1,55 ponto percentual abaixo ao ano após imposto, com p de 0,376, e a mensal 3,27 pontos abaixo, com p de 0,306. A leitura correta é que **não há evidência de que decidir mais vezes ajude**, e não que esteja provado que atrapalhe: onze anos pareados não sustentam a afirmação mais forte.

O mecanismo contraria a intuição corrente, que atribuiria a diferença a custo e imposto. A perda está no retorno bruto, que cai 4,66 pontos de anual para mensal antes de qualquer dedução. O custo de execução sobe apenas 0,08 ponto ao ano, e o imposto modelado até diminui, porque cada revisão mensal realiza uma fatia menor do livro. Ou seja, decidir mais vezes piora a seleção antes de encarecer a operação. O sinal combina qualidade, valor e momento, grandezas que se movem em horizonte anual, e reordenar todo mês troca posições antes que a tese tenha tempo de se realizar.

Registramos uma fraqueza do modelo tributário nessa comparação: ele cobra imposto sobre o ganho do próprio período, e não sobre o ganho acumulado da posição efetivamente vendida, o que subestima a conta do braço mensal. O viés favorece a cadência mais rápida, e ela perdeu mesmo assim, então a conclusão é robusta a essa limitação.

**Modelo de linguagem como fonte de retorno.** Este é o teste que mais interessa à governança do produto, e está detalhado a seguir.

### 5.5 O experimento com modelo de linguagem: três nulos

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
3. **O desacoplamento não custa desempenho.** Manter o modelo longe dos pesos não penalizou o resultado, e se algo o braço desacoplado foi melhor. O braço monolítico, que recebeu a caneta, **não estourou nenhum teto**, o que é uma constatação a favor dele e precisa ser dita. O que ele produziu foram carteiras aritmeticamente inválidas: os pesos não somavam um em 5 dos 13 anos, variando de 0,92 a 1,017, e em 2021 e 2022 omitiu 65 e 83 ativos elegíveis sem sinalizar. O otimizador não se justifica por impedir violação de limite, e sim por devolver uma alocação válida que não precise de conserto depois.

A conclusão de produto é direta. O modelo de linguagem justifica-se no Benevente por organizar e explicar decisões, não por gerá-las. Vender IA como fonte de alfa, com base nestes dados, seria vender algo que medimos e não encontramos.

### 5.6 Defeitos encontrados na própria auditoria

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

O fluxo de uso foi desenhado para que cada tela responda à pergunta criada pela anterior. Primeiro, a instituição escolhe a política e aceita os limites. Segundo, o sistema mostra quais arquivos e demonstrações estavam disponíveis e quais passaram na validação. Terceiro, a triagem informa ativos aprovados e reprovados com motivos. Quarto, a carteira candidata apresenta pesos, parcela em CDI, custo e comparação com as referências. Quinto, a pessoa revisa a tese em linguagem natural, aprova ou rejeita e registra a justificativa. Por fim, o dossiê reúne a decisão inteira, inclusive a versão da regra e os hashes dos arquivos. O usuário não precisa alternar entre um laboratório técnico e um documento separado; a experiência e a prova são duas visões do mesmo registro.

**Para o escritório.** O sistema entrega, por decisão, um dossiê completo, com política aplicada, dados com data e hash, tela de elegibilidade com motivo de cada reprovação, pesos, ordens com lote e participação no volume, e custo estimado. O que antes era reconstruído a mão sob pressão passa a ser subproduto da própria operação.

**Para o cliente final.** A pergunta "por que este papel?" passa a ter resposta datada e verificável, e a pergunta simétrica, "por que não aquele?", também.

**Para o ecossistema capixaba.** A hipótese comercial não é “rendemos mais”. É que um escritório local com processo demonstrável pode reter uma parcela maior do trabalho analítico e do relacionamento de longo prazo no estado. Essa hipótese precisa ser testada em entrevistas e pilotos; o backtest não a comprova.

**Modelo de oferta a validar.** A primeira versão comercial pode ser licenciada por instituição, com cobrança por usuários e número de políticas acompanhadas, e um serviço de implantação para integrar fontes, identidade, aprovação e arquivo documental. Não há preço publicado nem receita comprovada. As métricas do piloto devem ser tempo para produzir um dossiê, percentual de decisões com evidência completa, divergência entre custo previsto e nota conciliada, número de revisões exigidas e disposição a pagar. Retorno da carteira permanece uma medida de pesquisa e acompanhamento, nunca base de remuneração ou garantia contratual.

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
7. **O Benevente 2 é retrospectivo e posterior à Covid-19.** A escolha em 2015--2018 e a leitura separada de 2019--2025 evitam usar o retorno futuro na conta diária, mas não removem o conhecimento humano de que uma crise sanitária ocorreu.
8. **O imposto intranual do Benevente 2 ainda não foi reconciliado.** Custos de giro foram cobrados, mas vendas defensivas podem antecipar imposto e reduzir o resultado líquido.
9. **Não existe arquivo histórico de notícias com horário validado neste experimento.** O controle usa apenas preço e volatilidade. A LLM não antecipou a Covid-19 e não tomou decisões no Benevente 2.

---

## 8. Agenda

- Acumular anos avaliados depois do registro congelado, que é a única evidência capaz de mudar o estatuto do artefato de pesquisa para validado.
- Reconciliar eventos societários e proventos contra registro primário, elevando o recall do detector.
- Repetir o experimento de contaminação em modelos com datas de corte de treinamento distintas, para separar contaminação de capacidade.
- Pré-registrar um estudo trimestral ou orientado a eventos, com notícias arquivadas, horário de publicação e corte temporal verificável, sem reotimizar a regra anual depois de observar o resultado.
- Pré-registrar o Benevente 2 antes de qualquer acompanhamento futuro, incorporar imposto por lote vendido e comparar seus estados discretos a um alvo contínuo de volatilidade escolhido somente na janela de treino.
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
- BLACK, F.; LITTERMAN, R. Global Portfolio Optimization. *Financial Analysts Journal*, v. 48, n. 5, p. 28–43, 1992.
- DEMIGUEL, V.; GARLAPPI, L.; UPPAL, R. Optimal versus naive diversification: how inefficient is the 1/N portfolio strategy? *The Review of Financial Studies*, v. 22, n. 5, p. 1915–1953, 2009.
- NOVY-MARX, R.; VELIKOV, M. A taxonomy of anomalies and their trading costs. *The Review of Financial Studies*, v. 29, n. 1, p. 104–147, 2016.
- BENEVENTE WEALTH SYSTEM. **Documentação técnica, repositório de dados e validação de horizontes**. Repositório do projeto, 2026.

---

### Nota sobre a origem dos números

Todos os valores deste texto foram extraídos dos artefatos de execução do sistema, não transcritos de versões anteriores do material. As fontes primárias são `artifacts/published_nested/annual_results.csv` para a série anual publicada, `artifacts/audit_evidence/audit_evidence.json` para o placar anual e as janelas móveis, `artifacts/configuration_search_2012/summary.json` para a busca de configuração, o Sharpe deflacionado e o prêmio de retrospectiva, `artifacts/benevente2_event_risk/` para a candidata, a série diária e as 432 sensibilidades do Benevente 2, `artifacts/alloc_monthly/` e `artifacts/alloc_weekly/` para a realocação, `artifacts/allocation_regime/` para o regime anual, `artifacts/llm_contamination/summary.json` para o experimento com modelo de linguagem, e o manifesto do painel de preços, que carrega o SHA-256 do arquivo que gerou cada série.
