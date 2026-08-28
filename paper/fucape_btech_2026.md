# Benevente: um artefato auditável para decisões de carteira por perfil de investidor

---

## Resumo

Decisões de carteira precisam permanecer explicáveis depois de executadas. Este trabalho constrói e avalia o Benevente, um sistema que registra, para cada decisão, os dados admitidos, a regra quantitativa vigente, a carteira proposta, a explicação e a aprovação humana. A pesquisa segue design science e combina testes funcionais, auditoria adversarial e diagnóstico sequencial de onze decisões anuais entre 2015 e 2025. A política vigente declara três perfis, do conservador ao arrojado, com orçamento de renda variável, número de emissores e fração internacional congelados em registro público antes do período confirmatório, que começa em 2027. A declaração substituiu a busca de configurações depois de um experimento controlado: ampliar a seleção aninhada de 36 para 256 candidatos, com insumos idênticos, reduziu o retorno realizado em 2,63 pontos percentuais ao ano e levou o índice de Sharpe deflacionado de 0,957 a 0,777, abaixo do limiar de significância. Versão posterior trocou o caixa modelado por um instrumento comprável, e o retorno de cada perfil caiu entre 0,07 e 0,17 ponto ao ano (Seção 4.1.2). A auditoria dimensionou a dependência de proventos imputados, 13,9% da exposição acumulada a ações, recusou o selo de reconciliação externa após comparar 54 de 56 observações ativo-ano com a fonte primária, e manteve os intervalos de 95% do excesso cruzando zero contra caixa e Ibovespa. Os retornos históricos são, portanto, diagnóstico de desenvolvimento, não validação comercial. O modelo de linguagem não demonstrou ganho de retorno e permanece restrito à explicação. A contribuição é um fluxo verificável que separa dado, cálculo, linguagem e responsabilidade.

Palavras-chave: governança de investimentos; alocação de carteira; trilha de auditoria; design science; pesquisa reprodutível.

---

## 1. Introdução: problema, objetivo e contribuição

O problema é operacional: a recomendação é produzida hoje e defendida anos depois; sem preservar dado admitido, versão da regra e aprovação, a justificativa posterior incorpora informação que não existia. O Benevente produz proposta e registro verificável no mesmo fluxo. Intensidade do problema e disposição a pagar ainda dependem de piloto; o artigo não presume impacto regional nem demanda.

Quando um cliente pergunta por que uma ação entrou na carteira anos antes, o escritório precisa demonstrar três coisas.

1. Quais dados existiam naquela data: um balanço republicado em 2024 não pode aparecer como disponível em janeiro de 2023, e sem controle de data de recebimento a justificativa fica contaminada por informação que ninguém tinha.
2. Qual regra estava vigente naquele janeiro, com os limites de então, e não a regra de hoje.
3. Quem aprovou: decisão sem responsável identificado não é auditável, e automação sem aprovação humana desloca a responsabilidade para um sistema que não pode respondê-la.

Uma planilha sobrescreve o próprio estado e perde a autoria das alterações; um sistema fechado entrega a carteira sem evidenciar o critério. O artefato deve permitir que um terceiro refaça a decisão sem depender da memória de quem a produziu.

A pergunta prioritária, como usar modelos de linguagem acessíveis à comunidade para apoiar decisões de investimento, torna-se no Benevente uma questão de engenharia e governança: como produzir proposta e prova no mesmo fluxo, sem transferir ao texto gerado a seleção, os pesos ou a responsabilidade.

O objetivo é construir e avaliar um artefato B2B que transforme cada recomendação em documento verificável, pelo método do design science: identificar o problema, explicitar requisitos, construir e avaliar por utilidade, qualidade e evidência (Hevner et al., 2004; Peffers et al., 2007). A avaliação combina testes, inspeção das fontes, busca deliberada de erros e diagnóstico histórico. A contribuição reúne um protocolo reexecutável e um fluxo que preserva quem decidiu, com qual informação e política. O retorno passado mede o comportamento do protótipo, não sua utilidade nem o desempenho futuro.

---

## 2. Problema prático e fundamentação

O público inicial são escritórios de investimento, consultorias de valores mobiliários e gestão patrimonial que precisam recomendar, revisar e defender carteiras: preservar o contexto da decisão, demonstrar por que cada ativo entrou ou não, e comparar com alternativas reconhecíveis pelo cliente. O piloto comercial proposto, descrito na Seção 6.3, medirá o problema e a utilidade do artefato, sem presumir efeito sobre a economia local.

Três vieses clássicos de backtesting foram tratados como requisitos de projeto. O viés de sobrevivência é mitigado ao reconstruir o universo pelo arquivo histórico da B3 e manter os deslistados; ainda resta reconciliar integralmente seus eventos societários. O viés de antecipação, ou *look-ahead*, é mitigado pela data de recebimento de ITR e DFP e pelo corte anual; republicações e fontes auxiliares continuam sujeitas a inspeção. O viés de mineração de dados, ou *data-snooping*, é limitado pela seleção aninhada, pelo prêmio de retrospectiva e pelo Sharpe deflacionado (Bailey & López de Prado, 2014), mas onze decisões não substituem uma amostra prospectiva.

Markowitz (1952) fundamenta a comparação média-variância, ou MVO, calculada de modo independente sobre o mesmo conjunto elegível. Black e Litterman (1992) inspiram apenas a separação entre visões e alocação, não um modelo implementado. DeMiguel, Garlappi e Uppal (2009) justificam diversificação e cautela diante do erro de estimação; o MVO de 7,83% ao ano nesta execução descreve um comparador específico, não inferioridade geral. Qualidade, valor e confirmação de mercado dialogam com Novy-Marx (2013) e Fama e French (2015). Custos, giro e deslizamento entram no protocolo porque atritos podem consumir anomalias (Novy-Marx & Velikov, 2016).

A literatura recente separa utilidade narrativa de capacidade preditiva: Perlin et al. (2025), com 30 mil simulações e 1.522 empresas anonimizadas, não encontram superioridade consistente de LLM sobre 1/N ou S&P 500; Pelster e Val (2024) defendem o experimento ao vivo contra conhecimento posterior; Kim, Muhn e Nikolaev (2024) mostram extração narrativa útil sem alfa de negociação; Li et al. (2026, FINSABER) veem vantagens aparentes se deteriorarem em universos amplos e regimes distintos; FINCON (Yu et al., 2024) inspira divisão de responsabilidades, não autonomia. Esse conjunto sustenta a escolha do Benevente: a regra calcula, o modelo apenas explica fatos aprovados, e a utilidade será avaliada prospectivamente.

