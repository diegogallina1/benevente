# -*- coding: utf-8 -*-
"""Gera o protótipo da tela do mapa a partir do artefato, nunca à mão.

Números digitados à mão numa tela de demonstração já deram problema neste
projeto: uma substituição de texto trocou 9,6% dentro de +259,6% e publicou
+259,4% no site. A tela agora lê o mesmo JSON que o módulo produz, e a única
forma de um número aparecer errado aqui é ele estar errado lá.
"""
from __future__ import annotations

from pathlib import Path
import json
import sys

ROOT_PARA_MOTOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_calibration_web import nota_do_instrumento  # noqa: E402
from design_tokens import ANALITICA_LINK, FONTES_LINK, MONO, SANS, css as tokens_css  # noqa: E402
sys.path.insert(0, str(ROOT_PARA_MOTOR))
from fixed_income_catalog import motor_para_navegador  # noqa: E402

def _familia(pilha: str) -> str:
    """O primeiro nome da pilha, que é a fonte que a página realmente pede."""
    return pilha.split(",")[0].strip().strip('"')


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "portfolio_mapping_v1" / "mapping_by_profile.json"
CONEXAO = ROOT / "artifacts" / "b3_connection_v1" / "connection_example.json"
CALIBRACAO = ROOT / "artifacts" / "forecast_calibration_v1" / "calibration.json"
ACOMPANHAMENTO = ROOT / "web" / "forecast_2026.json"
MUDANCAS = ROOT / "web" / "mudancas_2026.json"
#: A grade do Tesouro serve de piso de comparação: é o papel sem risco de
#: crédito e com liquidez diária, e toda oferta de banco é medida contra ele.
OFERTAS_TESOURO = ROOT / "data" / "ofertas_tesouro.json"
OUT = ROOT / "docs" / "desenho_tela_mapa.html"


#: A aritmética da régua de renda fixa, no navegador. Fica numa constante
#: e não solta no meio da página porque o teste precisa carregar exatamente
#: este código e rodá-lo contra a versão em Python. Extrair a função do
#: HTML gerado por expressão regular funcionaria hoje e quebraria calado na
#: primeira vez que alguém mexesse na formatação.
REGUA_RF_JS = r"""/* --- a regua da renda fixa --- */
// A mesma conta que fixed_income_catalog faz em Python, refeita aqui porque a
// pessoa digita a oferta e espera o numero na hora. As tabelas nao sao
// reescritas: elas chegam prontas em DADOS.renda_fixa.motor, e um teste roda as
// duas implementacoes sobre a mesma grade de casos.

function aliquotaIR(dias) {
  const faixas = DADOS.renda_fixa.motor.ir;
  for (const f of faixas) if (dias <= f.ate_dias) return f.aliquota;
  return faixas[faixas.length - 1].aliquota;
}

// O IOF morde o rendimento antes do imposto de renda e some no trigesimo dia.
function fatorIOF(dias) {
  const tabela = DADOS.renda_fixa.motor.iof;
  if (dias >= 30) return 0;
  return tabela[Math.max(dias - 1, 0)];
}

function brutoAoAno(papel, cdi, ipca) {
  if (papel.indice === "cdi" || papel.indice === "selic") return cdi * papel.taxa;
  if (papel.indice === "cdi_mais") return cdi + papel.taxa;
  if (papel.indice === "pre") return papel.taxa;
  if (papel.indice === "ipca") return (1 + ipca) * (1 + papel.taxa) - 1;
  return NaN;
}

function diasEntre(deIso, ateIso) {
  const dia = 86400000;
  return Math.round((Date.parse(ateIso + "T00:00:00Z") - Date.parse(deIso + "T00:00:00Z")) / dia);
}

// Rendimento liquido anualizado no horizonte do proprio papel. Comparar um CDB
// de seis meses com um de tres anos pela taxa anunciada ignora que o primeiro
// paga 22,5% de imposto e o segundo 15%.
function liquidoAoAno(papel, referencia) {
  const rf = DADOS.renda_fixa;
  const regra = rf.motor.produtos[papel.tipo];
  if (!regra) return null;
  const dias = diasEntre(referencia, papel.vencimento);
  if (!(dias > 0)) return null;
  const anos = dias / rf.motor.dias_no_ano;

  const bruto = brutoAoAno(papel, rf.cdi_anual, rf.ipca_anual);
  if (!isFinite(bruto)) return null;
  const depoisDeTaxas = bruto - (papel.custodia || 0);
  const acumulado = Math.pow(1 + depoisDeTaxas, anos) - 1;

  const ir = regra.ir ? aliquotaIR(dias) : 0;
  const iof = regra.ir ? fatorIOF(dias) : 0;
  const liquidoAcumulado = acumulado * (1 - iof) * (1 - ir);
  const liquido = Math.pow(1 + liquidoAcumulado, 1 / anos) - 1;
  return {
    dias: dias, bruto: bruto, ir: ir, iof: iof, liquido: liquido,
    // Fracao do CDI bruto. E o numero que se compara, porque indice nao paga
    // imposto: um CDB anunciado a 118% do CDI entrega perto de 101% dele.
    sobre_cdi: rf.cdi_anual ? liquido / rf.cdi_anual : null,
    fgc: regra.fgc, regime: regra.regime,
  };
}

// O piso: Tesouro Selic mais curto, liquidez diaria, sem risco de credito, ja
// com custodia. Toda oferta de banco e medida contra ele.
function pisoLiquido(vencimento, referencia) {
  const piso = DADOS.renda_fixa.piso;
  return liquidoAoAno({ tipo: "TESOURO", indice: "selic", taxa: piso.rate,
                        vencimento: vencimento, custodia: piso.custody_fee_annual },
                      referencia);
}

// O resumo do FGC, sem tocar em tela. Fica aqui junto da regua porque e conta,
// e conta que imprime dinheiro precisa de teste: o ramo do teto movel so
// aparece em carteira grande, que e justamente a que ninguem monta a mao para
// conferir.
//
// "coberto" soma o que cabe em cada emissor, nao o que a pessoa tem. Espalhar
// tres milhoes por quinze bancos deixa um milhao garantido, nao tres, porque o
// teto de quatro anos e por CPF somando todas as instituicoes.
function resumoFgc(porConglomerado, limites) {
  const nomes = Object.keys(porConglomerado);
  const estouros = nomes
    .filter(n => porConglomerado[n] > limites.por_conglomerado_brl)
    .sort((x, y) => porConglomerado[y] - porConglomerado[x]);
  const coberto = nomes.reduce(
    (s, n) => s + Math.min(porConglomerado[n], limites.por_conglomerado_brl), 0);
  return {
    estouros: estouros,
    excedente_por_emissor: estouros.reduce(
      (s, n) => s + porConglomerado[n] - limites.por_conglomerado_brl, 0),
    coberto: coberto,
    excedente_movel: Math.max(0, coberto - limites.teto_movel_brl),
    acima_do_teto_movel: coberto > limites.teto_movel_brl,
  };
}

"""


HTML = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Plano de carteira</title>
__FONTES__
<style>
/* Dovetail aplicado ao Benevente. Tokens do guia, adaptados ao layout que já
   existe: canvas quase preto sob uma grade de blueprint, tipo branco, uma única
   faísca indigo.

   Três decisões que o guia obriga e valem nomear.

   O botão primário é branco com texto preto, não colorido. Não é estilo: texto
   branco sobre o indigo #6798ff dá contraste 2,80 e reprova. O guia acerta ao
   reservar o branco para a única superfície de alta luminância da página.

   O guia manda ter um acento só. O produto precisa de vermelho para valor
   negativo, que é requisito de leitura, não decoração, então são dois
   cromáticos e nada mais. Verde e amarelo saíram: o aviso de FGC passou a usar
   a borda de risco, e o selo de histórico usa indigo ou vermelho.

   E o vermelho tem contraste 1,01 contra o indigo: em escala de cinza os dois
   são o mesmo tom. Por isso nenhuma informação depende só da cor, o selo diz
   "foi" ou "NÃO foi" por escrito, e no gráfico a posição do ponto já revela se
   caiu fora da faixa.

   O guia é escuro por definição. O tema claro aqui é adaptação, não parte
   dele: mantém o indigo e inverte a pilha de superfícies. */
__TOKENS__

* { box-sizing: border-box; }
body {
  margin: 0; color: var(--fg); background: var(--canvas);
  /* Do token, e não escrita aqui. Este arquivo pedia Schibsted Grotesk e a
     página carregava só Figtree: nenhuma das duas aparecia, e o app inteiro
     renderizava na fonte do sistema. É o mesmo defeito que o site já teve, e
     ele sobreviveu aqui porque o app tem a própria folha de estilo. */
  font-family: var(--sans);
  font-size: 16px; line-height: 1.5; letter-spacing: -.25px;
  font-feature-settings: "liga";
  -webkit-font-smoothing: antialiased; overflow-wrap: break-word;
}
.wrap { max-width: 1200px; margin: 0 auto; padding: 24px 16px 96px; }
@media (min-width: 42rem) { .wrap { max-width: 42rem; padding: 64px 24px 96px; } }
.num { font-family: var(--mono);
       font-variant-numeric: tabular-nums; letter-spacing: 0; }
.neg { color: var(--neg); }
.hidden { display: none; }
::selection { background: var(--acao); color: var(--canvas); }

/* O monoespaçado em caixa alta com tracking largo: lê como metadado, não como
   texto corrido. É o que o guia usa para rotular seção. */
.label, .eyebrow {
  font-family: var(--mono);
  font-size: 12px; line-height: 1.4; letter-spacing: .85px;
  text-transform: uppercase; color: var(--acao); font-weight: 400; margin: 0;
}
h1 { font-size: 40px; line-height: 1.2; letter-spacing: -.84px; font-weight: 500;
     margin: 0 0 8px; text-wrap: balance; }
@media (min-width: 42rem) { h1 { font-size: 56px; line-height: 1.14; letter-spacing: -1.74px; } }
h2 { font-size: 24px; line-height: 1.29; letter-spacing: -.6px; font-weight: 500; margin: 0 0 8px; }
h3 { font-size: 20px; line-height: 1.33; letter-spacing: -.42px; font-weight: 500; margin: 0; }
.lede { color: var(--fg-2); font-size: 16px; line-height: 1.5; margin: 0 0 24px; }

header { padding-bottom: 24px; margin-bottom: 24px; border-bottom: 1px solid var(--line); }
.topo { display: flex; align-items: center; justify-content: space-between;
        gap: 16px; margin-bottom: 24px; }
.marca { font-family: var(--mono); font-size: 12px; letter-spacing: .85px;
         text-transform: uppercase; color: #102a43; margin: 0;
         display: inline-flex; align-items: center; gap: 8px; }
.marca .marca-b { width: 22px; height: 22px; border-radius: 6px; flex: none; }
/* No escuro o azul-marinho da marca desapareceria no fundo: a palavra passa a
   ser texto normal. O selo continua igual, porque ele carrega o proprio fundo. */
:root[data-theme="dark"] .marca { color: var(--fg); }
.marca span { color: var(--fg-2); }
header p:last-child { margin: 0; color: var(--fg-2); font-size: 16px; }

/* Pílula: o guia reserva o raio total para navegação e controles do topo. */
.tema { font: inherit; font-family: var(--mono); font-size: 12px;
        letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2);
        background: transparent; border: 1px solid var(--line-strong); border-radius: 9999px;
        min-height: 44px; padding: 0 14px; cursor: pointer;
        display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.tema:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }

.etapas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
          list-style: none; margin: 0 0 40px; padding: 0; }
.etapas li { border-top: 1px solid var(--line); padding-top: 8px;
             font-family: var(--mono); font-size: 12px;
             letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2); }
.etapas li[data-on="1"] { border-top-color: var(--acao); color: var(--fg); }
.etapas b { display: block; font-weight: 400; color: var(--acao); }

section { margin-bottom: 56px; }

