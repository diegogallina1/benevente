# Dados abertos de investimentos do Open Finance

O Open Finance brasileiro tem duas famílias de API. A de **dados de clientes**
(posição, saldo, movimentação) exige ser instituição autorizada pelo Banco
Central, com certificado, registro no diretório e consentimento do titular — está
fora do alcance deste projeto, e o porquê está em
[§7 do desenho da conexão](desenho_conexao_b3.md). A de **dados abertos** não tem
esquema de segurança na especificação: os únicos parâmetros são `page` e
`page-size`. É GET público, e é o que este documento opera.

Base: `/open-banking/opendata-investments/v1`, servida por cada participante no
host dele. Não existe endpoint central; os endereços vêm do
[diretório público de participantes](https://data.directory.openbankingbrasil.org.br/participants).

## Rodar

Sem credencial. Não há chave a criar, não há `.env` a preencher, e o coletor não
envia cabeçalho de autorização — um teste prende isso.

```powershell
# 1. Quem publica dados abertos de investimentos, sem colher nada
.\.venv-benevente\Scripts\python.exe tools\build_open_finance_investments.py --listar

# 2. Ensaio: um punhado de participantes, para ver o formato do que volta
.\.venv-benevente\Scripts\python.exe tools\build_open_finance_investments.py --limite 5

# 3. Uma instituição específica
.\.venv-benevente\Scripts\python.exe tools\build_open_finance_investments.py --participante "nome do banco"

# 4. Coleta inteira. Demora: são centenas de hosts de terceiros, cinco recursos
#    cada, com pausa entre chamadas de propósito
.\.venv-benevente\Scripts\python.exe tools\build_open_finance_investments.py
```

Sai em `data/dados_abertos_open_finance.json`, que é ignorado pelo Git: é dado
público, muda toda semana e não é resultado de pesquisa. Quem precisar do número
roda o coletor, e datar a própria coleta é parte do método.

O arquivo traz `colhido_em`, o `sha256` do conteúdo de cada recurso de cada
participante, e a lista nomeada do que falhou. Host fora do ar não derruba a
coleta; ele aparece em `falhas`.

## Usar

```python
from datetime import date
from fixed_income_catalog import Index, Product, load_catalog
from open_finance_reference import carregar, conferir, termos_de_distribuicao

colheita = carregar()                      # data/dados_abertos_open_finance.json
oferta = load_catalog("grade_do_escritorio.json")[0]

conferida = conferir(oferta, date.today(), colheita.emissoes)
if conferida.conferivel:
    for comparacao in conferida.comparacoes:
        print(comparacao.emissao.emissor_nome, comparacao.leitura)
else:
    print("não conferível:", conferida.recusa)

# Termos de um fundo em cada distribuidor que o publica
for termos in termos_de_distribuicao("64.108.803/0001-91", colheita.fundos):
    print(termos.marca, termos.taxa_administracao_maxima, termos.aplicacao_minima_brl)
```

A conferência casa por emissor, tipo, indexador, faixa de vencimento, termo de
resgate e público. O CNPJ do emissor é a chave certa e o catálogo do escritório
não o carrega, então há duas saídas: passar `emissor_cnpj=` quando se souber, ou
deixar casar por nome sabendo que casar por nome é frágil.

## O que a leitura afirma, e o que ela não afirma

A API publica quatro faixas de frequência com a **mediana** de cada uma e o
percentual de operações nela, mais o mínimo e o máximo. As bordas das faixas não
são publicadas.

Então a leitura é *"as faixas cuja mediana fica abaixo desta oferta somam 70% das
operações"*, e nunca *"esta oferta está no percentil 70"*. A segunda frase é uma
interpolação com aparência de medida, e cairia na mesma linha da tela que um
número medido — é a mesma recusa que rege o custo de aquisição em
`b3_connection`.

Fora dos extremos, a leitura diz só isso: abaixo do mínimo ou acima do máximo que
aquele emissor emitiu.

## O que é recusado, e por quê

| Caso | Motivo |
| --- | --- |
| Oferta em **CDI + spread** | A especificação manda descartar operação com taxa mista em CDI, DI e SELIC. Não existe distribuição para comparar, e converter para percentual do CDI com o CDI de hoje produziria um número que muda de verdade amanhã |
| **Debênture, CRI, CRA, Tesouro, LC** | Os dados abertos publicam distribuição de remuneração só para captação bancária. Para os demais vem apenas taxa de custódia e de carregamento — o que a instituição cobra, nunca a taxa do papel |
| Comparar **entre emissores** | Taxa maior de emissor pior não é oferta melhor, é outro risco de crédito |
| Comparar **entre faixas de prazo** | A tabela regressiva do IR inverte ordem entre prazos; a faixa é parte da identidade da linha |

## O que a primeira execução real respondeu

`--listar`, `colher` e `diagnostico` rodaram inteiros em 2026-09-17, pelo botão do
workflow, porque o ambiente onde o coletor foi escrito não alcança domínio
brasileiro. Os números abaixo são dessa data, não de hoje.

- **46 de 46 participantes** responderam. A descoberta pelo caminho
  `/opendata-investments/` publicado no diretório funcionou — não foi preciso
  supor nome de família de API.
- **Linhas colhidas:** `funds` 27.478, `bank-fixed-incomes` 20.127,
  `credit-fixed-incomes` 93, `variable-incomes` 36, `treasure-titles` 29.
- **44 recursos responderam HTTP 404.** A instituição está dizendo que não
  publica aquele recurso. Isso é resposta, não falha, e o coletor conta separado.
- **63 falhas**, por causa: 40 de TLS, 18 de HTTP 4xx, 5 de HTTP 5xx.

### As 40 falhas de TLS

O diagnóstico por host fecha a conta: **8 dos 41 hosts** não validam com o bundle
padrão, e 8 × 5 recursos = 40. Dois caminhos independentes, mesmo número.

| Host | Veredito | Raiz declarada na cadeia |
| --- | --- | --- |
| `api.bradesco.com` | falha | ICP-Brasil |
| `api.openbanking.bancointer.com.br` | falha | ICP-Brasil |
| `api.openbanking.caixa.gov.br` | falha | ICP-Brasil |
| `qrcode.openfinance.banking.infinitepay.io` | 19, autoassinado na cadeia | ICP-Brasil |
| `openfinance.sicoob.com.br` | 19, autoassinado na cadeia | ICP-Brasil |
| `openbanking.api.pagseguro.com` | 20, emissor local ausente | ICP-Brasil |
| `obbr.745.cipbanfico.com` | falha | GlobalSign R6 |
| `external.openfinance.stone.com.br` | falha | GlobalSign R3 |

Seis apresentam a raiz da **ICP-Brasil** — a PKI nacional, a mesma de e-CPF e
assinatura digital. Não é certificado avulso por banco, e é por isso que
`--ca-extra` existe: acrescentar essa âncora ao processo do coletor é conserto,
não gambiarra.

### Duas leituras erradas, registradas para não voltarem

- **Raiz pública não quer dizer certificado válido.** Citibank e Stone apresentam
  raiz GlobalSign, que já está no bundle padrão, e ainda assim o coletor levanta
  `CERTIFICATE_VERIFY_FAILED` — nos oito, sem exceção. Raiz confiável com
  verificação falhando é, quase sempre, **intermediária faltando na cadeia
  enviada**. Por isso o diagnóstico passou a contar quantos certificados o
  servidor manda: cadeia curta demais é o retrato disso.
- **"Sem resposta" era o instrumento, não o servidor.** Cinco dos oito hosts
  recebiam esse rótulo porque o passo descartava o stderr do `openssl`, que é
  exatamente onde está o motivo. Os servidores responderam; quem não soube ler
  foi o diagnóstico. Ele agora lê `Verification error:`, que sai logo depois do
  handshake e sobrevive quando o bloco `SSL-Session` não chega a ser impresso, e
  quando nem isso existe imprime o código de saída do `openssl` em vez de um
  rótulo inventado.

### O que ainda não dá para responder

Duas das três perguntas originais continuam abertas, por um motivo prosaico: **a
colheita não é preservada.** O arquivo fica no runner, o runner é descartado, e
sobra o log com os totais.

- **Se algum host recusa `page-size=1000`.** O coletor pagina até a página curta,
  então um teto menor do outro lado passa despercebido no total.
- **Se `bank-fixed-incomes` traz emissor de fora do distribuidor.** O payload tem
  `issuerInstitutionCnpjNumber` separado do participante, o que sugere que uma
  corretora publique emissores de terceiros. Confirmar exige ler o arquivo, não o
  total.

Guardar a colheita como artefato da execução responde as duas. Não entrou aqui
porque exige fixar `actions/upload-artifact` num SHA, e este repositório não
adivinha referência de ação.

## Limites

- Nenhum payload tem campo de período de referência. A data é a da coleta, e o
  arquivo diz isso. Supor "mês corrente" seria inventar a metade mais importante
  de um dado datado.
- Isto não substitui a grade do escritório e não monta catálogo. Oferta comprável
  — este papel, deste emissor, com este vencimento, hoje — continua sem fonte
  pública, porque captação bancária é bilateral.
- Posição de cliente continua fora. Ver [§7 do desenho da conexão](desenho_conexao_b3.md).