Essas escolhas definem o tipo de evidência que o trabalho pode produzir. O backtest é um experimento histórico sobre um protocolo, não uma simulação da experiência de cada cliente, cuja carteira implementável depende de suitability, liquidez, tributação e restrições contratuais. O artefato separa, por isso, a regra que mede o sinal, a política institucional que limita o risco e o texto explicativo que apoia a revisão humana.

---

## 3. O artefato

### 3.1 Visão geral

O Benevente é um sistema de apoio à decisão que executa um protocolo anual. Em janeiro, monta a carteira usando exclusivamente dados disponíveis naquela data. Mantém a carteira pelo ano, já com custos de execução. Revisa no ciclo seguinte. O resultado do ano entra depois, apenas para avaliação, e nunca retroalimenta a decisão que o gerou.

O sistema é composto por cinco camadas.

| Camada | Função | Saída auditável |
|---|---|---|
| Base de dados | Universo, preços e fundamentos com data | Manifesto com SHA-256 por arquivo |
| Elegibilidade | Tela de aprovação por ativo | Motivo de cada reprovação |
| Seleção e alocação | Escore multifatorial e regra quantitativa com limites | Ranking, pesos e restrições ativas |
| Execução | Ordens com lote e participação no volume | Custo estimado por ordem |
| Governança | Aprovação humana e conciliação | Quem aprovou e diferença contra a nota de corretagem |

[[FIGURE:architecture]]

O fluxo da Figura 1 separa funções que costumam aparecer misturadas: dados e fundamentos alimentam a validação; somente os ativos aceitos seguem para o cálculo; o motor quantitativo devolve pesos válidos e custos estimados; a pessoa revisa a proposta antes da aprovação. O modelo de linguagem recebe apenas fatos já calculados e os converte em nota legível, sem caminho de retorno para alterar pesos, e o dossiê registra cada etapa.

### 3.2 Base de dados: o universo de registro é a bolsa, não o provedor

O universo de registro é o arquivo histórico de cotações da própria B3, não um feed de terceiro. O painel construído cobre 514 emissores entre 2010 e 2025, dos quais 166 deixam de negociar antes de dezembro de 2025, 77 deles antes de 2020, e 58 já haviam perdido mais de 60% do próprio topo quando pararam de negociar. Um painel montado a partir de provedor público não contém essas empresas; excluí-las equivaleria a medir apenas os sobreviventes e a superestimar o retorno da estratégia.

Preços de papéis deslistados exigem reconstruir eventos societários sem ajuda do provedor. O detector de razões redondas obteve precisão de 88,1% e recall de 23,3%; para retirá-lo da posição de fonte principal, uma rotina consultou a página pública da B3 (2026b), que respondeu para 475 das 497 séries, com 9.772 registros, 127 subscrições e 153 eventos manuais; 22 códigos ficaram sem resposta. Entre as 56 observações ativo-ano efetivamente mantidas, 54 puderam ser reconstruídas com o arquivo atual; sete divergiram do retorno ajustado publicado em mais de cinco pontos percentuais e duas observações de MRFG3 ficaram sem resposta. A série publicada continua como dado de pesquisa até que uma base histórica primária ou licenciada reproduza cada retorno desde o preço bruto.

Os fundamentos vêm dos formulários ITR e DFP da CVM, com a data de recebimento usada como porta: um documento só entra na decisão de janeiro do ano *t* se o regulador o recebeu antes daquela data. A ponte entre o ticker da B3 e o CNPJ da CVM é construída ano a ano e sua cobertura é publicada: em 2012, primeiro ano da série, 266 de 314 ações tiveram ponte aceita e 171, fundamentos completos.

### 3.3 Elegibilidade, seleção e alocação

A tela de elegibilidade reprova ativos por liquidez insuficiente, ausência de fundamento na data, alavancagem ou cobertura de juros fora do aceitável. Cada reprovação é registrada com o motivo, o que permite responder por que um papel conhecido não entrou.

O foco econômico é uma análise fundamentalista multifatorial: qualidade avalia a capacidade de remunerar o capital; valor exige preço coerente com lucros, patrimônio ou geração de caixa; o momento de doze meses funciona como confirmação de mercado; a liquidez determina se a tese é executável. Bancos e empresas operacionais recebem métricas distintas, e o retorno histórico entra como fator complementar, sem substituir os demonstrativos.

Depois da triagem, cada ativo recebe um escore comparável dentro do universo disponível naquele janeiro. A estratégia publicada faz um corte nos melhores emissores, mantém apenas uma classe por emissor e distribui o orçamento de renda variável proporcionalmente ao escore, sujeito ao número de posições e aos limites da configuração. O saldo fica no CDI. No período aqui avaliado, a configuração completa, formada pela família de fatores, pelo número de posições e pelo orçamento de ações, era escolhida ano a ano pela seleção aninhada da Seção 4.1. Desde 25 de agosto de 2026 ela é declarada e congelada por perfil de investidor, conforme a Seção 3.4.

Essa separação também organiza os nomes. Benevente designa o produto; o módulo de seleção anual e a camada de proteção intranual, registrados como Benevente 1 e Benevente 2, são os mecanismos que a política declara por perfil (Seção 3.4); Benevente Quant AI designa a pesquisa, inclusive o experimento que combina um modelo de linguagem com um otimizador convexo. A carteira histórica publicada vem da regra multifatorial determinística. O modelo de linguagem não seleciona ativos nem define pesos: transforma fatos aprovados em tese, riscos e perguntas para revisão humana.

Sem expor o código da aplicação, a lógica é verificável: o sistema elimina ativos sem dados, liquidez ou lucro compatíveis, testa quatro leituras pré-declaradas e, na versão multifatorial, combina 40% de qualidade, 40% de lucro em relação ao preço e 20% de momento em doze meses. As 36 políticas candidatas cruzam orçamentos de ações de 55%, 75% e 95%, cestas de 5, 8 ou 12 emissores e quatro sinais; somente anos encerrados ordenam as alternativas de cada janeiro. Pesos, limites, transformações e arquivos recebem SHA-256.

### 3.4 A política vigente: três perfis declarados