/* --- conexão --- */
.seguranca { list-style: none; margin: 0 0 24px; padding: 0; border-top: 1px solid var(--line); }
.seguranca li { border-bottom: 1px solid var(--line); padding: 16px 0;
                font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.seguranca b { color: var(--fg); font-weight: 500; }
details { margin-top: 24px; border-top: 1px solid var(--line); }
details > summary { cursor: pointer; list-style: none; padding: 16px 0; min-height: 44px;
                    font-family: var(--mono); font-size: 12px;
                    letter-spacing: .85px; text-transform: uppercase; color: var(--acao);
                    display: flex; align-items: center; justify-content: space-between; gap: 16px; }
details > summary::-webkit-details-marker { display: none; }
details > summary::after { content: "+"; color: var(--fg-2); font-size: 16px; }
details[open] > summary::after { content: "–"; }
details > summary:focus-visible { outline: 2px solid var(--acao); outline-offset: -2px; }
details > summary b { color: var(--fg); font-weight: 400; }
.cols { display: grid; gap: 24px; margin-top: 0; }
.cols ul { margin: 8px 0 0; padding: 0; list-style: none; }
/* O trilho de borda que ficava aqui virava uma linha vertical no meio da tela:
   em duas colunas, o trilho da segunda cai a poucos pixels do centro da página.
   O marcador diz a mesma coisa sem desenhar a linha, e diz por forma, não por
   cor, que é a regra da casa: o vermelho e o verde têm o mesmo cinza. */
.cols li { font-size: 14px; line-height: 1.57; color: var(--fg-2);
           padding: 6px 0 6px 22px; position: relative; }
.cols li::before { content: "✓"; position: absolute; left: 0; top: 6px;
                   color: var(--acao); font-size: 13px; }
.cols .nao li::before { content: "✕"; color: var(--neg); }

/* --- superfícies --- */
.painel { background: var(--acao-fraco); border: 1px solid var(--acao); border-radius: 8px;
          padding: 24px; }
.painel .big { font-size: 40px; line-height: 1.2; letter-spacing: -.84px; font-weight: 500; }
/* O número que responde à pergunta da tela leva a cor da marca: é o único da
   página que a pessoa procura, e verde sobre a menta dá 4,66 de contraste. */
.painel .big { color: var(--acao); }
.painel p { margin: 8px 0 0; color: var(--fg-2); font-size: 14px; line-height: 1.57; }
.quando { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: baseline;
          font-family: var(--mono); font-size: 12px; letter-spacing: .85px;
          text-transform: uppercase; color: var(--fg-2);
          border-bottom: 1px solid var(--elev); padding-bottom: 16px; margin-bottom: 16px; }
.quando b { color: var(--fg); font-weight: 400; }
.quando.velho, .quando.velho b { color: var(--neg); }

.aviso { border-left: 2px solid var(--acao); background: var(--acao-fraco); border-radius: 0 8px 8px 0;
         padding: 16px; margin-top: 24px; font-size: 14px; line-height: 1.57; }
.aviso.erro { border-left-color: var(--neg); }
.aviso p { margin: 0; color: var(--fg-2); }
.aviso b { color: var(--fg); font-weight: 500; }

.barras { margin-top: 24px; }
.barra-linha { margin-bottom: 16px; }
.barra-linha > span { display: block; font-family: var(--mono);
                      font-size: 12px; letter-spacing: .85px; text-transform: uppercase;
                      color: var(--fg-2); margin-bottom: 8px; }
.legenda { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 16px;
           font-family: var(--mono); font-size: 12px; letter-spacing: .85px;
           text-transform: uppercase; color: var(--fg-2); }
.legenda i { display: inline-block; width: 8px; height: 8px; border-radius: 2px;
             margin-right: 8px; vertical-align: 0; }
/* A cor de cada quadradinho da legenda sai daqui, e não de um atributo style
   na marcação: com estilo em atributo a CSP precisaria de style-src
   'unsafe-inline', o que valeria para a página inteira. */
.legenda .em-acoes { background: var(--acao); }
.legenda .em-caixa { background: var(--line-strong); }
.legenda .fora     { background: var(--neg); }

/* --- perguntas --- */
.q { padding: 24px 0; border-top: 1px solid var(--line); }
.q:first-of-type { border-top: none; padding-top: 0; }
.q > p { margin: 0 0 8px; font-size: 20px; line-height: 1.33; letter-spacing: -.42px;
         font-weight: 500; text-wrap: pretty; }
.q .help { color: var(--fg-2); font-size: 14px; line-height: 1.57; margin: 0 0 16px; }
.opts { display: flex; flex-direction: column; gap: 8px; }
.opt { font: inherit; font-size: 14px; text-align: left; cursor: pointer;
       min-height: 44px; padding: 8px 16px; border-radius: 8px;
       border: 1px solid var(--line); background: var(--card); color: var(--fg);
       transition: border-color .12s, background .12s; }
.opt:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }
.opt[aria-pressed="true"] { background: var(--btn); color: var(--btn-fg);
                            border-color: var(--btn); font-weight: 500; }

.resumo { border-top: 1px solid var(--line); padding-top: 16px; }
.chips { margin: 0 0 8px; font-family: var(--mono); font-size: 12px;
         letter-spacing: .85px; text-transform: uppercase; color: var(--fg); }
.chips span + span::before { content: " · "; color: var(--fg-2); }
.link { font: inherit; font-size: 14px; color: var(--acao); background: none; border: 0;
        padding: 8px 0; min-height: 44px; cursor: pointer;
        text-decoration: underline; text-underline-offset: 3px; }
.link:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }
.veredito { font-size: 14px; line-height: 1.57; color: var(--fg-2); margin: 24px 0 0; }
.veredito b { color: var(--fg); font-weight: 500; }
.veredito b.neg { color: var(--neg); }

/* --- a régua --- */
.regua { margin-top: 40px; }

/* --- alertas --- */
.alerta { border-left: 2px solid var(--acao); background: var(--acao-fraco);
          border-radius: 0 8px 8px 0; padding: 16px; margin-top: 16px;
          font-size: 14px; line-height: 1.57; }
.alerta p { margin: 0; color: var(--fg-2); }
.alerta p + p { margin-top: 8px; }
.alerta b { color: var(--fg); font-weight: 500; }
.alerta .quando { font-family: var(--mono); font-size: 12px;
                  letter-spacing: .5px; color: var(--acao); }

/* --- a carteira inteira --- */
.carteira { margin-top: 32px; }
/* Sem flex-wrap a terceira linha, que é a procedência, ficava na mesma faixa do
   valor e vazava cortada para fora do cartão. E sem min-width zero o nome longo
   quebrava letra a letra em vez de encolher. */
.pos { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px;
       padding: 10px 0; border-top: 1px solid var(--line); font-size: 14px; }
.pos:first-of-type { border-top: 0; }
.pos b { font-weight: 500; color: var(--fg); flex: 1 1 auto; min-width: 0; }
.pos .val { font-family: var(--mono); font-variant-numeric: tabular-nums;
            color: var(--fg); white-space: nowrap; }
/* "sem-valor" e nao "falta": .falta ja existe neste app, com borda vermelha a
   esquerda, e o nome repetido colava um risco vermelho no numero. */
.pos .val.sem-valor { color: var(--neg); }
.pos .de { font-size: 12px; color: var(--fg-2); flex: 0 0 100%; margin-top: 2px; }
.pos .de b { font-weight: 400; color: var(--fg-2); }
.total { margin: 14px 0 0; font-family: var(--mono);
         font-size: 14px; display: flex; justify-content: space-between; gap: 12px;
         border-top: 1px solid var(--line-strong); padding-top: 12px; }
.pos-acao { font: inherit; font-size: 12px; background: none; border: 0; padding: 0;
            color: var(--acao); cursor: pointer; text-decoration: underline;
            text-underline-offset: 3px; }
#add-det { margin-top: 24px; }
.add-corpo { display: flex; flex-direction: column; gap: 12px; padding-top: 10px; }
.ajuda { margin: 0; font-size: 13px; line-height: 1.5; color: var(--fg-2); }
/* Os campos fluem por largura. Um por linha, o formulário de renda fixa tinha
   sete alturas de campo e obrigava a rolar para achar o botão. */
.add-linha { display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(min(11rem, 100%), 1fr)); }
.add-linha label { display: flex; flex-direction: column; gap: 4px; font-size: 12px;
                   color: var(--fg-2); }
.add-linha input, .add-linha select { font: inherit; font-size: 14px; padding: 8px 10px;
  border: 1px solid var(--line-strong); border-radius: 6px; background: var(--canvas);
  color: var(--fg); min-height: 40px; }
.erro-campo { margin: 0; font-size: 13px; color: var(--neg); }

/* --- acompanhar --- */
.ac-fig { margin: 24px 0 0; }
.ac-fig svg { display: block; width: 100%; height: auto; }
.ac-fig figcaption { margin-top: 8px; font-size: 12px; line-height: 1.4; color: var(--fg-2); }
#ac-frase { margin: 8px 0 0; font-size: 14px; line-height: 1.57; color: var(--fg-2); }
#ac-frase b { color: var(--fg); font-weight: 500; }
.regua h3 { margin-bottom: 8px; }
.regua p { margin: 0 0 16px; font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.regua p b { color: var(--fg); font-weight: 500; }
.regua p b.neg { color: var(--neg); }
.regua figure { margin: 16px 0 0; }
.regua svg { display: block; width: 100%; height: auto; }
.regua figcaption { margin-top: 8px; font-size: 12px; line-height: 1.4; color: var(--fg-2); }
.regua .chaves { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 8px;
                 font-family: var(--mono); font-size: 12px;
                 letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2); }
.regua .chaves i { display: inline-block; width: 8px; height: 8px; border-radius: 2px;
                   margin-right: 8px; vertical-align: 0; }

/* --- os dois planos --- */
.planos { display: grid; gap: 16px; }
.plano { text-align: left; font: inherit; cursor: pointer; color: var(--fg);
         background: var(--card); border: 1px solid var(--elev); border-radius: 8px;
         padding: 24px; display: flex; flex-direction: column; gap: 16px;
         transition: border-color .12s, background .12s; }
.plano:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }
.plano[aria-pressed="true"] { border-color: var(--acao); background: var(--acao-fraco); }
.plano .custo { font-size: 40px; line-height: 1.2; letter-spacing: -.84px; font-weight: 500; }
.plano .custo small { display: block; font-family: var(--mono);
                      font-size: 12px; letter-spacing: .85px; text-transform: uppercase;
                      color: var(--fg-2); margin-top: 8px; }
.plano dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 8px 16px;
            font-size: 14px; }
.plano dt { color: var(--fg-2); } .plano dd { margin: 0; text-align: right; }
.falta { border-left: 2px solid var(--neg); background: var(--canvas); border-radius: 0 4px 4px 0;
         padding: 16px; font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.falta b { display: block; color: var(--neg); font-weight: 500; margin-bottom: 8px; }
.selo { font-size: 12px; line-height: 1.4; padding: 8px 16px; margin-top: auto;
        border-left: 2px solid var(--acao); background: var(--canvas);
        border-radius: 0 4px 4px 0; color: var(--fg-2); }
.selo.nao { border-left-color: var(--neg); }

/* --- o que muda --- */
.razao { margin-top: 24px; }
.grupo { font-family: var(--mono); font-size: 12px; letter-spacing: .85px;
         text-transform: uppercase; color: var(--fg-2); margin: 24px 0 0;
         padding-bottom: 8px; border-bottom: 1px solid var(--line); }
.grupo:first-child { margin-top: 0; }
.linha { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px 16px;
         padding: 16px 0; border-bottom: 1px solid var(--line); align-items: baseline; }
.linha b { font-weight: 500; font-size: 16px; }
.linha .porque { grid-column: 1 / -1; color: var(--fg-2); font-size: 12px; line-height: 1.4; }
.linha .val { grid-column: 2; grid-row: 1; text-align: right; font-size: 16px; white-space: nowrap; }
.linha .val small { display: block; color: var(--fg-2); font-size: 12px; }

.conta { margin-top: 24px; background: var(--card); border: 1px solid var(--elev);
         border-radius: 8px; padding: 8px 24px 24px; }
.conta div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px 16px;
             padding: 16px 0; font-size: 14px; line-height: 1.57;
             border-bottom: 1px solid var(--elev); }
.conta div span:last-child { margin-left: auto; }
.conta .total { font-weight: 500; border-bottom: 0; color: var(--fg); }
.conta p { margin: 16px 0 0; font-size: 12px; line-height: 1.4; color: var(--fg-2); }

/* Botão do guia: fundo branco, texto preto, raio 8. É o único elemento de alta
   luminância da página, e é isso que o torna a ação óbvia. */
.acoes { margin-top: 24px; display: flex; flex-direction: column; gap: 16px; }
.btn { font: inherit; font-size: 14px; font-weight: 500; cursor: pointer;
       border: 1px solid var(--btn); border-radius: 8px; min-height: 44px;
       padding: 8px 16px; background: var(--btn); color: var(--btn-fg); width: 100%; }
.btn:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }
/* Desabilitado aqui não é um controle apagado: é o botão que virou o aviso
   "Conta conectada", e essa frase precisa ser lida. Com --fg-3 ela dava 4,25 de
   contraste e reprovava; --fg-2 dá 7,36. O token de desabilitado continua
   existindo para controles que a pessoa não precisa ler. */
