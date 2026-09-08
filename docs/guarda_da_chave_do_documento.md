# Guarda da chave que deriva o documento

Documento de engenharia. Ele descreve o que o código faz com
`BENEVENTE_DOCUMENTO_CHAVE` e o que a operação precisa decidir em volta dela.
Não decide controlador, base legal, prazo de retenção nem canal do titular:
essas quatro são do controlador, e a última seção diz onde elas encostam aqui.

## O que a chave é

`b3_connection.Consentimento.pseudonimiza` deriva o CPF ou CNPJ do titular com
HMAC-SHA256 antes de o número tocar qualquer registro nosso. A chave desse HMAC
é a variável de ambiente `BENEVENTE_DOCUMENTO_CHAVE`, de no mínimo 32 bytes. O
registro guarda o resultado em `documento_hash` e declara a derivação em
`documento_derivado_com`.

A versão anterior aplicava SHA-256 direto no número e chamava aquilo de
anonimização. Não era: existem cerca de 10⁹ CPFs válidos, e enumerar esse espaço
contra um hash é trabalho de minutos numa máquina comum.

## O que ela protege, e o que não

O HMAC fecha a enumeração para quem **não** tem a chave. Para quem tem, ela
continua aberta: com a chave, derivar os 10⁹ candidatos e procurar o pseudônimo
é o mesmo trabalho de antes.

Disso decorre a única frase que importa neste documento: **a chave é a
capacidade de reidentificação.** Ela não é parâmetro de configuração, é o
material que separa um registro pseudonimizado de uma lista de CPFs. Guardá-la
junto do registro que ela protege anula a proteção inteira, e é por isso que o
código recusa gravá-la em qualquer lugar por onde o registro passe.

O resultado é pseudônimo, não anônimo, e o registro diz isso de si mesmo em
`documento_derivado_com`. Quem ler o arquivo daqui a três anos não precisa
supor.

## Onde ela mora

Só no ambiente do processo que roda a conexão. Nunca no repositório, nunca no
registro, nunca em artefato, nunca em log.

Sem a variável, `chave_do_ambiente()` levanta `ChaveAusente` e o módulo para. A
recusa é deliberada: voltar em silêncio ao hash puro devolveria o problema com o
nome novo, que é a única saída pior do que tê-lo. Uma execução que falha por
falta de chave é um incidente de operação; uma que grava hash reversível chamado
de pseudônimo é um incidente de proteção de dados que ninguém percebe.

`research_b3_connection.py` é a exceção declarada: usa uma chave pública fixa,
escrita no próprio arquivo, sobre um CPF sintético, para o artefato de
demonstração seguir reproduzível. O JSON gerado diz isso em `consent_note`. Essa
chave não serve para mais nada e não deve ser copiada para lugar nenhum.

## Como gerar

Sorteada, nunca escolhida. O módulo checa comprimento e não tem como checar
entropia: trinta e dois caracteres de uma frase que uma pessoa inventou passam
na checagem e se enumeram como qualquer frase.

```powershell
# 32 bytes de aleatoriedade criptográfica, em hexadecimal (64 caracteres)
python -c "import secrets; print(secrets.token_hex(32))"
```

Guardar no cofre de segredos do ambiente que roda a conexão. Em máquina de
desenvolvimento, uma chave própria e diferente da de produção — chave
compartilhada entre ambientes faz um pseudônimo de teste bater com um de
produção, e nesse momento o ambiente de teste passa a conter dado pessoal.

## Quem acessa

A definir pelo controlador, e a lista deve ser curta e nominal. O que a
engenharia afirma é o teto: **quem tem a chave pode reidentificar todo titular
que já entrou no registro.** Acesso à chave e acesso à base de CPFs são o mesmo
acesso, e devem ser tratados com o mesmo critério.

## Rotação, e o que ela quebra

Rotacionar a chave troca **todos** os pseudônimos: o mesmo CPF passa a derivar
para outro valor. Isso tem duas consequências opostas, e as duas são reais.

A favor: pseudônimos de épocas diferentes deixam de ser ligáveis entre si, o que
limita o quanto a base acumula sobre um titular ao longo do tempo.

Contra: o registro encadeado perde a continuidade por titular. Depois da
rotação, não há como saber por comparação de pseudônimos que o consentimento de
2027 é do mesmo titular do de 2026.

Portanto rotação não é operação de higiene periódica a ser feita por hábito. É
evento datado, com decisão registrada, e três perguntas a responder antes:

1. **A continuidade por titular é necessária?** Se for, o registro precisa
   carregar a época da derivação junto do pseudônimo — hoje ele não carrega, e
   acrescentar isso muda o formato publicado e os hashes encadeados. É mudança a
   projetar, não a improvisar no dia da rotação.
2. **O que acontece com a chave antiga?** Destruí-la torna os pseudônimos
   anteriores permanentemente irreversíveis. Guardá-la preserva a reversão — e o
   risco — indefinidamente. Não há terceira opção: guardar "só por precaução" é
   escolher a segunda.
3. **Qual a data?** Ela entra no registro, porque a partir dela a leitura dos
   pseudônimos muda.

## Se a chave vazar

Todo pseudônimo já gravado volta a ser enumerável, inclusive os antigos: o
vazamento é retroativo por natureza. A resposta técnica é rotacionar e decidir o
destino dos registros escritos com a chave vazada. A resposta jurídica —
comunicação à ANPD e aos titulares — é do controlador, e depende de saber **o
que** vazou e **quando**, que é justamente o que a engenharia tem de conseguir
responder. Daí a chave precisar de origem única e acesso nominal: sem isso, a
pergunta "quem tinha essa chave em março" não tem resposta.

## Onde isto encosta nas definições em aberto

Duas das quatro decisões do controlador têm ligação direta com este documento.

**Retenção.** O prazo de guarda do registro determina por quanto tempo a chave
precisa sobreviver. E há um caminho que costuma passar despercebido: **destruir
a chave é uma forma de fazer o registro expirar.** Apagar uma chave é operação
única e verificável; apagar registros espalhados por backups, artefatos e cópias
não é. Se a política de retenção puder ser satisfeita tornando os pseudônimos
irreversíveis em vez de removendo linhas, ela fica muito mais barata de cumprir
e de provar. A decisão é do controlador; a possibilidade é técnica e existe.

**Base legal.** Consentimento (art. 7º, I) e execução de contrato (art. 7º, V)
levam a prazos e a direitos de revogação diferentes, e é o prazo que define por
quanto tempo a chave precisa existir. A ordem correta é decidir a base legal,
derivar dela a retenção, e só então fixar o ciclo de vida da chave — e não o
contrário.

As outras duas — controlador e canal do titular — não dependem deste documento.
O canal, em particular, tem solução técnica barata: um endereço publicado como
`mailto:`, sem formulário e sem coleta, atravessa o portão de segurança do site
como ele está hoje.