Desde agosto de 2026 o sistema opera sob uma política declarada. Em lugar de buscar a melhor configuração a cada ano, ela fixa três, uma por perfil, congeladas antes da avaliação prospectiva: o conservador aloca 35% do patrimônio em renda variável entre doze emissores; o equilibrado, 55% entre oito; o arrojado, 75% entre cinco. Em todos, um quinto do orçamento de renda variável fica num fundo negociado na B3 que replica o S&P 500 em reais (IVVB11), definido pela política e não pelo escore, e o saldo permanece em caixa. A camada de proteção intranual atua apenas sobre a parcela doméstica, porque o sinal de estresse é calculado sobre o Ibovespa. O registro traz os hashes dos insumos, o assinante, o critério de falseamento e o início da amostra confirmatória, e nenhum parâmetro muda depois do congelamento sem nova versão e nova contagem. As Seções 4.1.1 e 4.1.2 documentam as duas revisões; a 5.1 traz o diagnóstico.

### 3.5 Por que a decisão é anual

A cadência anual é coerente com o sinal e foi testada: fundamentos saem em ciclos contábeis e a tese precisa de tempo para aparecer no preço; a troca mensal vende a empresa antes do reconhecimento e multiplica decisões a justificar. A revisão em janeiro cria uma fronteira simples: o publicado até a data entra, o resto é do próximo ciclo.

Cadência anual não significa ignorar o risco por doze meses: preço, concentração, liquidez e eventos seguem monitorados, e uma política institucional pode prever gatilhos extraordinários. Significa que a reseleção sistemática ocorre uma vez ao ano. Mantidas regra e dados, a cadência anual superou a trimestral e a mensal antes dos custos; onze anos pareados não provam otimalidade, apenas ausência de evidência para trocar a regra mais simples. Notícias não entram no retorno histórico: um radar de acompanhamento lê fontes públicas e classifica alertas para revisão humana, sem alterar ativos ou pesos, porque avaliá-las exigiria um braço prospectivo com horário de publicação e decisões arquivadas antes do desfecho.

### 3.6 Custos, imposto e execução

Duas parcelas de custo são deduzidas do retorno bruto.

- Taxas da B3 e corretagem por ordem.
- Deslizamento por participação no volume, proporcional ao tamanho da ordem em relação ao volume médio diário do papel, de modo que uma ordem grande em papel ilíquido recebe custo maior.

O imposto de renda é modelado à parte e **não** é deduzido: toda taxa anualizada neste artigo é bruta de imposto. O modelo aplica 15% sobre ganho realizado em renda variável e 17,5% sobre renda fixa de 361 a 720 dias, no ano da revisão que realiza o ganho, com liquidação integral no último ano — hipótese terminal conservadora, não diferimento indefinido.

O sistema recusa, por regra, ordens que ultrapassem 5% do volume médio diário do papel; a ordem não é enviada.

### 3.7 Governança: o sistema propõe, a pessoa decide

Quatro mecanismos delimitam o que o software pode fazer. Eles transformam a prestação de contas algorítmica em propriedade do desenho, e não em explicação produzida depois do fato (Kroll et al., 2017). A aprovação humana e o enquadramento ao perfil também são coerentes com a Resolução CVM nº 30, enquanto qualquer uso como consultoria individualizada depende da estrutura autorizada prevista na Resolução CVM nº 19 (Comissão de Valores Mobiliários, 2021a, 2021b).

1. Aprovação humana obrigatória: nenhuma ordem é transmitida, porque a arquitetura não possui esse caminho.
2. Papel delimitado do modelo de linguagem: o modelo organiza tese e riscos a partir de fatos já aprovados, sem definir peso, alterar limite ou aprovar ativo. Trata-se de restrição de arquitetura verificável, e a Seção 5.6 apresenta o experimento que testou o relaxamento dessa restrição.
3. Conciliação pós-operação: a nota de corretagem é confrontada linha a linha com a ordem proposta.
4. Limites explícitos e versionados: teto de renda variável, teto por emissor e reserva em caixa ficam na política, registrados antes da seleção.

---

## 4. Método de avaliação

### 4.1 Sequência histórica de desenvolvimento

O artefato admite múltiplas políticas, combinando orçamento de renda variável, número de posições e família de fatores. Publicar a melhor delas medida sobre toda a amostra seria exatamente o erro que a Seção 2 descreve. Na sequência histórica, para decidir a política do ano *t*, o sistema ordena as 36 candidatas usando somente os anos encerrados antes de *t*, pelo índice de Sharpe do excesso sobre o CDI, e adota a primeira colocada. Trocar de política é tratado como operação real e cobra rebalanceamento integral.

O ranqueamento exige no mínimo três anos encerrados. Como o painel começa em 2012, os anos de 2012 a 2014 inicializam a escolha e 2015 a 2025 formam onze decisões anuais. A ordem temporal reduz o uso direto do retorno futuro em cada decisão, mas não cria uma amostra verdadeiramente externa: os dados, filtros e hipóteses foram examinados durante o desenvolvimento do projeto. Por isso, esta janela é chamada de diagnóstico retrospectivo sequencial, e não de teste fora da amostra. O teste prospectivo começa apenas depois do congelamento descrito na Seção 4.5.

#### 4.1.1 O experimento que motivou a política declarada

Em 25 de agosto de 2026, a defesa da Seção 4.1 foi submetida a um teste direto. Com insumos, código e janela idênticos — condição verificada pela reprodução das 36 configurações compartilhadas com diferença máxima de 5,6×10⁻¹⁷ —, a mesma seleção aninhada sobre 256 candidatos rendeu 12,68% ao ano contra 15,31% da grade de 36, uma perda de 2,63 pontos. O Sharpe deflacionado caiu de 0,957 para 0,777, abaixo da significância, porque o máximo esperado sob a hipótese nula subiu de 0,375 para 0,746 com o número de tentativas. Em 2018 o seletor ampliado dedicou o ano a uma configuração que rendeu −7,2% enquanto o CDI rendeu 6,4%. A seleção aninhada tem, portanto, um limite de capacidade: dez observações anuais não ordenam 256 candidatos, e ultrapassar o limite degrada a proteção do procedimento sem sinal visível de alerta.

A consequência de projeto foi a política declarada da Seção 3.4, congelada com assinante identificado, critério de falseamento e amostra confirmatória a partir de 2027. O experimento completo, com os controles e os negativos auxiliares, está em manuscrito próprio (declared_over_searched_2026), e cada número publicado é conferido por rotina automática contra os artefatos versionados. A mesma auditoria corrigiu a referência do Ibovespa, que passou a ser lida da série datada de origem — 11,74% ao ano e queda de 46,8% —, depois de constatada deriva na curva rebaseada do motor.

#### 4.1.2 Resultado posterior: o caixa deixa de ser um índice (26/08/2026)