.btn:disabled { background: transparent; color: var(--fg-2); border-color: var(--line-strong);
                cursor: default; }
.acoes span { font-size: 12px; line-height: 1.4; color: var(--fg-2); }

.registro { margin-top: 16px; background: var(--card); border: 1px solid var(--elev);
            border-radius: 8px; padding: 24px; }
.registro p { margin: 0 0 16px; font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.registro pre { margin: 0; overflow-x: auto; font-family: var(--mono);
                font-size: 12px; line-height: 1.6; color: var(--fg); }

.informar { margin-top: 16px; }
.informar label { display: block; font-family: var(--mono); font-size: 12px;
                  letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2);
                  margin-bottom: 8px; }
.campo { display: flex; flex-wrap: wrap; gap: 8px; }
.campo input { font: inherit; font-family: var(--mono); font-size: 16px;
               flex: 1 1 10rem; min-width: 0; min-height: 44px; padding: 8px 16px;
               color: var(--fg); background: var(--elev); border: 1px solid var(--line);
               border-radius: 8px; }
.campo input:focus { outline: 2px solid var(--acao); outline-offset: -1px; }
.campo input[aria-invalid="true"] { border-color: var(--neg); }
.campo .btn { flex: 0 0 auto; width: auto; min-width: 9rem; }
.informar .ajuda { font-size: 12px; line-height: 1.4; color: var(--fg-2); margin: 8px 0 0; }
.informar .ajuda.ruim { color: var(--neg); }
.resolvido { border-left: 2px solid var(--acao); background: var(--card);
             border-radius: 0 8px 8px 0; padding: 16px; margin-top: 24px;
             font-size: 14px; line-height: 1.57; }
.resolvido p { margin: 0; color: var(--fg-2); }
.resolvido b { color: var(--fg); font-weight: 500; }

footer { border-top: 1px solid var(--line); margin-top: 80px; padding-top: 24px;
         font-size: 12px; line-height: 1.4; color: var(--fg-2); }
footer p { margin: 0 0 8px; }
footer code { font-family: var(--mono); }
footer a { color: var(--acao); }

@media (min-width: 42rem) {
  .lede, header p:last-child, footer p { max-width: 640px; }
  .opts { flex-direction: row; flex-wrap: wrap; }
  .opt { padding: 8px 16px; }
  .barra-linha { display: grid; grid-template-columns: 96px 1fr; gap: 16px; align-items: center; }
  .barra-linha > span { text-align: right; margin-bottom: 0; }
  .cols { grid-template-columns: 1fr 1fr; gap: 32px; }
  .planos { grid-template-columns: 1fr 1fr; }
  .linha .porque { grid-column: 1; }
  .acoes { flex-direction: row; align-items: center; flex-wrap: wrap; }
  .btn { width: auto; min-width: 14rem; }
}
@media (hover: hover) and (pointer: fine) {
  /* Encolher alvo de toque é decisão sobre o ponteiro, não sobre a largura. */
  .tema, .link { min-height: 32px; }
  .btn { min-height: 36px; }
  .opt:hover { border-color: var(--line-strong); background: var(--elev); }
  .opt[aria-pressed="true"]:hover { background: var(--btn); }
  .plano:hover { border-color: var(--line-strong); }
  .btn:hover:not(:disabled) { opacity: .88; }
  .tema:hover { color: var(--fg); border-color: var(--fg-2); }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; scroll-behavior: auto !important; }
}
</style>

<div class="wrap">
<header>
  <div class="topo">
    <p class="marca"><svg class="marca-b" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="16" fill="#102a43"/><path d="M19 48V16h15.5c8.7 0 14 3.4 14 9.9 0 4.1-2.4 7.1-6.3 8.3 4.8 1.1 7.8 4.2 7.8 8.8C50 49.7 44.4 52 35.4 52H19zm9-19.5h6.6c3.5 0 5.4-1.3 5.4-3.8 0-2.4-1.9-3.6-5.4-3.6H28v7.4zm0 16.2h7.8c3.7 0 5.6-1.4 5.6-4.1 0-2.8-1.9-4.1-5.6-4.1H28v8.2z" fill="#f7fbf8"/></svg>Benevente <span>· protótipo</span></p>
    <button class="tema" type="button" id="tema" aria-label="Alternar tema claro e escuro">
      <span aria-hidden="true" id="tema-icone"></span><span id="tema-txt">Tema</span>
    </button>
  </div>
  <h1>Plano de carteira</h1>
  <p>Conecte a B3, responda quatro perguntas, veja dois planos com o custo de cada um.</p>
</header>

<ol class="etapas" id="etapas">
  <li data-on="1"><b>1</b>Conectar</li>
  <li><b>2</b>Perguntas</li>
  <li><b>3</b>Seu plano</li>
  <li><b>4</b>Acompanhar</li>
</ol>

<section id="conexao">
  <h2>Conectar a B3</h2>
  <p class="lede">Sua carteira vem direto da B3, com a sua autorização.</p>
  <ul class="seguranca">
    <li><b>Você entra no site da B3, não aqui.</b> A autorização acontece lá dentro,
        com o login da própria B3.</li>
    <li><b>A sua senha não passa por nós.</b> Nunca a vemos e nunca a guardamos.</li>
    <li><b>Você desliga quando quiser.</b> Em investidor.b3.com.br, na sua conta, em
        Segurança, Aplicativos e Sites.</li>
  </ul>
  <button class="btn" type="button" id="conectar">Conectar minha conta da B3</button>
  <div id="chegou" class="hidden">
    <div class="painel">
      <div class="big num" id="chegou-tit"></div>
      <p id="chegou-txt"></p>
    </div>
    <details>
      <summary><span><b>O que vem e o que não vem da B3</b></span></summary>
      <div class="cols">
        <div><p class="label">Vem</p><ul id="vem"></ul></div>
        <div><p class="label">Não vem</p><ul id="nvem" class="nao"></ul></div>
      </div>
    </details>
    <div class="aviso erro" id="lacuna"></div>
  </div>
</section>

<section id="perguntas" class="hidden">
  <h2>Quatro perguntas</h2>
  <p class="lede">Vale a resposta mais apertada. Dá para apontar qual decidiu.</p>
  <div id="qs"></div>
  <div id="resumo" class="resumo hidden">
    <p class="chips" id="chips"></p>
    <button class="link" type="button" id="alterar">Alterar respostas</button>
  </div>
  <p class="veredito" id="veredito"></p>
</section>

<section id="mapa" class="hidden">
  <h2>Sua carteira hoje</h2>
  <p class="lede">Cada posição mostra de onde o dado veio.</p>
  <div class="painel">
    <p class="quando" id="quando"></p>
    <div class="big num" id="aderencia"></div>
    <p id="aderencia-txt"></p>
  </div>
  <div class="barras">
    <div class="barra-linha"><span>hoje</span><div id="bar-hoje"></div></div>
    <div class="barra-linha"><span>seu perfil</span><div id="bar-alvo"></div></div>
    <div class="legenda">
      <span><i class="em-acoes"></i>ações</span>
      <span><i class="em-caixa"></i>renda fixa e caixa</span>
      <span><i class="fora"></i>fora da estratégia</span>
    </div>
  </div>
  <div class="aviso" id="fgc"></div>

  <div class="carteira">
    <p class="label">Tudo o que você tem</p>
    <div id="lista-posicoes"></div>
    <p class="total" id="total-carteira"></p>
    <div class="aviso erro hidden" id="sem-valor"></div>
  </div>

  <details id="add-det">
    <summary>Acrescentar o que a B3 não manda</summary>
    <div class="add-corpo">
      <p class="ajuda">CDB, LCI, LCA, previdência, cripto, imóvel. Papel de renda fixa
         entra na régua líquida e no limite do FGC.</p>
      <div class="add-linha">
        <label>O que é<input id="add-nome" type="text" placeholder="Previdência PGBL"></label>
        <label>Tipo<select id="add-tipo">
          <option>CDB</option><option>LCI</option><option>LCA</option>
          <option>LC</option><option>RDB</option>
          <option>previdência</option><option>cripto</option><option>conta no exterior</option>
          <option>imóvel</option><option>participação em empresa</option><option>outro</option>
        </select></label>
        <label>Quanto vale<input id="add-valor" type="text" inputmode="decimal" placeholder="R$ 0,00"></label>
      </div>
      <div class="add-linha hidden" id="add-rf">
        <label>Quem emite<input id="add-emissor" type="text" placeholder="Banco Exemplo"></label>
        <label>Como rende<select id="add-indice">
          <option value="cdi">% do CDI</option>
          <option value="cdi_mais">CDI mais taxa</option>
          <option value="pre">prefixado</option>
          <option value="ipca">IPCA mais taxa</option>
        </select></label>
        <label>Taxa<input id="add-taxa" type="text" inputmode="decimal" placeholder="110"></label>
        <label>Vencimento<input id="add-venc" type="date"></label>
      </div>
      <button class="link" type="button" id="add-botao">Acrescentar</button>
      <p class="erro-campo hidden" id="add-erro"></p>
      <div class="hidden" id="add-regua"></div>
    </div>
  </details>

  <div class="regua" id="regua"></div>
</section>

<section id="planos-sec" class="hidden">
  <h2>Dois planos</h2>
  <p class="lede">Um troca seus ativos pela seleção da política. O outro mantém e só protege. As duas ficam registradas.</p>
  <div class="planos" id="planos"></div>
</section>

<section id="razao-sec" class="hidden">
  <h2 id="razao-h"></h2>
  <p class="lede" id="razao-lede"></p>
  <details id="razao-det">
    <summary><span id="razao-resumo"></span></summary>
    <div class="razao" id="razao"></div>
  </details>
  <div class="conta" id="conta"></div>
  <div class="acoes">
    <button class="btn" type="button" id="gerar">Gerar o dossiê do plano</button>
    <span>O registro da sua decisão, com o plano que você não escolheu. Neste protótipo ele aparece na tela; no app, vira PDF assinável.</span>
  </div>
  <div class="registro hidden" id="registro"></div>
</section>

<section id="alertas-sec" class="hidden">
  <h2>O que mudou desde a sua decisão</h2>
  <p class="lede" id="alertas-lede"></p>
  <div id="alertas"></div>
</section>

<section id="acompanhar-sec" class="hidden">
  <h2>Acompanhar</h2>
  <p class="lede">O ano contra a faixa projetada para ele. A faixa não se mexe.</p>
  <div class="painel">
    <p class="label" id="ac-quando"></p>
    <div class="big num" id="ac-numero"></div>
    <p id="ac-frase"></p>
  </div>
  <figure class="ac-fig">
    <div id="ac-grafico"></div>
    <figcaption id="ac-legenda"></figcaption>
  </figure>
  <div class="aviso" id="ac-limite"></div>
</section>

<footer>
  <p><b>Protótipo.</b> A carteira é sintética. Os números vêm de
     <code>portfolio_mapping.py</code>, o perfil de <code>client_intake.py</code> e a leitura
     da B3 de <code>b3_connection.py</code>. Nenhuma ordem é transmitida por esta tela.</p>
  <p>O custo aparece antes do benefício de propósito, e nenhuma tela deste projeto promete
     patrimônio futuro: o que a Benevente publica é o quanto a própria régua erra.</p>
  <p>__TIPOGRAFIA__</p>
</footer>
</div>

<script>
const DADOS = __DADOS__;
const BRL = v => "R$ " + Math.round(v).toLocaleString("pt-BR");
const PCT = (v, c = 1) => (v * 100).toFixed(c).replace(".", ",") + "%";
// A ordem da escada vem do payload, do mais apertado ao mais solto. Escrita
// à mão ela ficou com três degraus: quando a escada ganhou o quarto, a
// resposta que apertava para ele dava RANK indefinido, a comparação virava
// falsa e o perfil caía silenciosamente no degrau de cima.
const RANK = Object.fromEntries(Object.keys(DADOS.profiles).map((n, i) => [n, i]));
const respostas = {};

const $ = id => document.getElementById(id);
// Nome de posicao e texto que a propria pessoa digitou, e ele chega a innerHTML
// em mais de um lugar. A exposicao aqui e ao proprio navegador de quem digitou,
// porque nada disto e guardado nem compartilhado, mas texto de usuario dentro de
// marcacao e um habito que envelhece mal quando o proximo campo vier de fora.
const escapa = v => String(v).replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};
const mostra = (...ids) => ids.forEach(i => $(i).classList.remove("hidden"));
const esconde = (...ids) => ids.forEach(i => $(i).classList.add("hidden"));
const etapa = n => [...$("etapas").children].forEach((li, i) =>
  i <= n ? li.setAttribute("data-on", "1") : li.removeAttribute("data-on"));

