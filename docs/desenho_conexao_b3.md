# A conexão com a B3

Escrito depois de ler o Manual Técnico das APIs da Área do Investidor. A leitura
derrubou uma suposição que estava embutida em todo o resto do produto, e é por
isso que este documento começa pelo que não funciona.

---

## 1. A descoberta que muda o desenho

**A B3 não entrega preço médio.** Existem endpoints de Posição, Movimentação,
Negociação de Ativos, Eventos Provisionados, Garantias, Ofertas Públicas. Não
existe endpoint de custo de aquisição, e não é omissão da documentação — é que
esse dado não está na base: a B3 sabe o que o investidor tem, não por quanto
comprou de forma consolidada.

Isso importa porque o número mais valioso do mapa é o imposto. Ele é o que
transforma "trocar de carteira" numa decisão em vez de num clique, e ele depende
inteiramente do custo. O produto inteiro se apoia num dado que a conexão não
traz.

O custo pode ser **reconstruído** das negociações. A reconstrução tem três
buracos que engenharia nenhuma fecha:

| Buraco | Por quê | Quem é afetado |
| --- | --- | --- |
| A base começa em **01/11/2019** | É o que o manual declara | Quem investe há mais tempo — justamente quem tem mais ganho acumulado |
| Transferência entre custodiantes (STVM) | A posição chega, o histórico ficou na outra corretora | Quem já trocou de corretora |
| Renda fixa de balcão | Só quantidade, ISIN, data de aquisição e vencimento. Sem valor, sem custo | Quem tem CDB, LCI, LCA, CRI, CRA |

O caso comum não é excepcional: uma ação boa comprada em 2017 chega com posição
perfeita e custo nenhum.

## 2. A decisão de desenho

A saída fácil seria estimar o custo faltante e seguir. Ela foi recusada, e o
motivo é o mesmo que rege o resto do projeto: **um imposto estimado tem a mesma
aparência de um imposto medido, aparece na mesma linha da tela e leva à mesma
decisão de vender.** A diferença entre os dois é invisível para quem lê e
enorme para quem paga.

O que o sistema faz:

1. Cada posição carrega a **qualidade do seu custo** (`b3_connection.Qualidade`):
   reconstruído, declarado, parcial ou ausente. Só as duas primeiras sustentam
   apuração.
2. Uma posição sem custo defensável **não entra na soma do imposto** e aparece
   nomeada, com o valor que está sendo vendido sem apuração.
3. O total do plano é publicado como **piso, não como total**, e a tela escreve
   "a partir de R$ X" enquanto houver lacuna.
4. O ganho de uma posição de custo parcial **não é publicado**. `valor de
   mercado − custo conhecido` não é o ganho: é o ganho que existiria se o custo
   conhecido fosse o custo inteiro, e o erro é grande justamente onde mais
   engana.

O efeito na carteira de demonstração é instrutivo e desconfortável: com a WEGE3
sem custo apurável, o custo do plano cai de R$ 11.817 para R$ 567. Se o número
aparecesse sozinho, seria uma mentira confortável. Aparece com R$ 180.000
marcados como vendidos sem apuração ao lado.

## 3. O que a conexão entrega

**Entrega.** Renda variável depositada — ações, ETFs, BDRs, FIIs — com quantidade
e valor; Tesouro Direto; negociações desde 01/11/2019; eventos corporativos
provisionados; empréstimo de ativos e derivativos.

**Entrega pela metade.** Renda fixa de balcão, só com quantidade, ISIN, data de
aquisição e vencimento — e apenas o regime depositado mais o registrado com Selo
Certifica.

**Não entrega.** Preço médio; qualquer dado anterior a 01/11/2019; ativos fora
da B3 (fundos não registrados, previdência, cripto, conta no exterior); imóveis
e participações.

## 4. Consentimento

O consentimento é da B3, não nosso. O investidor autoriza vinculando a conta B3
à nossa aplicação e fazendo login com as credenciais **dela**, dentro do site
dela. A gestão fica em `investidor.b3.com.br`, em Minha Conta, Segurança,
Aplicativos e Sites, onde ele vê todos os licenciados autorizados e revoga
qualquer um sem passar por nós.

O que fica do nosso lado é o **registro de que houve consentimento**: hash do
CPF (nunca o número), licenciado, data, escopo, e o hash do registro anterior —
encadeado como o log do monitor diário. Credencial não é armazenada, e o
registro diz isso explicitamente num campo, porque a ausência de um campo não
prova nada.

## 4b. Como a conexão autentica, e por que ela ainda não liga

O endpoint de negócio exige **TLS mútuo 1.2** — o cliente apresenta um
certificado emitido pela B3 e valida o servidor contra a CA dela — e **OAuth 2.0**
por cima, com Bearer no cabeçalho. O certificado chega no pacote de acesso, que
a B3 envia depois do cadastro; em produção, depois do contrato.