A política da Seção 4.1.1 declarava como caixa 100% do CDI capitalizado diariamente — um índice, não um instrumento: sem custódia, sem spread e sem rolagem. Registrada no dia seguinte (SHA-256 iniciado em ca2476d4), a versão 3 troca apenas esse componente por Tesouro Selic, reconstruído do arquivo diário do Tesouro Transparente e líquido da custódia da B3 na tabela histórica e do spread cobrado em cada rolagem. Nada mais muda, o que permite atribuir o efeito inteiro ao instrumento. O caixa rende 9,36% ao ano contra 9,68% do índice, e o retorno de cada perfil cai entre 0,07 e 0,17 ponto: conservador 12,34%, equilibrado 15,39% e arrojado 19,79%, com quedas máximas de −9,17%, −17,88% e −28,95%. O excesso sobre o caixa, porém, sobe entre 0,08 e 0,18 ponto, porque o comparador é integralmente caixa e a carteira não é. A troca revelou ainda que a coluna de caixa do painel anterior é constante até 2012: a escada avalia de 2015 e não era afetada, mas a seleção aninhada ordenava com o caixa rendendo zero naquele ano, penalizando as alternativas defensivas. Como as duas pontas do experimento da Seção 4.1.1 usaram o mesmo insumo, a comparação entre elas permanece válida; o que não se pode afirmar é que a ordenação teria sido idêntica com o caixa correto.

### 4.2 Comparadores

Três referências foram calculadas de forma independente.

- CDI, série 12 do Banco Central, como custo de oportunidade do caixa.
- Ibovespa, índice de retorno total que incorpora os proventos da carteira teórica e, por isso, é comparável a uma carteira que os reinveste (B3, 2026c).
- Otimização média-variância sobre o mesmo universo elegível. Esse método estima retorno médio e covariância com dados anteriores e escolhe pesos que maximizam a relação entre retorno esperado e risco sob os mesmos limites de elegibilidade.

O último comparador merece nota: em uma versão anterior, a série rotulada como MVO era numericamente idêntica à estratégia, ou seja, a estratégia estava sendo comparada a si mesma. O defeito foi encontrado na auditoria interna e corrigido com uma implementação independente, que passou a produzir resultados distintos, inclusive desfavoráveis à estratégia em um dos onze anos. Todos os comparadores usam as mesmas datas de início e fim da carteira.

### 4.3 Correção por múltiplas tentativas

Com 36 configurações avaliadas, o Sharpe da vencedora precisa ser deflacionado. Calculamos o Sharpe deflacionado com o número de tentativas, o número de observações e os momentos superiores da série de retornos.

Medimos também o prêmio de retrospectiva: a diferença entre o retorno anualizado da configuração que teria vencido a amostra inteira, escolha impossível na prática, e o da escolha aninhada. Esse número quantifica o que se ganharia publicando o vencedor da busca como se fosse resultado obtenível.

### 4.4 Auditoria da qualidade dos dados e sensibilidade

A reconstrução de retorno total combina 497 séries; em 139 delas a distribuição de proventos precisou ser imputada por falta de cobertura do provedor. Como uma série problemática pode nunca entrar na carteira, a auditoria cruzou, por ano, a política escolhida, os pesos e o tipo de reconstrução de cada série, e mede a parcela da exposição acumulada a ações que dependeu de provento imputado. Dois testes de sensibilidade complementam a inspeção: a reamostragem conjunta dos vetores anuais de estratégia e comparadores, com 100 mil amostras e semente registrada, que mede estabilidade interna sem criar crises novas; e perdas hipotéticas de 10, 25, 50 e 100 pontos percentuais aplicadas somente à parcela investida em séries imputadas, que mostram quanto o resultado depende dessa hipótese.

### 4.5 Registro prospectivo

A linhagem tem quatro registros: o módulo de seleção anual, em 16 de agosto de 2026; a camada de proteção e o protocolo de acompanhamento, depois das respectivas mudanças; a política por perfil, em 25 de agosto; e a revisão do instrumento de caixa, em 26 de agosto, que é a que governa decisões futuras. Extensões não herdam a data dos registros anteriores. Para sustentar uma conclusão prospectiva, cada perfil precisa superar o próprio caixa declarado e o Ibovespa após custos e tributos, respeitar o critério de falseamento do registro e acumular ao menos três decisões anuais completas posteriores ao congelamento; a amostra confirmatória começa no primeiro pregão de 2027. Nenhuma observação prospectiva havia sido consumida quando a versão 3 substituiu a 2, e por isso a contagem não recomeçou — se já tivesse sido, teria recomeçado. Não existe resultado prospectivo na data deste artigo: a carteira de janeiro de 2026 antecede os registros e é carteira-sombra.

---

## 5. Resultados e discussão

### 5.1 Funcionamento e diagnóstico financeiro

Cada decisão anual foi emitida com fontes, hashes, elegibilidade, ranking, pesos, custos, comparadores e justificativa, e os testes de integridade recusaram arquivo alterado, peso que não soma 100%, ordem acima do limite de liquidez e fundamento recebido após a data da decisão. A auditoria da Seção 5.7 encontrou sete defeitos no próprio processo, e as correções alteraram as métricas publicadas.

A Tabela 2 traz o diagnóstico retrospectivo da política vigente sobre 2015–2025, com custos modelados e a camada aplicada à parcela doméstica. Os valores descrevem a amostra de desenvolvimento e não constituem validação prospectiva.

| Perfil | Renda variável | Emissores | Retorno anualizado | Volatilidade | Queda máxima | Anos acima do CDI |
|---|---:|---:|---:|---:|---:|:---:|
| Conservador | 35% | 12 | 12,51% | 5,84% | −9,16% | 8 de 11 |
| Equilibrado | 55% | 8 | 15,51% | 10,51% | −17,86% | 8 de 11 |
| Arrojado | 75% | 5 | 19,87% | 16,94% | −28,94% | 8 de 11 |
| Ibovespa | — | — | 11,74% | 23,37% | −46,82% | — |
| CDI | — | — | 9,61% | 0,25% | — | — |

Os três perfis preservam a ordenação declarada de risco: retorno e queda máxima crescem juntos do conservador ao arrojado, e nenhum perfil se aproximou da queda máxima do Ibovespa.

As análises das Seções 5.2 a 5.4 — imputação, reamostragem pareada e correção por múltiplas tentativas — foram conduzidas sobre a série de desenvolvimento do módulo de seleção, que tem o histórico de auditoria mais longo. A Tabela 3 traz essa série e seus comparadores, líquidos de custos estimados.