/* --- tema --- */
// O claro é o padrão, e é o que o :root descreve. O guia é escuro por
// definição, mas o padrão foi pedido claro, e a inversão também conserta um
// defeito: enquanto o escuro era o :root, qualquer regra que tivesse escapado
// com cor literal ficava com a cor do escuro dentro do tema claro, que é a
// borda preta em volta de cartão branco e o texto que some no fundo.
const temaBtn = $("tema");
const guardado = (() => { try { return localStorage.getItem("tema"); } catch (e) { return null; } })();
function aplicaTema(valor) {
  const escuro = valor === "dark";
  if (escuro) document.documentElement.setAttribute("data-theme", "dark");
  else document.documentElement.removeAttribute("data-theme");
  $("tema-icone").textContent = escuro ? "☾" : "☀";
  $("tema-txt").textContent = escuro ? "Escuro" : "Claro";
  temaBtn.setAttribute("aria-pressed", String(escuro));
}
aplicaTema(guardado === "dark" ? "dark" : "light");
temaBtn.onclick = () => {
  const novo = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  aplicaTema(novo);
  try { localStorage.setItem("tema", novo); } catch (e) { /* janela anônima: segue sem salvar */ }
};

/* --- rolagem --- */
// Rolar a cada clique era o defeito: quando o destino já está à vista, mover a
// página desorienta, e no celular a barra do navegador aparece e some a cada
// movimento. Só rola quando o alvo está mesmo fora de vista, e nunca com
// animação para quem pediu movimento reduzido no sistema.
const menosMovimento = matchMedia("(prefers-reduced-motion: reduce)");
function rolaPara(alvo, bloco) {
  if (!alvo) return;
  const r = alvo.getBoundingClientRect();
  const altura = window.innerHeight || document.documentElement.clientHeight;
  if (r.top >= 0 && r.top <= altura * 0.6) return;
  const posicao = { block: bloco || "nearest" };
  if (menosMovimento.matches) { alvo.scrollIntoView(posicao); return; }
  const antes = alvo.getBoundingClientRect().top;
  alvo.scrollIntoView({ behavior: "smooth", ...posicao });
  // Nem todo contexto anima o scroll suave, e onde ele não anima nada acontece:
  // a pessoa clica a resposta e a página fica parada, como se o clique tivesse
  // falhado. Medido num renderizador onde "smooth" não move e "auto" move. Meio
  // segundo depois, se não saiu do lugar, vai de uma vez: chegar importa mais
  // que deslizar.
  setTimeout(() => {
    if (Math.abs(alvo.getBoundingClientRect().top - antes) < 2) alvo.scrollIntoView(posicao);
  }, 500);
}

/* --- conexão com a B3 --- */
const b3 = DADOS.b3;
const pendentes = Object.entries(b3.gaps.pendentes);
const nomesPendentes = pendentes.map(([t]) => t).join(", ");

$("conectar").onclick = () => {
  mostra("chegou");
  $("conectar").textContent = "Conta conectada";
  $("conectar").disabled = true;

  const total = Object.keys(b3.cost_basis).length;
  $("chegou-tit").textContent = b3.gaps.com_custo_defensavel + " de " + total +
    " posições completas";
  $("chegou-txt").textContent =
    "A B3 manda o que você tem, mas não manda por quanto você comprou, esse dado não " +
    "existe nas APIs dela. Ele é remontado a partir das suas negociações, e o histórico " +
    "começa em " + b3.base_starts.split("-").reverse().join("/") + ".";

  const lista = (id, itens) => {
    const ul = $(id); ul.innerHTML = "";
    itens.forEach(t => ul.append(el("li", null, t)));
  };
  lista("vem", b3.coverage.entrega);
  lista("nvem", b3.coverage.nao_entrega.concat(b3.coverage.entrega_pela_metade));

  const alerta = $("lacuna");
  if (!pendentes.length) alerta.style.display = "none";
  else {
    const [ticker, dados] = pendentes[0];
    const jaSabe = (b3.cost_basis[ticker] || {}).valor_brl || 0;
    alerta.innerHTML = "<p><b>Falta saber por quanto você comprou " + ticker + ".</b> " +
      "A compra é anterior a " + b3.base_starts.split("-").reverse().join("/") + " e não " +
      "está no histórico da B3. Sem ela o imposto não sai, e aqui não se chuta imposto: " +
      "chutado tem a mesma cara de calculado.</p>";
    alerta.append(campoDeCusto(ticker, jaSabe));
  }
  mostra("perguntas");
  etapa(1);
  rolaPara($("perguntas"), "start");
};

/* --- o custo informado pelo cliente --- */
// A aritmética abaixo é transcrição literal de resolver(), em
// tests/test_b3_connection.py, que é comparada com o módulo de verdade em
// vários valores de custo. Reescrever a apuração inteira aqui criaria duas
// implementações da mesma regra, e elas divergem em silêncio porque as duas
// continuam plausíveis sozinhas. A tela faz só a aritmética final.
const custosInformados = {};
let perfilAtual = null, planoAtual = null;

// Aceita "180.000,50" e "180000,50"; um ponto seguido de uma ou duas casas é
// lido como decimal, porque é assim que muita gente digita.
function leValor(txt) {
  const limpo = String(txt).replace(/[^\d.,-]/g, "");
  if (!limpo) return NaN;
  const decimal = limpo.includes(",")
    ? limpo.replace(/\./g, "").replace(",", ".")
    : (/^\d+\.\d{1,2}$/.test(limpo) ? limpo : limpo.replace(/\./g, ""));
  return parseFloat(decimal);
}

function campoDeCusto(ticker, jaSabe) {
  const caixa = el("div", "informar");
  const anterior = custosInformados[ticker];
  caixa.innerHTML =
    "<label for='custo'>Quanto você pagou, ao todo, pela sua posição em " + ticker + "?</label>" +
    "<div class='campo'><input id='custo' type='text' inputmode='decimal' autocomplete='off' " +
    "placeholder='R$ 0,00' aria-describedby='custo-ajuda'>" +
    "<button class='btn' type='button' id='custo-ok'>Informar</button></div>" +
    "<p class='ajuda' id='custo-ajuda'>Some tudo que pagou pela posição, em todas as compras. " +
    (jaSabe > 0 ? "Das compras que a B3 mandou já sabemos " + BRL(jaSabe) + ". Falta somar as " +
                  "anteriores. " : "") +
    "O valor está na sua declaração de imposto de renda ou nas notas de corretagem.</p>";
  const campo = caixa.querySelector("#custo");
  // Campo de dinheiro devolve centavo: 1.000,5 é um valor que ninguém digitou.
  if (anterior !== undefined) campo.value = anterior.toLocaleString("pt-BR",
    anterior % 1 ? { minimumFractionDigits: 2 } : {});
  caixa.querySelector("#custo-ok").onclick = () => informar(ticker, jaSabe);
  campo.onkeydown = e => { if (e.key === "Enter") informar(ticker, jaSabe); };
  return caixa;
}

function informar(ticker, jaSabe) {
  const campo = $("custo"), ajuda = $("custo-ajuda");
  const valor = leValor(campo.value);
  if (!isFinite(valor) || valor < 0) {
    campo.setAttribute("aria-invalid", "true");
    ajuda.className = "ajuda ruim";
    ajuda.textContent = "Informe um valor em reais, como 180.000,00.";
    campo.focus();
    return;
  }
  custosInformados[ticker] = valor;
  const alerta = $("lacuna");
  alerta.className = "resolvido";
  alerta.innerHTML = "<p><b>" + ticker + ": " + BRL(valor) + " informados.</b> " +
    "O imposto fecha, e os dois planos abaixo já estão com ele. O valor foi declarado por " +
    "você e não conferido contra nota de corretagem.</p>";
  // Um dígito a mais muda o imposto em ordem de grandeza, e quem digitou errado
  // precisa de caminho de volta, sem ele, o único recerto é recarregar a página.
  const trocar = el("button", "link", "Corrigir o valor");
  trocar.type = "button";
  trocar.onclick = () => {
    alerta.className = "aviso erro";
    alerta.innerHTML = "<p><b>Corrigindo o custo de " + ticker + ".</b> O valor anterior era " +
      BRL(valor) + ".</p>";
    alerta.append(campoDeCusto(ticker, jaSabe));
    $("custo").focus();
  };
  alerta.append(trocar);
  if (perfilAtual) render(perfilAtual);
}

function resolvido(m) {
  const r = m.pending_resolution;
  if (!r || !r.positions || !r.positions.length) return m;
  if (r.positions.some(p => !(p.ticker in custosInformados))) return m;

  let total = r.fixed_brl;
  const impostoDaCesta = {}, ganhoDaCesta = {};
  Object.entries(r.buckets).forEach(([cesta, cfg]) => {
    let ganho = cfg.other_gain_brl;
    r.positions.forEach(p => {
      if (p.bucket === cesta) ganho += p.sale_brl - custosInformados[p.ticker] * p.sale_fraction;
    });
    ganho -= cfg.carried_loss_brl;
    const imposto = (ganho > 0 && cesta !== "fora_do_escopo" && !cfg.exempt_month)
      ? ganho * cfg.rate : 0;
    ganhoDaCesta[cesta] = ganho + cfg.carried_loss_brl;
    impostoDaCesta[cesta] = imposto;
    total += imposto;
  });

  const cestas = Object.assign({}, m.tax_by_bucket);
  Object.keys(impostoDaCesta).forEach(c => {
    cestas[c] = { realised_gain_brl: ganhoDaCesta[c], tax_brl: impostoDaCesta[c] };
  });
  const moves = m.moves.map(x => {
    if (!(x.ticker in custosInformados) || x.action === "manter") return x;
    const p = r.positions.find(q => q.ticker === x.ticker);
    if (!p) return x;
    return Object.assign({}, x, {
      realised_gain_brl: p.sale_brl - custosInformados[x.ticker] * p.sale_fraction,
      notes: ["custo informado por você, não conferido contra nota de corretagem"],
    });
  });
  return Object.assign({}, m, {
    transition_tax_brl: total - m.transition_cost_brl,
    transition_total_brl: total,
    transition_cost_pct: total / m.total_brl,
    tax_is_complete: true,
    positions_without_cost_basis: [],
    unpriced_sale_brl: 0,
    tax_by_bucket: cestas,
    moves: moves,
  });
}

/* --- perguntas --- */
const escolha = DADOS.questionnaire.questions.filter(q => q.kind === "escolha");
const qsBox = $("qs");
// As caixas ficam guardadas para a resposta poder levar à pergunta seguinte. Sem
// isso a pessoa responde e rola à mão quatro vezes: são quatro cliques de
// decisão e quatro de navegação, e metade do tempo era a metade que não decide.
const caixasQ = [];
escolha.forEach((q, i) => {
  const box = el("div", "q");
  box.append(el("p", null, q.prompt), el("p", "help", q.help));
  const opts = el("div", "opts");
  q.options.forEach(o => {
    const b = el("button", "opt", o.label);
    b.type = "button";
    b.setAttribute("aria-pressed", "false");
    b.onclick = () => {
      respostas[q.key] = o;
      opts.querySelectorAll(".opt").forEach(x => x.setAttribute("aria-pressed", "false"));
      b.setAttribute("aria-pressed", "true");
      avaliar();
      // Só avança enquanto está respondendo pela primeira vez. Quem voltou para
      // trocar uma resposta quer ver o que mudou, e ser empurrado para a frente
      // a cada clique é o oposto de ajudar.
      if (!editando) seguinte(i);
    };
    opts.append(b);
  });
  box.append(opts);
  qsBox.append(box);
  caixasQ.push(box);
});

// A próxima pergunta ainda sem resposta, ou o plano quando não sobrar nenhuma.
function seguinte(depoisDe) {
  for (let i = depoisDe + 1; i < escolha.length; i++) {
    if (!respostas[escolha[i].key]) { rolaPara(caixasQ[i], "start"); return; }
  }
  for (let i = 0; i < escolha.length; i++) {
    if (!respostas[escolha[i].key]) { rolaPara(caixasQ[i], "start"); return; }
  }
  rolaPara($("mapa"), "start");
}

const resumoBox = $("resumo");
// Quem abriu o formulário para mudar uma resposta continua com ele aberto: antes
// ele fechava sozinho a cada clique, e a página saltava a cada opção escolhida.
// Fecha quando a pessoa disser que terminou.
let editando = false;
function editar(abrir) {
  editando = abrir;
  qsBox.classList.toggle("hidden", !abrir);
  $("chips").classList.toggle("hidden", abrir);
  $("alterar").textContent = abrir ? "Pronto" : "Alterar respostas";
  if (abrir) rolaPara(qsBox, "start");
}
$("alterar").onclick = () => editar(!editando);

