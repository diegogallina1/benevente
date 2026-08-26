# Desenho do canal de WhatsApp

Documento de desenho. Nada aqui foi construído; o objetivo é decidir a forma
antes de escrever a primeira linha, porque as decisões erradas neste canal são
caras de desfazer e algumas são irreversíveis do ponto de vista regulatório.

## 1. A pergunta que define tudo o resto

**Quem está do outro lado?**

O sistema inteiro se apoia numa propriedade: ele é ferramenta de apoio à decisão
de profissional habilitado, não serviço de recomendação autônoma. Não transmite
ordens, não recomenda sozinho, e a responsabilidade permanece de quem assina.
Essa propriedade é o que mantém a atividade dentro do que o escritório já está
autorizado a fazer.

Um site não atravessa essa linha porque é publicação: quem chega, chega por
conta própria e lê o que está publicado. **Uma mensagem que chega no celular de
alguém, dirigida a ele, sobre a carteira dele, é outra coisa.** É comunicação
ativa e individualizada, e o enquadramento muda conforme o destinatário.

Portanto:

* **O canal fala com quem assina.** Assessor, consultor, gestor, membro de
  comitê. O conteúdo é o mesmo que o dossiê já entrega, no formato que cabe num
  celular.
* **O canal não fala com o investidor final.** Não porque seja tecnicamente
  difícil, mas porque isso seria outro produto, com outro enquadramento e outro
  parecer jurídico. Se um dia for o caminho, começa do zero nesta seção.

Essa fronteira não é uma preferência de desenho. É a mesma fronteira do resto do
projeto, aplicada a um meio novo.

## 2. O que o canal faz

Ele é um **canal de notificação e consulta sobre decisões que o sistema já
produziu**. Não é um assistente que responde perguntas sobre investimentos.

### 2.1 O que ele envia sozinho

Três eventos, e apenas três, porque são os únicos que exigem ação ou ciência de
quem assina:

| Evento | Quando | Frequência medida |
|---|---|---|
| **Mudança de estado da camada** | O sinal de estresse muda de normal para alerta, de alerta para severo, ou retoma | 3 a 4 por ano por perfil, medido em onze anos |
| **Decisão anual disponível** | Primeiro pregão de janeiro, quando a cesta nova sai | 1 por ano por perfil |
| **Item do radar que exige revisão** | O radar de eventos classifica algo como exigindo olho humano | poucos por mês, e o volume é configurável |

O volume total é baixo por construção — na ordem de **uma dúzia de mensagens por
ano por perfil acompanhado**. Isso não é acidente: um canal que manda mensagem
todo dia treina o destinatário a ignorá-lo, e o dia em que a mensagem importa é
justamente o dia em que ela some no meio das outras.

### 2.2 O que ele responde quando perguntado

Dentro da janela de conversa, um conjunto **fechado** de consultas:

* `carteira <perfil>` — o que o livro carrega hoje, com a exposição corrente
* `dossiê <perfil> <ano>` — o PDF da decisão
* `por que <ticker>` — o motivo declarado da entrada, com a data
* `estado` — em que estado a camada está e desde quando
* `limites` — o link para as limitações

Qualquer coisa fora dessa lista recebe uma resposta única: o canal explica o que
sabe responder e oferece o link. **Não há caminho em que ele improvise sobre um
ativo, um mercado ou uma decisão que não esteja num artefato publicado.**

### 2.3 O que ele nunca faz

* Não transmite ordem, não confirma execução, não integra com corretora.
* Não responde "devo comprar X?" nem nenhuma variação disso.
* Não personaliza recomendação por cliente final.
* Não inventa número. Todo valor que sai já está num arquivo com hash.

## 3. Onde o modelo de linguagem entra — e por que quase não entra

A plataforma do WhatsApp impõe uma restrição que, por sorte, é exatamente a
regra que este projeto já adotou: **mensagens enviadas fora de uma conversa
ativa precisam usar modelos de texto aprovados previamente pela Meta**, com
campos variáveis. Não é possível gerar texto livre num alerta.

Ou seja: o texto dos três alertas da Seção 2.1 é **congelado e aprovado antes**,
e o sistema só preenche as variáveis com valores que vêm de artefato hasheado.
O modelo de linguagem não participa disso. Não por escolha nossa — por desenho
da plataforma, que aqui coincide com o nosso.

Dentro da janela de conversa, texto livre é permitido. Ainda assim, as respostas
da Seção 2.2 são **templates locais preenchidos com dados**, não geração. O
modelo de linguagem tem, no máximo, um papel: transformar uma pergunta em
linguagem natural na consulta correspondente da lista fechada — classificação,
não redação. Se a classificação falhar, a resposta é a de fallback, nunca um
palpite.

Isso preserva a mesma fronteira do produto: a regra calcula, o texto explica
fatos já aprovados, e uma pessoa responde.

## 4. Arquitetura

O princípio é o mesmo do site: **o canal é leitor, nunca fonte de verdade.**