| Série | Retorno anualizado | Valor final de R$ 100 mil | Anos vencidos | Queda máxima diária |
|---|---:|---:|:---:|---:|
| Seleção anual (Benevente 1) | 17,86% | R$ 609.832 | | −47,8% |
| Com proteção (Benevente 2), antes do IR incremental | 18,45% | R$ 643.774 | | −28,7% |
| Com proteção (Benevente 2), após estimativa do IR incremental¹ | 18,29% | R$ 634.531 | | −28,7% |
| Seleção anual (Benevente 1), após modelo anual de IR | 16,03% | R$ 513.052 | | |
| Ibovespa | 11,77% | R$ 340.068 | 7 de 11 | −47,0% |
| CDI | 9,61% | R$ 274.368 | 6 de 11 | 0% |
| MVO neutra, mesmo universo | 7,83% | R$ 229.255 | 10 de 11 | |

¹ Estimativa agregada para R$ 100 mil, com alíquota de 15%, isenção mensal quando as vendas não superam R$ 20 mil e compensação de perdas. Ela mede apenas o imposto adicional causado pelas reduções intranuais do Benevente 2; não substitui a apuração por lote nem a conciliação de notas de corretagem.

A coluna em reais traduz a taxa anualizada em escala econômica. Sob as hipóteses do diagnóstico, R$ 100 mil teriam terminado em R$ 609.832 na série do módulo de seleção, R$ 643.774 com a camada de proteção antes do imposto incremental, R$ 340.068 no Ibovespa e R$ 274.368 no CDI. Esses valores dependem da qualidade da série reconstruída e devem ser lidos junto com a Seção 5.2.

Em janelas móveis, contra o CDI a série vence 8 de 9 janelas de três anos, 6 de 7 de cinco e 2 de 2 de dez; contra a otimização de referência, vence todas. As janelas se sobrepõem, então descrevem a amostra sem aumentar seu tamanho.

O retorno da série de desenvolvimento veio com risco elevado: a queda máxima diária chegou a 47,8%, próxima aos 47,0% do Ibovespa, porque entre 2018 e 2021 a política então selecionada manteve 95% em ações concentradas em cinco ou seis emissores. A camada de proteção preservou os mesmos ativos e reduziu a exposição só depois de estresse observado, levando a queda a 28,7%, com a maior perda na Covid-19. É por isso que a política vigente limita o orçamento por perfil: a amostra não permite afirmar proteção futura, mas a ordenação de risco da Tabela 2 é propriedade de construção, não de ajuste.

### 5.2 Qualidade dos dados e dependência de imputação

O painel contém 139 séries com proventos imputados, mas a carteira não as utilizou de modo uniforme. Somando somente a parcela de ações escolhida em cada ano, 13,9% da exposição acumulada dependeu de imputação. O caso mais relevante ocorreu em 2020: AZUL4 e MRFG3 representaram 50% da carteira total. Em cinco dos onze anos houve alguma exposição; nos demais, nenhuma série escolhida dependia desse procedimento.

| Ano | Peso total em séries imputadas | Séries selecionadas |
|---|---:|---|
| 2015 | 11,0% | CIEL3 |
| 2016 | 24,0% | ENBR3 |
| 2020 | 50,0% | AZUL4 e MRFG3 |
| 2021 | 25,0% | MRFG3 |
| 2025 | 5,0% | STBP3 |

Aplicar uma perda adicional de 10 pontos percentuais apenas à parcela imputada reduz o retorno anualizado de 17,86% para 16,78%; com 25 pontos, para 15,11%; com 50, para 12,16%; com 100, para 5,41%. A carteira deixa de superar o Ibovespa quando a penalização chega a cerca de 53 pontos percentuais, e o CDI, perto de 70. O teste mostra margem econômica, mas não repara o dado: como metade da carteira de 2020 dependeu de séries imputadas, o retorno histórico permanece diagnóstico até a reconciliação em fonte primária.

### 5.3 Incerteza da amostra

A reamostragem pareada preserva, em cada sorteio, o mesmo ano da estratégia e dos comparadores. Em 100 mil amostras, a probabilidade interna de excesso positivo foi alta, mas o intervalo de 95% cruzou zero contra CDI e Ibovespa; somente a comparação com a implementação de MVO permaneceu positiva em todo o intervalo. A ordenação observada não dependeu de um único ano sorteado repetidamente, o que não equivale a superioridade na população.

| Comparador | Amostras com excesso positivo | Mediana do excesso anualizado | Intervalo de 95% |
|---|---:|---:|---:|
| CDI | 93,4% | +8,19 p.p. | −2,27 a +20,01 p.p. |
| MVO de referência | 100,0% | +10,06 p.p. | +4,73 a +15,29 p.p. |
| Ibovespa | 94,4% | +5,94 p.p. | −1,31 a +14,28 p.p. |

O limite do procedimento é importante: reamostrar onze anos não cria regimes que não estejam na série nem transforma desenvolvimento em validação externa. A informação obtida é a estabilidade interna suficiente para continuar o teste prospectivo, não a comprovação de superioridade.

### 5.4 Correção por múltiplas tentativas

| Estatística | Valor |
|---|---:|
| Sharpe observado do excesso sobre o CDI | 0,933 |
| Sharpe máximo esperado sob a hipótese nula, com 36 tentativas | 0,355 |
| Probabilidade do Sharpe deflacionado | 0,986 |
| Significante a 95% | sim |
| Prêmio de retrospectiva | 0,65 p.p. ao ano |

O prêmio de retrospectiva indica que escolher a política vencedora conhecendo toda a amostra teria rendido 0,65 ponto percentual a mais por ano do que a escolha sequencial; em uma versão anterior, com um ano a menos de histórico inicial, esse prêmio era de 4,98 pontos. O Sharpe deflacionado corrige múltiplas tentativas, mas não resolve a dependência de dados nem a ausência de teste prospectivo: é uma defesa contra uma forma específica de sobreajuste, não um certificado geral de validade.

### 5.5 O que não funcionou

Oito hipóteses foram testadas e nenhuma se sustentou de forma suficiente para substituir a política principal. Elas são publicadas porque um artefato que só reporta o que deu certo não é auditável.

Ampliar a busca de configurações. Conforme a Seção 4.1.1, passar de 36 para 256 candidatos custou 2,63 pontos ao ano e a significância. Foi a rejeição que reorganizou o protocolo.

Pesar pelo inverso da volatilidade. Contra o peso publicado, proporcional ao escore, o esquema perdeu em oito das oito configurações medidas, reduzindo a queda máxima em 0,95 ponto ao custo de 2,11 pontos de retorno ao ano, e piorou o pior ano justamente nas cestas largas em que deveria ajudar.