function avaliar() {
  if (Object.keys(respostas).length < escolha.length) {
    $("veredito").textContent = "";
    esconde("mapa", "planos-sec", "razao-sec", "acompanhar-sec", "alertas-sec");
    return;
  }
  // Respondido, o formulário vira uma linha: no celular, deixá-lo aberto obriga
  // a rolar por tudo que já foi respondido para chegar ao resultado.
  if (!editando) qsBox.classList.add("hidden");
  resumoBox.classList.remove("hidden");
  $("chips").innerHTML = escolha.map(q => "<span>" + respostas[q.key].brief + "</span>").join("");

  // O perfil é o menor teto, igual ao módulo: sem soma, sem peso, sem nota.
  let perfil = "arrojado";
  escolha.forEach(q => {
    const o = respostas[q.key];
    if (o.caps_profile && RANK[o.caps_profile] < RANK[perfil]) perfil = o.caps_profile;
  });
  // Todas as respostas que prenderam no teto final, não só a primeira: quando
  // duas apertam igual, mostrar uma faz a outra parecer não ter contado.
  const causas = escolha.map(q => respostas[q.key])
    .filter(o => o.caps_profile === perfil && o.note);
  const pior = DADOS.questionnaire.worst_measured_drawdown[perfil];
  $("veredito").innerHTML = "Perfil <b>" + perfil + "</b>, " +
    (causas.length ? causas.map(o => o.note).join(", e ")
                   : "nenhuma resposta impôs teto abaixo do máximo") +
    ". A pior queda já medida neste perfil foi de <b class='num neg'>" + PCT(pior) + "</b>.";
  etapa(2);
  if (perfilAtual !== perfil) planoAtual = null;
  render(perfil);
}

/* --- mapa --- */
function render(perfil) {
  perfilAtual = perfil;
  desenhaCarteira();
  const p = DADOS.profiles[perfil];
  const a = resolvido(p.adequar), b = resolvido(p.adaptar);
  mostra("mapa", "planos-sec");

  // "Sem movimentação" e "não atualizou" precisam ser distinguíveis aqui. Com
  // 97% de SLA a carteira falha em chegar cerca de uma vez por mês, e tratar os
  // dois casos igual mostra a posição de anteontem como se fosse a de ontem.
  const carga = b3.freshness.example;
  const faixa = $("quando");
  faixa.className = "quando" + (carga.utilizavel ? "" : " velho");
  faixa.innerHTML = "<span>Posição de <b>" +
    carga.data_referencia.split("-").reverse().join("/") + "</b></span><span>" +
    carga.explicacao + "</span>";

  $("aderencia").textContent = PCT(a.alignment) + " já serve";
  $("aderencia-txt").textContent =
    "De " + BRL(a.total_brl) + ", essa parte já está de acordo com o que a política declara " +
    "para o perfil " + perfil + ". É o resto que os dois planos tratam de forma diferente.";

  const fora = b.out_of_scope_brl / b.total_brl;
  barra("bar-hoje", [b.equity_before, 1 - b.equity_before - fora, fora]);
  barra("bar-alvo", [b.equity_budget, 1 - b.equity_budget, 0]);

  desenhaFgc(a);
  regua(perfil);
  planos(perfil, a, b);
}

/* --- o quanto a régua erra ---------------------------------------------
   Não é projeção de patrimônio, e a diferença é o produto inteiro. Todo
   janeiro a regra projeta uma faixa para o ano seguinte usando só o que se
   sabia até ali; depois o ano acontece e cai dentro ou fora. O que se publica
   é a contagem, não a promessa. */
function regua(perfil) {
  const c = DADOS.calibracao[perfil];
  if (!c) return;
  const host = $("regua");
  const dentro = c.cobertura.inside, total = c.cobertura.total;
  const vies = c.vies_pp;
  const otimista = vies < -0.5;

  host.innerHTML = "";
  host.append(el("h3", null, "O quanto esta régua erra"));
  host.append(el("p", null,
    "Todo janeiro a regra projeta uma faixa para os doze meses seguintes, usando só o " +
    "que se sabia até aquele dia. Depois o ano acontece. Em <b>" + total + " anos</b>, o " +
    "resultado caiu dentro da faixa em <b>" + dentro + "</b>."));
  host.append(el("p", null, otimista
    ? "E o meio da faixa ficou <b class='neg'>" + Math.abs(vies).toFixed(1).replace(".", ",") +
      " pontos otimista por ano</b>: a régua erra para o lado que favorece quem vende. " +
      "Está publicado aqui porque é o número que ninguém mostra."
    : (vies > 0.5
        ? "E o meio da faixa ficou <b>" + vies.toFixed(1).replace(".", ",") +
          " pontos abaixo</b> do que aconteceu: aqui a régua erra para o lado conservador."
        : "E o meio da faixa não puxou para lado nenhum de forma perceptível: o desvio " +
          "médio foi de " + Math.abs(vies).toFixed(1).replace(".", ",") + " ponto por ano.")));
  // Sem esta linha, "8 de 8" vira argumento de venda. Com oito observações e
  // erro padrão de catorze pontos, nenhuma contagem dessas se distingue de
  // acaso, e é justamente o perfil que acertou tudo que precisa dizer isso.
  const ep = Math.round((c.cobertura.standard_error || 0) * 100);
  host.append(el("p", null,
    c.nota
      ? "<b>A régua não mede este perfil.</b> " + c.nota
      : "<b>Oito anos é pouco.</b> A margem de erro é de " + ep + " pontos: acertar 6 ou 8 " +
        "não se distingue de sorte. Isto mede a régua, não promete resultado."));
  host.append(grafico(c.anos));
  const chaves = el("div", "chaves",
    "<span><i style='background:var(--line-strong)'></i>faixa projetada com dados anteriores ao ano</span>" +
    "<span><i style='background:var(--acao)'></i>o que aconteceu</span>" +
    "<span><i style='background:var(--neg)'></i>ficou fora da faixa</span>");
  host.append(chaves);
}


/* --- a carteira inteira --- */
// Três origens, uma lista só. Separar em três telas faria a pessoa somar de
// cabeça, e é justamente a soma que decide o plano.
//
// Valor ausente aparece como "?" e nunca como zero. Zero é uma resposta, e a
// diferença entre "vale zero" e "não sei quanto vale" é o que decide se o plano
// pode ser calculado. Enquanto houver "?", o total se declara parcial.
const acrescentados = [];
const valoresInformados = {};

function carteiraToda() {
  const daB3 = (b3.posicoes || []).map(p => Object.assign({}, p, {
    valor_brl: valoresInformados[p.nome] != null ? valoresInformados[p.nome] : p.valor_brl,
  }));
  return daB3.concat(acrescentados);
}

function desenhaCarteira() {
  const itens = carteiraToda();
  const host = $("lista-posicoes");
  host.innerHTML = "";

  itens.forEach((p, i) => {
    const linha = el("div", "pos");
    const temValor = p.valor_brl != null;
    linha.append(el("b", null, p.nome));
    const v = el("span", "val" + (temValor ? "" : " sem-valor"),
                 temValor ? BRL(p.valor_brl) : "R$ ?");
    linha.append(v);

    const de = el("span", "de");
    const detalhe = [p.tipo, p.origem];
    if (p.vencimento) detalhe.push("vence em " + p.vencimento.split("-").reverse().join("/"));
    if (p.emissor) detalhe.push(p.emissor);
    de.textContent = detalhe.join(" · ");

    if (!temValor) {
      de.append(document.createTextNode(". " + p.falta + ". "));
      const b = el("button", "pos-acao", "Informar o valor");
      b.type = "button";
      b.onclick = () => pedeValor(p.nome);
      de.append(b);
    } else if (p.origem === "informado por você") {
      de.append(document.createTextNode(". "));
      const b = el("button", "pos-acao", "Remover");
      b.type = "button";
      b.onclick = () => { acrescentados.splice(acrescentados.indexOf(p), 1); desenhaCarteira(); };
      de.append(b);
    }
    linha.append(de);
    host.append(linha);
  });

  const comValor = itens.filter(p => p.valor_brl != null);
  const sem = itens.filter(p => p.valor_brl == null);
  const total = comValor.reduce((s, p) => s + p.valor_brl, 0);
  $("total-carteira").innerHTML =
    "<span>" + (sem.length ? "Total do que já tem valor" : "Total") + "</span>" +
    "<span>" + BRL(total) + "</span>";

  const aviso = $("sem-valor");
  if (sem.length) {
    aviso.classList.remove("hidden");
    aviso.innerHTML = "<p><b>" + sem.length + " posição(ões) sem valor.</b> O total é " +
      "parcial, e toda porcentagem sobre o patrimônio sai baixa: " +
      sem.map(p => escapa(p.nome)).join(", ") + ".</p>";
  } else {
    aviso.classList.add("hidden");
  }
}

function pedeValor(nome) {
  const bruto = prompt("Quanto vale " + nome + " hoje, em reais?");
  if (bruto == null) return;
  const v = leValor(bruto);
  if (!isFinite(v) || v < 0) { alert("Valor não reconhecido. Use algo como 25.000,00"); return; }
  valoresInformados[nome] = v;
  desenhaCarteira();
  if (perfilAtual) render(perfilAtual);
}

/* --- o limite do FGC, inteiro --- */
// Havia meia conta aqui: so o teto de 250 mil por conglomerado, so o primeiro
// estouro na tela, e o limite lido de um numero escrito na frase. Faltavam
// duas coisas que mudam a resposta.
//
// A primeira e o teto movel de um milhao por CPF em quatro anos. Ele e o total
// que o FGC paga a uma pessoa somando todas as instituicoes na janela, entao
// espalhar tres milhoes por quinze bancos, cada um abaixo de 250 mil, nao deixa
// os tres milhoes garantidos: deixa um milhao. Quem so olha o teto por emissor
// nunca ve isso.
//
// A segunda e que o que a pessoa acrescenta a mao nao entrava na conta. Os
// papeis que mais dependem do FGC sao justamente CDB, LCI e LCA, que a B3 nao
// manda e que ela digita, e eles eram invisiveis para o unico aviso que
// existia sobre eles.
function exposicaoPorConglomerado(a) {
  const soma = {};
  const junta = (nome, valor) => {
    if (!nome || !(valor > 0)) return;
    soma[nome] = (soma[nome] || 0) + valor;
  };
  Object.entries(a.fgc_exposure || a.fgc_breaches || {}).forEach(([n, v]) => junta(n, v));
  acrescentados.forEach(item => {
    if (item.regua && item.regua.fgc) junta(item.conglomerado || item.emissor, item.valor_brl);
  });
  return soma;
}

function desenhaFgc(a) {
  const caixa = $("fgc");
  const limites = DADOS.renda_fixa.motor.fgc;
  const porConglomerado = exposicaoPorConglomerado(a);
  const r = resumoFgc(porConglomerado, limites);

  if (!r.estouros.length && !r.acima_do_teto_movel) { caixa.style.display = "none"; return; }
  caixa.style.display = "block";

  const partes = [];
  if (r.estouros.length) {
    const linhas = r.estouros.map(n => "<li>" + escapa(n) + ": " + BRL(porConglomerado[n]) +
      ", sendo " + BRL(porConglomerado[n] - limites.por_conglomerado_brl) + " a descoberto</li>");
    partes.push("<p><b>" + BRL(r.excedente_por_emissor) + " acima do teto por emissor.</b> " +
      "A garantia cobre " + BRL(limites.por_conglomerado_brl) + " por CPF em cada " +
      "conglomerado.</p><ul>" + linhas.join("") + "</ul>");
  }
  if (r.acima_do_teto_movel) {
    partes.push("<p><b>" + BRL(r.excedente_movel) + " além do teto de quatro anos.</b> " +
      "Somando o que cabe em cada emissor dá " + BRL(r.coberto) + ", e o FGC paga no máximo " +
      BRL(limites.teto_movel_brl) + " por CPF em " + limites.janela_anos + " anos, " +
      "por mais bancos que sejam. Dividir em mais emissores não levanta esse teto.</p>");
  }
  partes.push("<p>Os dois planos mantêm a posição: é risco assumido, e assumir precisa " +
    "ser decisão.</p>");
  caixa.innerHTML = partes.join("");
}

__REGUA_RF__

const TIPOS_RF = ["CDB", "LCI", "LCA", "LC", "RDB"];

function mostraCamposRF() {
  const eRF = TIPOS_RF.indexOf($("add-tipo").value) >= 0;
  $("add-rf").classList.toggle("hidden", !eRF);
  if (!eRF) $("add-regua").classList.add("hidden");
}

