"""Cliente das APIs da Área do Investidor da B3: transporte, portão e frescor.

Este módulo é a metade da conexão que dá para construir sem contrato. A outra
metade — os caminhos exatos de cada endpoint — está atrás do portal de
desenvolvedores, que exige login, e **não é adivinhada aqui**. Caminho chutado
vira um cliente que compila, parece pronto, e falha na primeira chamada real
com uma mensagem que ninguém entende. Os caminhos são configuração; sem eles o
cliente recusa a chamada em vez de tentar.

O que é real e verificável neste arquivo:

* **mTLS mais OAuth.** O endpoint de negócio da B3 exige TLS mútuo 1.2 — o
  cliente apresenta um certificado emitido pela B3 e valida o servidor contra a
  CA dela — e por cima disso um Bearer. Sem o certificado não há conexão, e o
  certificado só existe depois do cadastro. É o portão real do cronograma, não
  um detalhe de implementação.
* **Uma consulta por investidor por dia.** É orientação expressa do manual, e a
  API Guia existe para dizer quais documentos tiveram movimentação. O cliente
  mantém um livro local e recusa a segunda chamada do dia.
* **Consentimento conferido a cada carga.** O investidor revoga dentro da B3,
  sem passar por nós. Um sinalizador local de "autorizado" seria uma permissão
  que sobrevive à revogação — então a autorização é perguntada à B3 antes de
  ler, sempre.
* **Frescor.** Os dados são de D-1, publicados a partir das 8h, com SLA de 97%
  ao mês. Cerca de um dia por mês a carteira não chega. Nada aqui devolve dado
  velho sem dizer que é velho: toda leitura carrega a data de referência e o
  estado, e "não teve movimento" é diferente de "não atualizou".

Nenhuma credencial mora neste arquivo nem no repositório. Caminho do
certificado e senha vêm do ambiente, e o módulo se recusa a rodar com valores
embutidos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
import json
import os

#: Ambiente de certificação, autosserviço e gratuito, confirmado na
#: documentação pública. O de produção depende de contrato e a URL vem no
#: pacote de acesso — não é inventada aqui.
CERT_HOST = "https://apib3i-cert.b3.com.br"
CERT_PORT = 2443

#: Endpoints que a documentação pública confirma. Os de negócio (Posição,
#: Movimentação, Negociação, Guia) ficam em configuração porque a especificação
#: deles está atrás de login.
PACOTE_DE_ACESSO = "/api/acesso/autosservico"
HEALTHCHECK = "/api/healthcheck/{token}"

#: Do manual técnico: dado de D-1, disponível a partir das 8h, uma chamada por
#: investidor por dia, SLA de 97% ao mês.
PUBLICA_A_PARTIR_DE = 8
CONSULTAS_POR_DIA = 1
SLA_MENSAL = 0.97


class Frescor(str, Enum):
    """O estado de uma leitura. A diferença entre os dois últimos é o ponto.

    Uma tela que trata "não teve movimento" e "não atualizou" do mesmo jeito
    mostra a carteira de anteontem como se fosse a de hoje. Num mês com 97% de
    SLA isso acontece por volta de uma vez por mês, sem aviso.
    """
    ATUAL = "atualizado com o fechamento de ontem"
    SEM_MOVIMENTO = "sem movimentação: a posição de ontem continua valendo"
    NAO_ATUALIZOU = "não atualizou hoje: o dado exibido é de antes"
    CEDO = "ainda antes das 8h: o dado de ontem só é publicado depois"
    SEM_CONSENTIMENTO = "autorização revogada ou ausente: nada foi lido"


class ConfiguracaoAusente(RuntimeError):
    """Falta caminho de endpoint ou credencial. Melhor que chutar."""


class ConsentimentoAusente(RuntimeError):
    """A B3 não confirma autorização para este documento."""


class LimiteDiario(RuntimeError):
    """Segunda chamada do mesmo investidor no mesmo dia."""


@dataclass(frozen=True)
class Credenciais:
    """Onde estão o certificado e o segredo. Nunca os valores em si."""
    certificado_p12: str
    senha_env: str
    ca_bundle: str
    client_id_env: str

    @classmethod
    def do_ambiente(cls) -> "Credenciais":
        faltando = [v for v in ("B3_CERT_P12", "B3_CERT_SENHA", "B3_CA_BUNDLE", "B3_CLIENT_ID")
                    if not os.environ.get(v)]
        if faltando:
            raise ConfiguracaoAusente(
                "faltam variáveis de ambiente: " + ", ".join(faltando) +
                ". O certificado é emitido pela B3 no cadastro; sem ele não há conexão.")
        return cls(certificado_p12=os.environ["B3_CERT_P12"], senha_env="B3_CERT_SENHA",
                   ca_bundle=os.environ["B3_CA_BUNDLE"], client_id_env="B3_CLIENT_ID")


@dataclass
class Endpoints:
    """Os caminhos de negócio, que vêm da especificação, não daqui.

    Ficam num arquivo de configuração para que quem tem acesso ao portal os
    preencha. Enquanto estiverem vazios, o cliente recusa a chamada — é
    preferível a um 404 disfarçado de erro de rede.
    """
    posicao: str = ""
    movimentacao: str = ""
    negociacao: str = ""
    guia: str = ""
    autorizacao: str = ""

    def exigir(self, nome: str) -> str:
        caminho = getattr(self, nome, "")
        if not caminho:
            raise ConfiguracaoAusente(
                f"o caminho da API de {nome} não está configurado. Ele está na especificação "
                f"em developers.b3.com.br, que exige login — este projeto não o adivinha.")
        return caminho

    @classmethod
    def de_arquivo(cls, path) -> "Endpoints":
        dados = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return cls(**{k: v for k, v in dados.items() if k in cls.__annotations__})


@dataclass
class LivroDeChamadas:
    """Quem já foi consultado hoje. Existe para respeitar o limite do manual."""
    por_documento: dict[str, str] = field(default_factory=dict)

    def registrar(self, documento_hash: str, dia: date) -> None:
        anterior = self.por_documento.get(documento_hash)
        if anterior == dia.isoformat():
            raise LimiteDiario(
                f"{documento_hash[:12]}… já foi consultado em {dia:%d/%m/%Y}. O manual pede uma "
                f"chamada por investidor por dia; use a API Guia para saber quem se moveu.")
        self.por_documento[documento_hash] = dia.isoformat()


@dataclass(frozen=True)
class Leitura:
    """O resultado de uma carga, com o que permite julgar se serve."""
    documento_hash: str
    frescor: Frescor
    data_referencia: date | None
    payload: dict | None = None
    lida_em: str = ""

    @property
    def utilizavel(self) -> bool:
        return self.frescor in (Frescor.ATUAL, Frescor.SEM_MOVIMENTO)

    @property
    def atraso_em_dias(self) -> int | None:
        if self.data_referencia is None or not self.lida_em:
            return None
        return (datetime.fromisoformat(self.lida_em).date() - self.data_referencia).days

    def para_tela(self) -> dict:
        return {
            "frescor": self.frescor.name.lower(),
            "explicacao": self.frescor.value,
            "data_referencia": self.data_referencia.isoformat() if self.data_referencia else None,
            "utilizavel": self.utilizavel,
            "atraso_em_dias": self.atraso_em_dias,
        }


def referencia_esperada(agora: datetime) -> date | None:
    """Qual data de referência a B3 deve ter publicado neste momento.

    Antes das 8h, o dado de ontem ainda não saiu. Depois, é o pregão anterior —
    e fim de semana e feriado não geram referência nova, o que aqui é aproximado
    pelo dia útil anterior, porque calendário de feriado é problema à parte.
    """
    if agora.hour < PUBLICA_A_PARTIR_DE:
        return None
    dia = agora.date() - timedelta(days=1)
    while dia.weekday() >= 5:
        dia -= timedelta(days=1)
    return dia


def classificar(agora: datetime, referencia_recebida: date | None,
                teve_movimentacao: bool) -> Frescor:
    """A regra que separa 'nada mudou' de 'nada chegou'."""
    esperada = referencia_esperada(agora)
    if esperada is None:
        return Frescor.CEDO
    if referencia_recebida is None or referencia_recebida < esperada:
        return Frescor.NAO_ATUALIZOU
    return Frescor.ATUAL if teve_movimentacao else Frescor.SEM_MOVIMENTO


def sessao_mtls(credenciais: Credenciais):
    """O transporte de verdade: TLS mútuo mais Bearer.

    ``requests`` só aceita certificado em PEM, e o pacote da B3 chega em ``.p12``.
    A conversão é feita fora daqui, por openssl, e o caminho dos dois arquivos
    resultantes vem do ambiente — assim nenhuma senha passa por argumento de
    linha de comando, onde ficaria visível na lista de processos:

        openssl pkcs12 -in b3.p12 -clcerts -nokeys  -out b3_cert.pem
        openssl pkcs12 -in b3.p12 -nocerts -nodes   -out b3_key.pem

    ``verify`` aponta para a CA da B3, nunca para ``False``. Desligar a
    verificação faria a conexão funcionar e deixaria de ser TLS mútuo de fato —
    é o atalho que costuma sobreviver até produção.
    """
    import requests  # local: o módulo precisa importar sem rede instalada

    sessao = requests.Session()
    sessao.cert = (credenciais.certificado_p12, os.environ.get("B3_CERT_KEY_PEM", ""))
    if not all(sessao.cert):
        raise ConfiguracaoAusente(
            "B3_CERT_P12 deve apontar para o certificado em PEM e B3_CERT_KEY_PEM para a "
            "chave, ambos convertidos do .p12 que a B3 enviou. Veja o docstring.")
    sessao.verify = credenciais.ca_bundle

    def _transporte(metodo, url, headers, params):
        resposta = sessao.request(metodo, url, headers=headers, params=params, timeout=30)
        corpo = None
        if resposta.content:
            try:
                corpo = resposta.json()
            except ValueError:
                corpo = None
        return resposta.status_code, corpo

    return _transporte


class B3Client:
    """O cliente. Não faz rede sem certificado, caminho e consentimento.

    ``transporte`` é injetado: recebe (metodo, url, headers, params) e devolve
    ``(status, corpo)``. Em produção é um ``requests.Session`` com o par de
    certificados; nos testes é um dublê com respostas gravadas. A separação
    existe para que a lógica de portão e frescor seja exercitável sem
    credencial, que é justamente o que ninguém tem antes do contrato.
    """

    def __init__(self, transporte, endpoints: Endpoints, credenciais: Credenciais | None = None,
                 host: str = CERT_HOST, livro: LivroDeChamadas | None = None) -> None:
        self.transporte = transporte
        self.endpoints = endpoints
        self.credenciais = credenciais
        self.host = host.rstrip("/")
        self.livro = livro or LivroDeChamadas()

    def _chamar(self, caminho: str, token: str, params: dict | None = None):
        return self.transporte("GET", f"{self.host}{caminho}",
                               {"Authorization": f"Bearer {token}"}, params or {})

    def tem_consentimento(self, documento_hash: str, token: str) -> bool:
        """Pergunta à B3, sempre. Nunca a um sinalizador nosso.

        Guardar 'autorizado' do nosso lado seria uma permissão que sobrevive à
        revogação feita no site da B3 — exatamente o contrário do que o
        consentimento significa.
        """
        status, corpo = self._chamar(self.endpoints.exigir("autorizacao"), token,
                                     {"documento": documento_hash})
        return status == 200 and bool((corpo or {}).get("autorizado"))

    def documentos_com_movimentacao(self, token: str, dia: date) -> set[str]:
        """A API Guia: quem se moveu. É ela que evita varrer a base inteira."""
        status, corpo = self._chamar(self.endpoints.exigir("guia"), token,
                                     {"dataReferencia": dia.isoformat()})
        if status != 200:
            return set()
        return {str(d) for d in (corpo or {}).get("documentos", [])}

    def ler_posicao(self, documento_hash: str, token: str, agora: datetime,
                    moveu: bool | None = None) -> Leitura:
        """Uma carga, com portão de consentimento, limite diário e frescor."""
        if agora.hour < PUBLICA_A_PARTIR_DE:
            return Leitura(documento_hash, Frescor.CEDO, None, None, agora.isoformat())
        if not self.tem_consentimento(documento_hash, token):
            return Leitura(documento_hash, Frescor.SEM_CONSENTIMENTO, None, None,
                           agora.isoformat())

        self.livro.registrar(documento_hash, agora.date())
        status, corpo = self._chamar(self.endpoints.exigir("posicao"), token,
                                     {"documento": documento_hash})
        if status != 200 or not corpo:
            return Leitura(documento_hash, Frescor.NAO_ATUALIZOU, None, None, agora.isoformat())

        bruta = (corpo or {}).get("dataReferencia")
        referencia = date.fromisoformat(bruta) if bruta else None
        if moveu is None:
            moveu = referencia == referencia_esperada(agora)
        return Leitura(documento_hash, classificar(agora, referencia, moveu), referencia,
                       corpo, agora.isoformat())