Meta de volatilidade em janeiro. O mecanismo cortou exposição em cinco de treze anos, sempre depois de um estresse visível e nunca antes de um. Em 2020, janeiro estava calmo, o ano operou com exposição integral e a queda máxima não se alterou; em 2016, a exposição foi reduzida a 8,8% de ações em um ano em que a estratégia rendeu 35%.

Previsão anual de regime. Cinco indicadores disponíveis em janeiro (prêmio de lucro sobre o CDI, nível do CDI, retorno e volatilidade de doze meses e distância do topo) tentaram antecipar se o ano favoreceria ações ou caixa. O melhor deles acertou três de quatro chamadas (p = 0,31), resultado indistinguível do acaso; o prêmio potencial de 6,5 pontos percentuais ao ano não foi capturado por nenhum indicador.

Realocação mensal e semanal. Em 118 períodos mensais e 521 semanais, nenhuma das sete regras contínuas superou de forma significativa o peso estático, e a regra de média-variância foi significativamente pior. O prêmio por acertar o momento existe, mas nenhum sinal testado o capturou.

Reseleção mais frequente da cesta. Questão distinta da anterior: não a proporção entre ações e caixa, mas se a própria cesta deveria ser retriada mais vezes por ano. Três cadências foram comparadas com a mesma regra, os mesmos limites e o mesmo painel; apenas as datas de decisão variam.

| Cadência | Decisões | CAGR bruto | Líquido de custo | Após IR | Giro no ano |
|---|---:|---:|---:|---:|---:|
| Anual | 11 | 18,58% | 18,51% | 17,09% | 62,1% |
| Trimestral | 44 | 16,37% | 16,25% | 15,60% | 116,0% |
| Mensal | 132 | 13,92% | 13,75% | 13,32% | 177,6% |

Nenhuma cadência mais rápida superou a anual: pareada por ano-calendário e após imposto, a trimestral ficou 1,55 ponto percentual abaixo (p = 0,376) e a mensal, 3,27 (p = 0,306). A leitura correta é ausência de evidência a favor, e não prova de prejuízo. A diferença nasce antes dos custos, pois o retorno bruto cai 4,66 pontos da cadência anual para a mensal, o que indica que o sinal amadurece lentamente. O modelo tributário chega a favorecer o braço mensal, que ainda assim não venceu.

Modelo de linguagem como fonte de retorno. Este é o teste que mais interessa à governança do produto, e está detalhado a seguir.

Proteção intranual concebida depois da Covid-19. A camada de proteção reduz a exposição após estresse de queda e volatilidade do Ibovespa. No histórico da série de desenvolvimento, a queda máxima recuou de 47,8% para 28,7%. A configuração escolhida somente com 2015–2018 também elevou o retorno anualizado de 17,86% para 18,45%, mas a diferença anual de retorno em 2019–2025 não foi detectável (p = 0,964). Para R$ 100 mil, a estimativa agregada do imposto incremental das reduções foi de R$ 2.195, levando o valor terminal estimado de R$ 643.774 para R$ 634.531, antes da tributação já pertencente à revisão anual. A camada integra a política declarada da Seção 3.4; sua evidência histórica permanece retrospectiva.

### 5.6 O experimento com modelo de linguagem: três resultados nulos

O produto restringe o modelo de linguagem à explicação. Um experimento retrospectivo separado permitiu que ele produzisse escore ou pesos apenas para medir o custo dessa restrição. Como o treinamento do modelo pode conter notícias e desfechos posteriores, os quatro braços são diagnóstico de sensibilidade, não validação temporal da LLM.

Uma extensão prospectiva medirá fidelidade, completude, cobertura de riscos e números inventados da camada de linguagem. Ela não seleciona ativos nem herda resultados anteriores.

- Nomeado: o modelo vê os nomes das empresas e devolve um escore limitado, que inclina o retorno esperado dentro do otimizador convexo.
- Anonimizado: idêntico, mas com as empresas identificadas por números, de modo que o modelo vê fundamentos e não marcas.
- Determinístico: controle sem modelo, ordenando o mesmo universo pelo escore de fator pré-declarado.
- Monolítico: o contrafactual em que o modelo devolve pesos diretamente, sem otimizador nem restrições.

| Comparação | Diferença anualizada | p |
|---|---:|---:|
| Nomeado menos anonimizado (contaminação temporal) | +0,38 p.p. | 0,905 |
| Anonimizado menos determinístico (valor agregado pelo modelo) | −0,05 p.p. | 0,989 |
| Anonimizado menos monolítico (valor do desacoplamento) | +0,81 p.p. | 0,777 |

Os três resultados não permitem rejeitar a hipótese de ausência de diferença, e cada um responde a uma pergunta distinta.

1. Não houve diferença detectável entre identificar as empresas pelo nome e ocultar sua identidade, o que não prova ausência de contaminação: o modelo pode inferir a empresa pelos fundamentos ou reconhecer padrões aprendidos depois do período.
2. O modelo não agregou retorno: o braço anonimizado ficou 0,05 ponto percentual abaixo do controle determinístico, com p = 0,989.
3. Manter o modelo longe dos pesos não penalizou o resultado. Quando recebeu essa função, ele produziu vetores que não somavam 100% em cinco dos treze anos e omitiu dezenas de ativos elegíveis sem sinalizar.

A conclusão de produto: o modelo organiza e explica decisões, mas não as gera. Qualquer uso futuro em sinal, ranking ou peso terá de começar depois do registro específico da versão avaliada e ser comparado prospectivamente ao controle determinístico.

### 5.7 Defeitos encontrados na própria auditoria

A auditoria interna adversarial encontrou e corrigiu sete defeitos, todos na direção de inflar o resultado.

| Defeito | Efeito | Correção |
|---|---|---|
| Comparador MVO idêntico à estratégia | Comparação da estratégia consigo mesma | Implementação independente |
| Painel de provedor descartava deslistadas | Viés de sobrevivência | Universo reconstruído do arquivo da B3 |
| Ano de deslistagem descartado inteiro | Perda truncava o ano | Liquidação da posição em CDI |
| Imposto ausente | Retorno superestimado | Modelo tributário brasileiro |
| Custo fixo ignorando liquidez | Ordem grande sem penalidade | Deslizamento por participação no volume |
| Rebalanceamento diário implícito | Artefato de vetorização | Trajetória de compra e manutenção |
| Filtro de sessões usando pico global | Anos legítimos descartados | Pico móvel local |