// A pessoa digita 110 para "110% do CDI" e 1,2 para "CDI mais 1,2%". Os dois
// sao percentuais na tela e fracao na conta, e por isso a leitura e a mesma.
// O que muda entre eles e o significado, e quem decide isso e brutoAoAno.
function leTaxa(texto) {
  const bruto = leValor(texto);
  return isFinite(bruto) && bruto > 0 ? bruto / 100 : NaN;
}

$("add-tipo").onchange = mostraCamposRF;
mostraCamposRF();

$("add-botao").onclick = () => {
  const nome = $("add-nome").value.trim();
  const valor = leValor($("add-valor").value);
  const tipo = $("add-tipo").value;
  const erro = $("add-erro");
  const diz = m => { erro.textContent = m; erro.classList.remove("hidden"); };
  if (!nome) { diz("Escreva o que é."); return; }
  if (!isFinite(valor) || valor <= 0) { diz("Escreva quanto vale, como 25.000,00."); return; }

  const item = { nome: nome, tipo: tipo, origem: "informado por você", valor_brl: valor,
                 quantidade: null, vencimento: null, emissor: null,
                 completa: true, falta: "" };

  if (TIPOS_RF.indexOf(tipo) >= 0) {
    const emissor = $("add-emissor").value.trim();
    const taxa = leTaxa($("add-taxa").value);
    const venc = $("add-venc").value;
    if (!emissor) { diz("Escreva quem emite. É o que decide o limite do FGC."); return; }
    if (!isFinite(taxa)) { diz("Escreva a taxa, como 110 para 110% do CDI."); return; }
    if (!venc) { diz("Escreva o vencimento. Sem ele não dá para saber o imposto."); return; }
    item.emissor = emissor;
    item.conglomerado = emissor;
    item.indice = $("add-indice").value;
    item.taxa = taxa;
    item.vencimento = venc;
    const r = liquidoAoAno(item, DADOS.renda_fixa.referencia);
    if (!r) { diz("O vencimento precisa ser depois de hoje."); return; }
    item.regua = r;
  }

  erro.classList.add("hidden");
  acrescentados.push(item);
  $("add-nome").value = ""; $("add-valor").value = "";
  $("add-emissor").value = ""; $("add-taxa").value = ""; $("add-venc").value = "";
  mostraRegua(item);
  desenhaCarteira();
  // O aviso do FGC é desenhado junto do plano, e um papel acrescentado depois
  // dele deixava o aviso velho na tela: a pessoa somava trezentos mil num banco
  // que já tinha duzentos e não via nada mudar. Redesenhar o plano inteiro é o
  // que o resto da tela já faz quando a carteira muda.
  if (perfilAtual) render(perfilAtual);
};

// O que o papel rende na mesma unidade que todo o resto, e contra o piso.
function mostraRegua(item) {
  const caixa = $("add-regua");
  if (!item.regua) { caixa.classList.add("hidden"); return; }
  const r = item.regua;
  const piso = pisoLiquido(item.vencimento, DADOS.renda_fixa.referencia);
  const diferenca = piso ? (r.liquido - piso.liquido) * 100 : null;
  const veredito = diferenca === null ? ""
    : diferenca >= 0
      ? "<p>Rende <b>" + diferenca.toFixed(2).replace(".", ",") + " ponto</b> ao ano acima do "
        + "Tesouro Selic no mesmo prazo. É o que este papel paga pelo risco de crédito e "
        + "pela carência.</p>"
      : "<p>Rende <b>" + Math.abs(diferenca).toFixed(2).replace(".", ",") + " ponto</b> ao ano "
        + "abaixo do Tesouro Selic no mesmo prazo, que tem liquidez diária e não tem risco de "
        + "crédito. A oferta está cobrando risco sem pagar por ele.</p>";
  caixa.innerHTML = "<p><b>" + escapa(item.nome) + "</b> rende <b>" + PCT(r.liquido) +
    "</b> líquido ao ano, que é <b>" + PCT(r.sobre_cdi) + " do CDI</b>." +
    (r.ir ? " O imposto no prazo é de " + PCT(r.ir) + "." : " É isento de imposto de renda.") +
    "</p>" + veredito +
    "<p class='ajuda'>" + (r.fgc ? "Coberto pelo FGC, dentro dos limites abaixo."
                                 : "Sem cobertura do FGC.") +
    " Régua com CDI a " + PCT(DADOS.renda_fixa.cdi_anual) + " ao ano" +
    (item.indice === "ipca" ? " e IPCA a " + PCT(DADOS.renda_fixa.ipca_anual) + ", premissa declarada" : "") +
    ". Não é recomendação.</p>";
  caixa.classList.remove("hidden");
}


/* --- alertas de mudança na estratégia --- */
// Só aparece para quem escolheu adequar, ou seja, para quem está copiando a
// política. Quem escolheu manter a própria carteira não recebe alerta de uma
// estratégia que ele não segue: seria ruído com aparência de instrução.
//
// O alerta diz o que aconteceu e o que isso pede da carteira dele, em reais,
// porque "a camada reduziu para 55%" não é acionável e "venda R$ 12.600 de
// ações" é.
function alertas(perfil, chave) {
  const m = DADOS.mudancas && DADOS.mudancas.perfis ? DADOS.mudancas.perfis[perfil] : null;
  if (chave !== "adequar" || !m) { esconde("alertas-sec"); return; }
  mostra("alertas-sec");

  const host = $("alertas");
  host.innerHTML = "";
  const tudo = carteiraToda();
  const patrimonio = tudo.reduce((s, p) => s + (p.valor_brl || 0), 0);
  // Quantas linhas ainda não têm valor. O número em reais abaixo sai deste
  // patrimônio, então enquanto faltar posição ele é piso, não valor final, e a
  // tela precisa dizer isso no mesmo parágrafo em que dá a ordem de grandeza.
  const semValor = tudo.filter(p => p.valor_brl == null).length;

  if (!m.changes.length) {
    $("alertas-lede").textContent =
      "Nada mudou na política desde o registro. Se algo mudar, aparece aqui.";
    return;
  }
  $("alertas-lede").textContent =
    "Você escolheu seguir a política. Quando ela se mexe, a sua carteira precisa " +
    "acompanhar, e é isto que mudou até agora.";

  m.changes.forEach(c => {
    const caixa = el("div", "alerta");
    caixa.append(el("p", "quando", c.date.split("-").reverse().join("/")));
    const p1 = el("p");
    p1.innerHTML = "A camada de proteção entrou: " + c.why + ", no fechamento de " +
      c.observed_on.split("-").reverse().join("/") + ". Cada ação passou a valer <b>" +
      Math.round(c.factor * 100) + "%</b> do peso de janeiro.";
    caixa.append(p1);

    const p2 = el("p");
    const saiu = c.from_equity - c.to_equity;
    p2.innerHTML = "Na sua carteira: vender <b>" + BRL(patrimonio * saiu) + "</b> em ações " +
      "para o CDI, na mesma proporção. A parte em S&P 500 fica." +
      (semValor ? " Piso, porque " + semValor + " posição(ões) sem valor ficam fora da conta."
                : "");
    caixa.append(p2);
    host.append(caixa);
  });
}

/* --- acompanhar --- */
// A faixa foi calculada no primeiro pregão do ano e não se mexe. Se ela se
// ajustasse ao que foi acontecendo, nunca erraria, e uma faixa que nunca erra
// não mede nada. O que anda é a linha do realizado.
//
// A comparação é por pregão decorrido, não por data: em agosto o realizado é
// comparado com a faixa de agosto. Comparar meio ano com a faixa do ano
// inteiro faria a carteira parecer atrasada só porque o ano não acabou.
function acompanhar(perfil) {
  const ac = DADOS.acompanhamento;
  const r = ac.perfis[perfil];
  if (!r) { esconde("acompanhar-sec"); return; }
  mostra("acompanhar-sec");
  etapa(3);

  const n = r.agora;
  $("ac-quando").textContent = n.sessions + " pregões de " + ac.ano +
    " · até " + n.date.split("-").reverse().join("/");
  $("ac-numero").textContent = PCT(n.realised);
  $("ac-numero").className = "big num" + (n.realised < 0 ? " neg" : "");
  // Nenhuma faixa foi projetada em janeiro. Todas foram desenhadas em agosto com
  // dados anteriores ao ano, e a tela dizia "projetada em janeiro" para três
  // delas porque o payload afirmava isso a partir de um literal. Agora a data
  // vem do artefato e a frase vem da data.
  const quando = r.faixa_de_janeiro ? "projetada antes do ano"
    : "desenhada em " + r.faixa_desenhada.split("-").reverse().join("/") + ", com dados anteriores a " + ac.ano;
  $("ac-frase").innerHTML = "Para este ponto do ano, a faixa " + quando + " vai de <b>" +
    PCT(n.p10) + "</b> a <b>" + PCT(n.p90) + "</b>. O resultado está <b>" +
    (n.inside ? "dentro" : "fora") + "</b> dela.";
  $("ac-grafico").innerHTML = cone(r.faixa, r.realizado);
  $("ac-legenda").textContent = r.faixa_de_janeiro
    ? "Área: o projetado antes do ano. Linha: o que aconteceu."
    : "Área: o projetado para o ano, com dados anteriores a ele. Linha: o que aconteceu. Toda a série de 2026 é reconstrução.";
  $("ac-limite").innerHTML = "<p>" + (r.faixa_de_janeiro ? ac.limitacao : ac.limitacao_tardia) + "</p>";
}

function cone(faixaBruta, realizado) {
  // No primeiro pregão o retorno acumulado é zero por definição, e a faixa tem
  // largura zero junto. Sem esse ponto o desenho começa no pregão cinco e a
  // linha aparece solta à esquerda da área, como se estivesse fora dela.
  const faixa = [{ sessions: 0, p10: 0, p50: 0, p90: 0 }].concat(faixaBruta);
  const W = 320, H = 140, T = 10, B = 18, L = 4, R = 4;
  const maxS = faixa[faixa.length - 1].sessions;
  const baixo = Math.min(...faixa.map(p => p.p10), ...realizado.map(p => p.r));
  const alto = Math.max(...faixa.map(p => p.p90), ...realizado.map(p => p.r));
  const folga = (alto - baixo) * 0.08 || 0.01;
  const min = baixo - folga, max = alto + folga;
  const x = s => L + (W - L - R) * (s / maxS);
  const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));

  // A faixa é um polígono só: o contorno de cima na ida, o de baixo na volta.
  const area = faixa.map(p => x(p.sessions) + "," + y(p.p90)).join(" ") + " " +
    faixa.slice().reverse().map(p => x(p.sessions) + "," + y(p.p10)).join(" ");
  const linha = realizado.map(p => x(p.sessions) + "," + y(p.r)).join(" ");
  const fim = realizado[realizado.length - 1];

  return "<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
    "A faixa projetada para o ano e o retorno acumulado até agora, por pregão decorrido.'>" +
    "<polygon points='" + area + "' fill='var(--acao-fraco)'/>" +
    "<polyline points='" + linha + "' fill='none' stroke='var(--acao)' stroke-width='2' " +
      "stroke-linejoin='round' stroke-linecap='round'/>" +
    "<circle cx='" + x(fim.sessions) + "' cy='" + y(fim.r) + "' r='4' fill='var(--acao)' " +
      "stroke='var(--canvas)' stroke-width='2'/>" +
    "<text x='" + x(0) + "' y='" + (H - 5) + "' font-size='9' fill='var(--fg-2)'>janeiro</text>" +
    "<text x='" + x(maxS) + "' y='" + (H - 5) + "' font-size='9' fill='var(--fg-2)' " +
      "text-anchor='end'>fim do ano</text></svg>";
}

function grafico(anos) {
  const L = 8, R = 8, T = 12, B = 22, W = 320, H = 132;
  const baixo = Math.min(...anos.map(a => Math.min(a.p10, a.realised)));
  const alto = Math.max(...anos.map(a => Math.max(a.p90, a.realised)));
  const folga = (alto - baixo) * 0.08;
  const min = baixo - folga, max = alto + folga;
  const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));
  const passo = (W - L - R) / anos.length;
  const x = i => L + passo * (i + 0.5);

  const svg = ["<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
    "Para cada ano, a faixa projetada em janeiro e o retorno que de fato aconteceu.'>"];
  // O eixo de porcentagem, a linha do zero e o traço da mediana saíram. O
  // gráfico responde uma pergunta só, o resultado caiu dentro do que foi
  // projetado?, e nenhum dos três ajudava a responder.
  anos.forEach((a, i) => {
    const cx = x(i);
    svg.push("<line x1='" + cx + "' x2='" + cx + "' y1='" + y(a.p10) + "' y2='" + y(a.p90) +
      "' stroke='var(--acao-fraco)' stroke-width='9' stroke-linecap='round'/>");
    // Anel na cor do fundo: sem ele o ponto tem contraste 1,0 contra a barra no
    // tema escuro, ou seja, some justamente quando cai dentro da faixa, que é
    // o caso comum e o que o gráfico existe para mostrar.
    svg.push("<circle cx='" + cx + "' cy='" + y(a.realised) + "' r='4' fill='" +
      (a.inside ? "var(--acao)" : "var(--neg)") +
      "' stroke='var(--canvas)' stroke-width='2'/>");
    svg.push("<text x='" + cx + "' y='" + (H - 6) + "' text-anchor='middle' font-size='9' " +
      "fill='var(--fg-2)'>" + String(a.year).slice(2) + "</text>");
  });
  svg.push("</svg>");

  const fig = el("figure");
  fig.innerHTML = svg.join("") +
    "<figcaption>Cada barra é a faixa de 80% projetada em janeiro daquele ano, com o " +
    "traço no meio. O ponto é o retorno que aconteceu.</figcaption>";
  return fig;
}