```
pipeline diário (23:10, dias úteis, já existe)
        │
        ├── live_performance_<perfil>.json   ← estado da camada, exposição, hash encadeado
        ├── live_profiles_2026.json          ← resumo por perfil
        └── event_radar.json                 ← itens que pedem revisão
                    │
                    ▼
            notificador (novo)
              compara o estado publicado com o último estado notificado
              decide se há evento; se não há, não manda nada
                    │
                    ▼
            fila de mensagens (arquivo versionado)
              cada item: destinatário, modelo, variáveis, artefato de origem + hash
                    │
                    ▼
            entregador (novo)
              envia pela API, registra id, status e horário
                    │
                    ▼
            web/message_log.json  ← encadeado por SHA-256, como o monitor já faz
```

Três decisões de arquitetura que valem justificativa:

1. **A fila é um arquivo antes de ser uma entrega.** Um evento vira item de fila,
   e o envio é um passo separado. Isso permite rodar o canal inteiro em modo seco
   por semanas, auditar o que ele teria mandado, e só então ligar a entrega.
2. **Todo item carrega o hash do artefato que o gerou.** Um alerta que não pode
   ser rastreado até o arquivo que o motivou é um alerta que ninguém consegue
   defender três anos depois — o mesmo problema que o produto existe para
   resolver.
3. **O log de mensagens é encadeado.** Mesma disciplina do acompanhamento diário:
   cada registro traz o hash do anterior, então apagar ou reescrever uma
   notificação passada quebra a cadeia de forma visível.

## 5. Identidade, consentimento e dados

* **Cadastro explícito.** Só recebe quem foi cadastrado como signatário, com
  nome, papel e vínculo com o escritório. Nada de lista importada.
* **Opt-in registrado com data.** A plataforma exige, a LGPD exige, e o registro
  do consentimento é dado como qualquer outro: datado e versionado.
* **Saída em uma palavra.** `sair` remove da lista e o canal confirma. Sem
  fricção, sem retenção.
* **Número de telefone é dado pessoal.** Fica fora do repositório público, fora
  de qualquer artefato publicado e fora dos logs de mensagem — o log referencia
  um identificador interno, não o número.

## 6. Custo

O modelo de cobrança da plataforma é por mensagem, por categoria. Os alertas da
Seção 2.1 são da categoria utilitária. Com o volume medido — cerca de uma dúzia
por ano por perfil —, o custo por escritório acompanhado é irrelevante frente a
qualquer outra linha do produto.

Duas observações que mudam a conta se ignoradas:

* Respostas dentro da janela de conversa passam a ser cobradas a partir de
  outubro de 2026, o que muda o cálculo de um canal conversacional. O nosso é de
  notificação com consulta ocasional, então o efeito é pequeno — mas isso é uma
  consequência do desenho da Seção 2, não uma sorte.
* Um canal que virasse "resumo semanal" multiplicaria o volume por vinte e
  entregaria menos: as três notificações existem porque **exigem ação**, e um
  resumo periódico não exige nada.

## 7. O que precisa de parecer jurídico antes de existir

Registrado aqui porque é mais barato perguntar antes:

1. **Um alerta de mudança de exposição enviado a um assessor constitui
   recomendação?** A leitura que sustenta o desenho é que não — é informe sobre
   o estado de uma regra que o próprio escritório contratou, endereçado a um
   profissional habilitado. Mas essa leitura precisa de confirmação, não de
   otimismo.
2. **Obrigações de registro e guarda.** A comunicação de assessores é matéria
   regulada, e o canal precisa nascer já compatível com o que a norma exige de
   retenção e recuperação.
3. **Conflito e transparência de remuneração.** Se o escritório remunerar por
   giro, um canal que avisa sobre mudanças de exposição precisa deixar claro que
   a cadência não é calibrada por receita — o mesmo cuidado que a página para
   escritórios já tem.

## 8. Como construir, em ordem

Cada fase precisa terminar antes da seguinte começar, e cada uma tem um critério
de saída que não é "funcionou na minha máquina".

**Fase 0 — modo seco, sem WhatsApp.** O notificador roda junto do pipeline
diário e escreve a fila num arquivo. Ninguém recebe nada. Critério de saída:
duas semanas de fila conferida à mão, com todo evento rastreável ao artefato que
o gerou, e nenhum evento espúrio.

**Fase 1 — um destinatário só, você.** Modelos aprovados, entrega ligada, um
número cadastrado. Critério de saída: um mês sem mensagem indevida, sem duplicata
e sem alerta perdido, com o log encadeado íntegro.

**Fase 2 — um escritório convidado.** O piloto silencioso ganha o canal.
Critério de saída: o escritório diz se as três notificações são as certas — e
provavelmente vai dizer que falta uma e sobra outra. É a informação que a Fase 2
existe para comprar.

**Fase 3 — decisão.** Abrir, ajustar ou desligar, com base no que a Fase 2
mediu. Não antes.

## 9. O que este desenho deliberadamente não resolve

* **Não integra com corretora.** Nenhuma fase acima transmite ordem, e a
  arquitetura não tem esse caminho — pela mesma razão que o resto do sistema não
  tem.
* **Não substitui o dossiê.** O canal aponta para ele. Um alerta de celular não
  é o documento que se leva a um comitê três anos depois.
* **Não atende o investidor final.** Está na Seção 1, e é a decisão mais
  importante deste documento.