Depois da última correção, o retorno anualizado publicado caiu e a queda máxima subiu de 30,4% para 47,8%. A mudança evidencia o funcionamento do controle, que foi capaz de piorar o resultado quando os dados o exigiram, mas não prova que todos os defeitos foram encontrados.

---

## 6. Aplicabilidade, implantação e modelo de uso

### 6.1 Público e proposta de valor

O produto foi concebido para escritórios de investimento, consultorias, gestores patrimoniais e escritórios multifamiliares. A política aplicada, os dados e seus hashes, a elegibilidade, os pesos, as ordens, o custo estimado e a aprovação permanecem ligados à mesma decisão, o que reduz o tempo de reconstrução e permite responder por que um papel entrou e por que outro ficou de fora. O valor a testar está na consistência do processo e na capacidade de revisão, não em promessa de superar o mercado.

### 6.2 Fluxo operacional

O uso começa pelo perfil declarado adequado ao cliente. O usuário vê quais arquivos e demonstrações estavam disponíveis e quais passaram na validação; a triagem mostra aprovados e reprovados com o respectivo motivo; a carteira candidata apresenta pesos, parcela defensiva, custo e comparação com CDI, Ibovespa e MVO. O profissional revisa a tese, registra riscos, aprova ou rejeita a proposta e informa a justificativa, e o dossiê final reúne esse percurso com a versão da regra.

### 6.3 Implantação e piloto comercial

A implantação começa pela definição de fontes, políticas, acessos e aprovadores. No piloto o sistema acompanha poucas carteiras sem enviar ordens, e os dossiês são confrontados com o processo vigente; a conciliação de custos e posições fecha o ciclo entre proposta e execução. O piloto medirá tempo, completude da evidência, revisões, divergência de custos e disposição a pagar. O produto permanece em protótipo reprodutível: a janela descreve a amostra, e a avaliação prospectiva começa nos registros congelados, com hashes versionados e data carimbada por terceiro.

### 6.4 Matriz de evidências

A Tabela 10 delimita o que pode ser afirmado na submissão.

| Afirmação | Evidência disponível | Situação |
|---|---|---|
| O artefato preserva dados, regra, pesos e aprovação | Testes funcionais, hashes e dossiês reproduzíveis | Demonstrada no protótipo |
| A auditoria encontra erros que alteram métricas | Sete defeitos reproduzidos e corrigidos | Demonstrada no desenvolvimento |
| A regra superou comparadores entre 2015 e 2025 | Diagnóstico sequencial e reamostragem interna | Observada, não prospectiva |
| A série histórica tem qualidade institucional | 13,9% da exposição a ações dependeu de imputação | Não demonstrada |
| O modelo de linguagem gera retorno adicional | Diferença de −0,05 p.p. e p = 0,989 | Não demonstrada |
| Há demanda e disposição a pagar | Piloto ainda não executado | Não demonstrada |
| A regra funciona em dados futuros | Registros congelados de 2026; amostra confirmatória a partir de 2027 | Em acompanhamento |

A matriz converge com a literatura: ausência de alfa do modelo (Perlin et al., 2025; Li et al., 2026), valor narrativo sem autorização de pesos (Kim et al., 2024) e exigência prospectiva (Pelster & Val, 2024).

---

## 7. Limitações e recomendações

### 7.1 Limitações

A primeira limitação é temporal: onze decisões anuais são poucas, e a janela também serviu ao desenvolvimento. O prêmio de retrospectiva e o Sharpe deflacionado tratam parte do risco de múltiplas tentativas, mas não equivalem a validação prospectiva.

A segunda limitação está nos dados. A página atual da B3 respondeu para 95,6% das séries consultadas, percentual que mede resposta do serviço, não completude histórica; a reconstrução das posições mantidas encontrou sete diferenças materiais em 54 comparações e duas observações sem resposta. Papéis sem cobertura completa recebem, em casos identificados, distribuição imputada pela mediana transversal do ano, fragilidade que atingiu 13,9% da exposição acumulada a ações e 50% da carteira de 2020. O arquivo novo melhora a auditabilidade porque permite reprovar a própria reconciliação; não transforma a curva em evidência institucional.

A terceira é econômica. Na série de desenvolvimento, a queda máxima diária chegou a 47,8%, ligeiramente pior que os 47,0% do Ibovespa; a camada de proteção reduziu essa marca retrospectiva para 28,7%, mas foi concebida depois da Covid-19 e ainda não demonstrou benefício prospectivo; o imposto de renda variável é apurado por ativo e custo médio; resta conciliar com notas de corretagem. A política vigente limita a exposição por perfil, com quedas máximas retrospectivas entre 9,2% e 28,9%, mas seus parâmetros também foram definidos com conhecimento da amostra e só a janela confirmatória poderá qualificá-los.

Por fim, o produto não elimina responsabilidade profissional: uso comercial exige enquadramento regulatório, suitability, segurança, contrato de fontes e aprovação humana. O modelo de linguagem não seleciona ativos nem define pesos, e o radar de notícias serve apenas ao alerta humano, sem participar do retorno histórico.

### 7.2 Recomendações de pesquisa e implantação

O passo científico prioritário é acumular decisões posteriores aos registros congelados. Em paralelo, uma versão institucional precisará de um livro histórico de eventos capaz de cobrir os 22 códigos não devolvidos e de reproduzir as sete diferenças materiais encontradas no escopo da estratégia. Testes seguintes devem acrescentar trajetórias sintéticas com regimes de baixa prolongada, sem substituir a observação futura; um estudo com notícias deve ser registrado como braço separado, com horário verificável. O passo de produto é um piloto silencioso, sem execução automática, que meça tempo, completude documental, divergência de custos, compreensão do usuário e disposição a pagar.

---

## 8. Conclusão

O Benevente foi construído para resolver uma falha operacional específica: carteiras são propostas em um momento e justificadas em outro, enquanto os dados, a regra e a aprovação podem se separar. O protótipo mostrou que é possível produzir a alocação e a evidência da decisão no mesmo fluxo, com fundamentos admitidos pela data de recebimento, regra quantitativa separada da explicação em linguagem natural, custos, imposto e comparadores independentes.

No diagnóstico 2015–2025, os três perfis superaram o caixa em oito de onze anos cada um, com quedas escalonadas conforme o perfil; a incerteza amostral e a imputação parcial impedem tratar isso como superioridade comprovada. Os negativos são parte da contribuição: reselecionar mais vezes não ajudou, o modelo de linguagem não acrescentou retorno, a alocação direta por texto saiu aritmeticamente inconsistente em parte dos anos e a própria busca se degradou ao ser ampliada. O conjunto justifica um sistema em que a regra calcula, a linguagem explica e uma pessoa responde.