function barra(id, partes) {
  // Cada faixa carrega o próprio par de cores, e não uma cor de texto só para
  // todas. O rótulo era var(--canvas), "o oposto do fundo da página", o que
  // funcionava no escuro e reprovava no claro: branco sobre a faixa neutra dava
  // 1,91 de contraste, e o número sumia dentro da barra. Medidos, claro e
  // escuro: 5,35 e 10,66 na faixa de ações, 10,37 e 9,59 na neutra, 5,31 e
  // 7,13 na de perda.
  const faixas = [
    ["var(--acao-vivo)", "var(--acao-vivo-fg)"],
    ["var(--line-strong)", "var(--fg)"],
    ["var(--neg)", "var(--canvas)"],
  ];
  const host = $(id);
  host.innerHTML = "";
  host.style.cssText = "display:flex;height:2rem;overflow:hidden;gap:1px";
  partes.forEach((v, i) => {
    if (v <= 0.001) return;
    const s = el("div");
    s.style.cssText = "flex:" + v + ";background:" + faixas[i][0] +
      ";display:grid;place-items:center;font-size:12px;color:" + faixas[i][1];
    s.className = "num";
    s.textContent = v > 0.09 ? PCT(v, 0) : "";
    s.title = PCT(v);
    host.append(s);
  });
}

/* --- os dois planos --- */
function planos(perfil, a, b) {
  const host = $("planos");
  host.innerHTML = "";
  [["adequar", a], ["adaptar", b]].forEach(([chave, m]) => {
    const d = el("button", "plano");
    d.type = "button";
    d.setAttribute("aria-pressed", "false");
    d.append(
      el("h3", null, m.path_label),
      el("div", "custo num", BRL(m.transition_total_brl) +
        "<small>" + (m.tax_is_complete ? "custo total" : "custo já calculado") + " · " +
        (m.transition_cost_pct < 0.0001 ? "menos de 0,01%" : PCT(m.transition_cost_pct, 2)) +
        " do patrimônio</small>"),
      el("dl", null,
        "<dt>Movimenta</dt><dd class='num'>" + BRL(m.turnover_brl) + "</dd>" +
        "<dt>Imposto</dt><dd class='num'>" + BRL(m.transition_tax_brl) + "</dd>"));
    // Em vez de um "a partir de" que ninguém decifra, a falta é dita por
    // extenso: o que falta, de quanto é, e por quê.
    if (!m.tax_is_complete) {
      d.append(el("div", "falta",
        "<b>Ainda falta o imposto de " + m.positions_without_cost_basis.map(p => p.ticker).join(", ") +
        // Sem "e só aumenta": um ganho eleva o imposto, um prejuízo abate o das
      // outras vendas da mesma cesta. Só dá para afirmar a direção quem sabe o
      // custo, que é justamente o que falta.
      "</b>" + BRL(m.unpriced_sale_brl) + " vão ser vendidos e a B3 não informou por quanto " +
        "você comprou. Esse imposto entra na conta quando você informar o valor."));
    }
    d.append(el("div", "selo " + (m.track_record_applies ? "" : "nao"),
      m.track_record_applies
        ? "O resultado que publicamos foi medido nesta carteira"
        : "O resultado que publicamos NÃO foi medido nesta carteira"));
    d.onclick = () => {
      host.querySelectorAll(".plano").forEach(x => x.setAttribute("aria-pressed", "false"));
      d.setAttribute("aria-pressed", "true");
      planoAtual = chave;
      razao(perfil, chave, true);
    };
    host.append(d);
    if (planoAtual === chave) { d.setAttribute("aria-pressed", "true"); razao(perfil, chave, false); }
  });
}

/* --- o que muda no plano escolhido --- */
// O que a tela entrega ao gerador do dossiê: respostas, custos declarados e a
// escolha. Nenhum número atravessa, o gerador refaz as contas com o mesmo
// módulo, e é isso que impede o PDF de discordar da tela por acidente.
function registroDaDecisao(perfil, chave) {
  const respostasBrutas = {};
  escolha.forEach(q => { respostasBrutas[q.key] = respostas[q.key].value; });
  return {
    schema: "benevente_plan_record_v1",
    decided_at: new Date().toISOString(),
    client: "",
    answers: respostasBrutas,
    profile: perfil,
    declared_costs: Object.fromEntries(
      Object.entries(custosInformados).map(([t, v]) => [t, Math.round(v * 100) / 100])),
    chosen_path: chave,
  };
}

function razao(perfil, chave, rolar) {
  const m = resolvido(DADOS.profiles[perfil][chave]);
  const outro = resolvido(DADOS.profiles[perfil][chave === "adequar" ? "adaptar" : "adequar"]);
  mostra("razao-sec");
  etapa(3);
  $("razao-h").textContent = m.path_label;
  $("razao-lede").textContent = m.honesty;

  const grupos = [["vender", "Sai"], ["reduzir", "Reduz"], ["comprar", "Entra"], ["manter", "Fica"]];
  const host = $("razao");
  host.innerHTML = "";
  const plural = { vender: "saem", reduzir: "diminuem", comprar: "entram", manter: "ficam" };
  const contagem = grupos
    .map(([a]) => [plural[a], m.moves.filter(x => x.action === a).length])
    .filter(([, n]) => n > 0);
  $("razao-resumo").innerHTML = "<b>" + contagem.reduce((s, [, n]) => s + n, 0) +
    " ativos</b> · " + contagem.map(([rot, n]) => n + " " + rot).join(", ");
  grupos.forEach(([acao, titulo]) => {
    const linhas = m.moves.filter(x => x.action === acao);
    if (!linhas.length) return;
    host.append(el("p", "grupo", titulo + " · " + linhas.length));
    linhas.forEach(x => {
      const r = el("div", "linha");
      const delta = x.delta_brl;
      r.append(
        el("b", null, x.ticker),
        el("div", "val num" + (delta < 0 ? " neg" : ""),
          (delta === 0 ? BRL(x.from_brl) : (delta > 0 ? "+" : "−") + BRL(Math.abs(delta))) +
          "<small>" + BRL(x.from_brl) + " para " + BRL(x.to_brl) + "</small>"),
        // O motivo primeiro: é ele que responde "por que essa linha existe". A
        // nota vem depois porque é consequência, não causa.
        el("div", "porque", x.reason + (x.notes && x.notes.length ? " · " + x.notes[0] : "")));
      host.append(r);
    });
  });

  const conta = $("conta");
  let html = "<div><span>Execução</span><span class='num'>" +
    BRL(m.transition_cost_brl) + "</span></div>";
  Object.entries(m.tax_by_bucket).forEach(([cesta, d]) => {
    const nome = { renda_variavel: "Ações e fundos", renda_fixa: "Renda fixa",
                   fora_do_escopo: "Fora da estratégia" }[cesta] || cesta;
    // Prejuízo não é base de imposto, é crédito, mas só dentro da própria
    // cesta. O prejuízo de cripto não abate imposto de ação, e prometer isso
    // aqui contradiria a regra que o módulo implementa três telas atrás.
    const rotulo = d.realised_gain_brl >= 0
      ? nome + " · imposto sobre " + BRL(d.realised_gain_brl) + " de ganho"
      : cesta === "fora_do_escopo"
        ? nome + " · prejuízo de " + BRL(-d.realised_gain_brl) + ", que se apura à parte"
        : nome + " · prejuízo de " + BRL(-d.realised_gain_brl) + ", que vira crédito neste tipo";
    html += "<div><span>" + rotulo + "</span><span class='num'>" + BRL(d.tax_brl) + "</span></div>";
  });
  if (!m.tax_is_complete) {
    html += "<div><span class='neg'>Imposto de " +
      m.positions_without_cost_basis.map(p => p.ticker).join(", ") + ", sobre " +
      BRL(m.unpriced_sale_brl) + " vendidos</span>" +
      "<span class='num neg'>ainda sem calcular</span></div>";
  }
  html += "<div class='total'><span>" +
    (m.tax_is_complete ? "Total, pago uma vez" : "Calculado até aqui, pago uma vez") +
    "</span><span class='num'>" + BRL(m.transition_total_brl) + "</span></div>";
  html += "<p>Ganho e prejuízo se compensam dentro do mesmo tipo de investimento, nunca " +
    "entre tipos." +
    (m.exempt_month_assumed && (m.tax_by_bucket.renda_variavel || {}).realised_gain_brl > 0
      ? " Ações ficam em zero pela isenção de R$ 20 mil no mês. Outra venda no mesmo mês " +
        "derruba a isenção."
      : "") +
    (m.tax_by_bucket.fora_do_escopo
      ? " O zero em Fora da estratégia não é isenção, é conta que não fazemos aqui, " +
        "porque cripto tem regras próprias."
      : "") +
    " O outro plano custaria " + BRL(outro.transition_total_brl) + ".</p>";
  conta.innerHTML = html;

  const caixa = $("registro");
  caixa.classList.add("hidden");
  $("gerar").onclick = () => {
    // O visualizador bloqueia download iniciado pela página, então o protótipo
    // mostra o que seria enviado em vez de fingir um arquivo que não desce.
    caixa.classList.remove("hidden");
    caixa.innerHTML = "";
    const texto = el("p", null,
      "Este é o registro da sua decisão. No app ele vai para o servidor, que " +
      "refaz as contas e devolve o PDF assinável. Aqui ele aparece para você ver " +
      "o que seria enviado: só respostas e escolhas, nenhum número calculado.");
    const pre = el("pre");
    pre.textContent = JSON.stringify(registroDaDecisao(perfil, chave), null, 2);
    caixa.append(texto, pre);
    rolaPara(caixa, "nearest");
  };

  alertas(perfil, chave);
  acompanhar(perfil);
  if (rolar) rolaPara($("razao-sec"), "start");
}
</script>
"""


#: O site tem CSP com ``script-src 'self'``: script embutido é bloqueado. Por
#: isso a versão publicada separa o JavaScript num arquivo, enquanto o artefato
#: continua num documento só. Mesma fonte, dois empacotamentos.
SITE_HTML = ROOT / "web" / "app.html"
SITE_JS = ROOT / "web" / "plano.js"
SITE_CSS = ROOT / "web" / "plano.css"

#: Trava de conveniência, não de segurança. O conteúdo é sintético e a
#: comparação roda no navegador, qualquer pessoa que abra o código passa. Serve
#: para o visitante casual não cair numa tela inacabada, e nada além disso.
SENHA_SHA256 = "4c073be62dd2eeca3d94f45932aef78e01d815664e90d0144b7ed10978f8b801"

#: Desligada em 31/08/2026, a pedido, para testar sem atrito. O código dela fica
#: aqui inteiro: religar é trocar esta linha para ``True``.
#:
#: O que a deixa desligável é a carteira ser sintética. Ela nunca protegeu dado
#: de ninguém, e não é o que vai proteger: antes de qualquer dado real de
#: cliente entrar nesta tela, o que precisa existir é autenticação no servidor,
#: não uma comparação de hash no navegador. Um teste recusa a combinação de
#: trava desligada com página que não se declara protótipo de dado sintético.
TRAVA_LIGADA = False

CABECALHO_SITE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="Protótipo do aplicativo da Benevente: conecta a B3, quatro perguntas e dois planos. Dados sintéticos.">
<link rel="canonical" href="https://benevente.dgo.fi/app">
"""