Isso torna o portão explícito: **sem certificado emitido pela B3 não existe
conexão**, e nenhuma engenharia contorna isso. O ambiente de certificação é
autosserviço e gratuito, em `https://apib3i-cert.b3.com.br` (porta 2443), com
`POST /api/acesso/autosservico` para obter o pacote e
`GET /api/healthcheck/{token}` para conferir a ligação.

**O que este repositório implementa** (`b3_client.py`): o transporte com mTLS e
Bearer, o portão de consentimento, o limite de uma chamada por investidor por
dia e a classificação de frescor. Tudo exercitável sem credencial, porque o
transporte é injetado e os testes usam respostas gravadas.

**O que ele deliberadamente não implementa**: os caminhos exatos dos endpoints
de Posição, Movimentação, Negociação e Guia. A especificação está no portal de
desenvolvedores, atrás de login, e este projeto **não adivinha URL**. Elas são
configuração; enquanto estiverem vazias o cliente recusa a chamada com uma
mensagem que diz o que falta, em vez de produzir um 404 disfarçado de erro de
rede. Quem tiver acesso ao portal preenche um arquivo e a conexão fecha.

## 5. Condições operacionais

- A API é **contratada** com a B3. O ambiente de certificação é autosserviço e
  gratuito; o de produção depende de contrato. Isso é um portão real de
  cronograma, não um detalhe de implementação.
- Dados de **D-1**, publicados a partir das 8h.
- **Uma consulta por investidor por dia**, por orientação expressa do manual. A
  API Guia informa quais documentos tiveram movimentação, e é ela que evita
  varrer a base inteira.
- SLA de disponibilidade de **97% ao mês**. Cerca de um dia por mês a carteira
  simplesmente não chega.

Essa última linha virou código. `b3_client.Frescor` separa quatro estados, e a
distinção que importa é entre dois deles: **"sem movimentação"** significa que a
posição de ontem continua valendo, e **"não atualizou"** significa que o dado
exibido é de antes. Tratar os dois do mesmo jeito mostra a carteira de anteontem
como se fosse a de ontem, uma vez por mês, sem avisar — e o cliente decide vender
com base nela. A tela publica a data de referência junto do número, em vermelho
quando o dado está velho.

## 6. LGPD

Posição financeira identificada é dado pessoal. As decisões tomadas:

- CPF vira hash antes de tocar em qualquer registro nosso.
- A base legal é o consentimento, e ele é específico por escopo de endpoint.
- Revogação na B3 precisa interromper a leitura do nosso lado — o que exige
  checar a API de Autorização antes de cada carga, não confiar num flag local.
- O registro encadeado prova quando lemos e sob qual autorização. É o mesmo
  raciocínio do resto do projeto: o que não se rastreia até um artefato não se
  defende três anos depois.

## 7. Open Finance

Cobriria o que a B3 não cobre — inclusive fundos e previdência fora da B3 — mas
consumir dados de investimento exige enquadramento como participante regulado.
Enquanto isso não existir, o Open Finance entra como origem declarada de posição
lançada por outro caminho, nunca como integração.

## 8. O que este desenho deliberadamente não resolve

- **Eventos corporativos no custo.** Split, bonificação e subscrição alteram o
  preço médio. A API de Eventos Provisionados dá matéria-prima, mas a
  reconstrução correta não está implementada e o módulo não finge que está.
- **Conciliação com a nota de corretagem.** Os custos de execução são modelados;
  a nota é a verdade e chega depois.
- **Preço de renda fixa de balcão.** Sem valor de mercado vindo da B3, ele
  depende do escritório ou do cliente.
- **Fundos e previdência fora da B3.** Ficam como lançamento manual, com a
  origem declarada por posição.

## 9. Fases

| Fase | Entrega | Critério de saída |
| --- | --- | --- |
| 0 | Módulo de reconstrução e de lacunas rodando sobre extrato exportado à mão | O relatório de lacunas bate com a conferência manual em dez carteiras |
| 1 | Ambiente de certificação da B3, sem cliente real | Uma carteira de teste percorre posição, negociação e reconstrução ponta a ponta. Bloqueado em: pacote de acesso da B3 e os caminhos dos endpoints |
| 2 | Contrato de produção e consentimento de verdade | Primeiro consentimento registrado, encadeado e revogável, conferido na tela da B3 |
| 3 | Carga diária com API Guia e tratamento de indisponibilidade | A tela distingue "sem movimentação" de "não atualizou" |

---

**Fontes.** [Manual Técnico APIs – Área Logada da B3](https://www.b3.com.br/data/files/60/72/19/05/45CDF7104532BBF7AC094EA8/Manual%20Tecnico%20-%20APIs%20vf.pdf) ·
[Integrações da Área do Investidor](https://www.b3.com.br/pt_br/produtos-e-servicos/central-depositaria/canal-com-investidores/integracoes-da-area-do-investidor-apis/) ·
[Portal de desenvolvedores](https://developers.b3.com.br/apis/api-area-do-investidor)

Implementação em `b3_connection.py`; demonstração em `research_b3_connection.py`.