A conclusão sustentada pela evidência é estreita. O artefato cria uma cadeia auditável e a usa para achar erros que alteram o próprio resultado — inclusive recusando um selo que os dados não sustentavam e trocando um caixa que não era comprável — e para medir o limite do próprio procedimento de seleção. A viabilidade comercial depende de um piloto que meça ganho de tempo, completude documental, compreensão e disposição a pagar. A validade financeira exigirá uma base histórica reconciliável e observações posteriores aos registros congelados; a amostra confirmatória da política vigente começa no primeiro pregão de 2027. Até lá, o desempenho histórico permanece diagnóstico de desenvolvimento.

---

## 9. Disponibilidade

Código, testes, manifestos e arquivos de evidência estão em https://github.com/diegogallina1/benevente, com fontes, limitações e comandos de reprodução documentados. A demonstração está em https://benevente-wealth-system.vercel.app/.

---

## Referências

Bailey, D. H., Borwein, J. M., López de Prado, M., & Zhu, Q. J. (2017). The probability of backtest overfitting. *Journal of Computational Finance, 20*(4), 39–69. https://doi.org/10.21314/JCF.2016.322

Bailey, D. H., & López de Prado, M. (2014). The deflated Sharpe ratio: Correcting for selection bias, backtest overfitting, and non-normality. *Journal of Portfolio Management, 40*(5), 94–107. https://doi.org/10.3905/jpm.2014.40.5.094

Banco Central do Brasil. (2026). *Sistema Gerenciador de Séries Temporais: série 12, taxa de juros CDI*. https://www3.bcb.gov.br/sgspub/

B3 S.A. – Brasil, Bolsa, Balcão. (2026a). *Cotações históricas: série histórica de preços dos títulos negociados na Bolsa*. https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/mercado-a-vista/cotacoes-historicas/

B3 S.A. – Brasil, Bolsa, Balcão. (2026b). *Dividendos e outros eventos corporativos*. https://sistemaswebb3-listados.b3.com.br/dividensOtherCorpActPage/

B3 S.A. – Brasil, Bolsa, Balcão. (2026c). *Ibovespa B3*. https://www.b3.com.br/pt_br/market-data-e-indices/indices/indices-amplos/ibovespa.htm

Benevente. (2026). *Documentação técnica, repositório de dados e validação de horizontes*. https://github.com/diegogallina1/benevente

Black, F., & Litterman, R. (1992). Global portfolio optimization. *Financial Analysts Journal, 48*(5), 28–43. https://doi.org/10.2469/faj.v48.n5.28

Comissão de Valores Mobiliários. (2021a). *Resolução CVM nº 19, de 25 de fevereiro de 2021: atividade de consultoria de valores mobiliários* (texto consolidado). https://conteudo.cvm.gov.br/legislacao/resolucoes/resol019.html

Comissão de Valores Mobiliários. (2021b). *Resolução CVM nº 30, de 11 de maio de 2021: adequação dos produtos, serviços e operações ao perfil do cliente* (texto consolidado). https://conteudo.cvm.gov.br/legislacao/resolucoes/resol030.html

Comissão de Valores Mobiliários. (2026a). *Demonstrações Financeiras Padronizadas (DFP): dados abertos*. https://dados.cvm.gov.br/dataset/cia_aberta-doc-dfp

Comissão de Valores Mobiliários. (2026b). *Formulário de Informações Trimestrais (ITR): dados abertos*. https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/ITR/DADOS/

DeMiguel, V., Garlappi, L., & Uppal, R. (2009). Optimal versus naive diversification: How inefficient is the 1/N portfolio strategy? *Review of Financial Studies, 22*(5), 1915–1953. https://doi.org/10.1093/rfs/hhm075

Fama, E. F., & French, K. R. (2015). A five-factor asset pricing model. *Journal of Financial Economics, 116*(1), 1–22. https://doi.org/10.1016/j.jfineco.2014.10.010


Hevner, A. R., March, S. T., Park, J., & Ram, S. (2004). Design science in information systems research. *MIS Quarterly, 28*(1), 75–105. https://doi.org/10.2307/25148625

Kim, A. G. H., Muhn, M., & Nikolaev, V. V. (2024). *Financial statement analysis with large language models* [Working paper]. arXiv. https://arxiv.org/abs/2407.17866

Kroll, J. A., Huey, J., Barocas, S., Felten, E. W., Reidenberg, J. R., Robinson, D. G., & Yu, H. (2017). Accountable algorithms. *University of Pennsylvania Law Review, 165*(3), 633–705.

Li, Y., Kim, K., Cucuringu, M., & Ma, S. (2026). Can LLM-based financial investing strategies outperform the market in long run? In *Proceedings of the 32nd ACM SIGKDD Conference on Knowledge Discovery and Data Mining* (pp. 2711–2722). https://doi.org/10.1145/3770854.3785702

López de Prado, M. (2018). *Advances in financial machine learning*. Wiley.

Markowitz, H. (1952). Portfolio selection. *Journal of Finance, 7*(1), 77–91. https://doi.org/10.2307/2975974

Novy-Marx, R. (2013). The other side of value: The gross profitability premium. *Journal of Financial Economics, 108*(1), 1–28. https://doi.org/10.1016/j.jfineco.2013.01.003

Novy-Marx, R., & Velikov, M. (2016). A taxonomy of anomalies and their trading costs. *Review of Financial Studies, 29*(1), 104–147. https://doi.org/10.1093/rfs/hhv063

Peffers, K., Tuunanen, T., Rothenberger, M. A., & Chatterjee, S. (2007). A design science research methodology for information systems research. *Journal of Management Information Systems, 24*(3), 45–77. https://doi.org/10.2753/MIS0742-1222240302

Pelster, M., & Val, J. (2024). Can ChatGPT assist in picking stocks? *Finance Research Letters, 59*, 104786. https://doi.org/10.1016/j.frl.2023.104786

Perlin, M. S., Foguesatto, C. R., Müller, F. M., & Righi, M. B. (2025). Can AI beat a naive portfolio? An experiment with anonymized data. *Finance Research Letters*, 107126. https://doi.org/10.1016/j.frl.2025.107126

Yu, Y., Yao, H., Jiang, H., Lu, Y., Cao, Y., Yan, D., & Zhuang, F. (2024). FinCon: A synthesized LLM multi-agent system with conceptual verbal reinforcement for enhanced financial decision making. In *Advances in Neural Information Processing Systems 37*. https://doi.org/10.52202/079017-4354