TRAVA = """
<div class="wrap" id="trava">
  <header>
    <div class="topo"><p class="marca"><svg class="marca-b" viewBox="0 0 64 64" aria-hidden="true"><rect width="64" height="64" rx="16" fill="#102a43"/><path d="M19 48V16h15.5c8.7 0 14 3.4 14 9.9 0 4.1-2.4 7.1-6.3 8.3 4.8 1.1 7.8 4.2 7.8 8.8C50 49.7 44.4 52 35.4 52H19zm9-19.5h6.6c3.5 0 5.4-1.3 5.4-3.8 0-2.4-1.9-3.6-5.4-3.6H28v7.4zm0 16.2h7.8c3.7 0 5.6-1.4 5.6-4.1 0-2.8-1.9-4.1-5.6-4.1H28v8.2z" fill="#f7fbf8"/></svg>Benevente <span>· protótipo</span></p></div>
    <h1>Protótipo do aplicativo</h1>
    <p>Página de teste, com carteira sintética. Não indexada e ainda em construção.</p>
  </header>
  <label class="label" for="senha">Senha de acesso</label>
  <div class="campo" style="margin-top:.5rem">
    <input id="senha" type="password" autocomplete="off" placeholder="senha">
    <button class="btn" type="button" id="entrar">Entrar</button>
  </div>
  <p class="ajuda" id="trava-erro"></p>
  <p style="margin-top:2rem"><a class="link" href="./index.html">Voltar ao site</a></p>
</div>
"""


def _partes(pagina: str) -> tuple[str, str]:
    """Separa o documento em (marcação, javascript)."""
    i = pagina.index("<script>")
    j = pagina.index("</script>", i)
    return pagina[:i], pagina[i + len("<script>"):j]


def main() -> None:
    dados = json.loads(SOURCE.read_text(encoding="utf-8"))
    conexao = json.loads(CONEXAO.read_text(encoding="utf-8"))
    calibracao = json.loads(CALIBRACAO.read_text(encoding="utf-8"))
    tesouro = json.loads(OFERTAS_TESOURO.read_text(encoding="utf-8"))
    acompanhamento = json.loads(ACOMPANHAMENTO.read_text(encoding="utf-8"))
    mudancas = json.loads(MUDANCAS.read_text(encoding="utf-8"))
    magro = {
        "questionnaire": dados["questionnaire"],
        # ``modules`` sai daqui: o app nunca o usou, e ele carregava para dentro
        # do documento as duas palavras que a tela evita de propósito.
        "profiles": {nome: {caminho: {k: v for k, v in p[caminho].items() if k != "modules"}
                            for caminho in ("adequar", "adaptar")}
                     for nome, p in dados["profiles"].items()},
        "b3": {"base_starts": conexao["base_starts"], "coverage": conexao["coverage"],
               "freshness": conexao["freshness"],
               "consent": {k: v for k, v in conexao["consent"].items()
                           if k in ("escopo", "revogavel_em", "credencial_armazenada")},
               "cost_basis": conexao["cost_basis"], "gaps": conexao["gaps"],
               # A carteira inteira, com a procedência de cada linha. Sem ela a
               # tela mostrava só o agregado e prometia no texto uma origem por
               # posição que não exibia.
               "posicoes": conexao["posicoes"], "consolidado": conexao["consolidado"]},
        # O que a política mudou no ano. Quem copia a estratégia precisa saber
        # que ela se mexeu, e o que isso pede da carteira dele.
        "mudancas": {"ano": mudancas["year"],
                     "perfis": {k: {"changes": v["changes"], "now": v["now"]}
                                for k, v in mudancas["profiles"].items()}},
        # Calibração: o que se publica não é a projeção, é o quanto ela erra.
        "calibracao": {
            perfil: {"anos": [{k: dados[k] for k in ("year", "p10", "p50", "p90",
                                                     "realised", "inside")}
                              for dados in r["years"]],
                     "cobertura": r["coverage"],
                     "vies_pp": r["median_bias_pp"],
                     # A mesma função do publicador do site: a explicação de
                     # por que a régua não vale para um perfil não pode
                     # existir em duas versões que divergem.
                     "nota": nota_do_instrumento(perfil, r)}
            for perfil, r in calibracao["profiles"].items()
        },
        # A régua de renda fixa. A pessoa digita a oferta que viu na corretora e
        # a conta roda no navegador, porque esperar servidor para comparar dois
        # números seria pior que não comparar. As tabelas viajam prontas daqui,
        # de fixed_income_catalog, e um teste roda a versão Python e a do
        # navegador sobre a mesma grade para elas não se separarem.
        #
        # O piso é o Tesouro Selic de prazo mais curto: liquidez diária, sem
        # risco de crédito, e já com a custódia descontada. Uma oferta de banco
        # que não bate esse piso está cobrando risco e prazo sem pagar por eles.
        "renda_fixa": {
            "motor": motor_para_navegador(),
            "cdi_anual": tesouro["selic_annual_used"],
            # O IPCA aqui só serve para trazer papel indexado à mesma unidade. É
            # premissa declarada, não projeção da casa, e aparece na tela como tal.
            "ipca_anual": 0.045,
            "referencia": tesouro["reference_date"],
            "piso": min((x for x in tesouro["products"] if x["index"] == "Selic"),
                        key=lambda x: x["maturity"]),
        },
        # O ano corrente. A faixa vem congelada de janeiro; o realizado, do
        # acompanhamento diário. O artefato é um documento só, então os dois
        # vêm embutidos, e o realizado entra de cinco em cinco pregões: entre
        # um pregão e o vizinho a linha não muda o suficiente para se enxergar,
        # e a versão cheia dobraria o tamanho do arquivo.
        "acompanhamento": {
            "ano": acompanhamento["year"],
            "limitacao": acompanhamento["limitation"],
            # A ressalva de quem foi declarado com o ano em curso é outra, e o
            # rodapé da tela dizia "calculada em janeiro" para ele também.
            "limitacao_tardia": acompanhamento["late_band"]["limitation"],
            "perfis": {
                perfil: {
                    "faixa": r["band"],
                    # Se a faixa foi declarada antes do ano ou desenhada depois
                    # que o degrau passou a existir. A tela dizia "projetada em
                    # janeiro" para todos, e para o degrau declarado em agosto
                    # isso seria falso.
                    "faixa_de_janeiro": r["band_declared_before_year"],
                    "faixa_desenhada": r["band_drawn_on"],
                    "realizado": [x for i, x in enumerate(r["realised"])
                                  if i % 5 == 0 or i == len(r["realised"]) - 1],
                    "agora": r["now"],
                }
                for perfil, r in acompanhamento["profiles"].items()
            },
        },
    }
    # O artefato precisa ser um documento so, entao recebe os tokens embutidos.
    # A versao do site le web/tokens.css, o mesmo arquivo que as paginas usam, # e os dois saem de tools/design_tokens.py, que e a fonte unica.
    pagina = (HTML.replace("__DADOS__", json.dumps(magro, ensure_ascii=False,
                                                   separators=(",", ":")))
                  .replace("__REGUA_RF__", REGUA_RF_JS)
                  # O rodapé nomeava a tipografia à mão e nomeava a errada. Sai
                  # das mesmas constantes que a folha de estilo usa.
                  .replace("__TIPOGRAFIA__", f"Tipografia {_familia(SANS)} e {_familia(MONO)}.")
                  .replace("__FONTES__", "\n".join((FONTES_LINK, ANALITICA_LINK)))
                  .replace("__TOKENS__", tokens_css(com_cabecalho=False)))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(pagina, encoding="utf-8", newline="\n")

    # --- versão do site: mesmo conteúdo, script fora do documento ---
    marcacao, script = _partes(pagina)
    # No site o bloco embutido da lugar ao <link>: uma fonte, um arquivo.
    marcacao = marcacao.replace(tokens_css(com_cabecalho=False),
                                "/* tokens em ./tokens.css */")
    # O artefato declara charset e viewport porque e aberto como arquivo solto,
    # sem invólucro nenhum, sem o charset o navegador chuta windows-1252 e todo
    # acento aparece quebrado. No site, CABECALHO_SITE ja os declara, e duas
    # declaracoes no mesmo documento so confundem quem for ler.
    for meta in ('<meta charset="utf-8">\n',
                 '<meta name="viewport" content="width=device-width, initial-scale=1">\n'):
        marcacao = marcacao.replace(meta, "", 1)
    # A marcação da trava sai junto com o script dela. Deixar o campo de senha
    # na página sem o código que o lê seria o pior dos dois estados: parece
    # quebrado e ainda convida alguém a digitar uma senha num campo inerte.
    corpo = (marcacao.replace('<div class="wrap">', TRAVA + '<div class="wrap hidden" id="app">', 1)
             if TRAVA_LIGADA else marcacao)
    # A folha do app sai do documento pelo mesmo motivo que o script saiu: para
    # a CSP do site poder fechar em 'self'. Enquanto os 20 KB de CSS ficavam
    # dentro de <style>, style-src precisava de 'unsafe-inline', e isso vale
    # para a página inteira, não só para este bloco. A versão de docs/ continua
    # sendo um arquivo só, porque ela não é servida sob a CSP.
    abre = corpo.index("<style>")
    corte = corpo.index("</style>") + len("</style>")
    SITE_CSS.write_text(
        "/* Gerado por tools/build_mapa_prototype.py. Não edite à mão.\n"
        " * Separado do documento porque a CSP do site é style-src 'self'. */\n"
        + corpo[abre + len("<style>"):corte - len("</style>")],
        encoding="utf-8", newline="\n")
    SITE_HTML.write_text(
        CABECALHO_SITE + '<link rel="stylesheet" href="./tokens.css">\n'
        + corpo[:abre] + '<link rel="stylesheet" href="./plano.css">'
        + "\n</head>\n<body>\n" + corpo[corte:]
        + '\n<script src="./plano.js"></script>\n</body>\n</html>\n',
        encoding="utf-8", newline="\n")
    SITE_JS.write_text(
        "// Gerado por tools/build_mapa_prototype.py. Não edite à mão.\n"
        "// Separado do documento porque a CSP do site é script-src 'self'.\n"
        + (_TRAVA_JS.replace("__SHA__", SENHA_SHA256) if TRAVA_LIGADA else "")
        + script, encoding="utf-8", newline="\n")

    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1024:.1f} KB · "
          f"{len(magro['profiles'])} perfis, "
          f"{len([q for q in magro['questionnaire']['questions'] if q['kind'] == 'escolha'])} perguntas")
    # Carimba na hora. O gerador reescreve app.html a cada execução com a
    # referência crua, e quem rodasse só o gerador publicaria uma página apontando
    # para o hash antigo do script, a correção não chegaria a navegador com
    # cache. Deixar isso para um passo seguinte é confiar na memória de alguém.
    import importlib.util
    spec = importlib.util.spec_from_file_location("stamp_assets", ROOT / "tools" / "stamp_assets.py")
    stamp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stamp)
    ausentes: list[str] = []
    carimbado, trocas = stamp.stamp(SITE_HTML, ausentes)
    if ausentes:
        raise SystemExit(f"referência para arquivo inexistente: {ausentes}")
    if trocas:
        SITE_HTML.write_text(carimbado, encoding="utf-8", newline="\n")

    print(f"{SITE_HTML.relative_to(ROOT)} + {SITE_JS.relative_to(ROOT)}: "
          f"{(SITE_HTML.stat().st_size + SITE_JS.stat().st_size) / 1024:.1f} KB")


_TRAVA_JS = r"""
/* Trava de conveniência, não de segurança. A comparação roda no navegador e o
   conteúdo é sintético: quem abrir o código passa. Ela existe para o visitante
   casual não cair numa tela inacabada. Nada real pode ser protegido assim, se um dia esta página mostrar carteira de cliente, a trava tem de sair e dar
   lugar a autenticação de verdade no servidor.
   A senha não aparece em texto claro aqui só para não vazar por leitura casual
   do fonte; o hash não a torna secreta. */
(function () {
  const ESPERADO = "__SHA__";
  const trava = document.getElementById("trava");
  const app = document.getElementById("app");
  const erro = document.getElementById("trava-erro");

  function liberar() {
    trava.style.display = "none";
    app.classList.remove("hidden");
  }
  try { if (sessionStorage.getItem("benevente-app") === "1") liberar(); } catch (e) {}

  async function conferir() {
    const valor = document.getElementById("senha").value;
    let digest;
    try {
      const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(valor));
      digest = [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, "0")).join("");
    } catch (e) {
      erro.textContent = "Este navegador não permite conferir a senha nesta página.";
      return;
    }
    if (digest !== ESPERADO) {
      erro.className = "ajuda ruim";
      erro.textContent = "Senha incorreta.";
      return;
    }
    try { sessionStorage.setItem("benevente-app", "1"); } catch (e) {}
    liberar();
  }

  document.getElementById("entrar").onclick = conferir;
  document.getElementById("senha").onkeydown = e => { if (e.key === "Enter") conferir(); };
})();
"""


if __name__ == "__main__":
    main()
