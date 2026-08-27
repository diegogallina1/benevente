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

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "portfolio_mapping_v1" / "mapping_by_profile.json"
CONEXAO = ROOT / "artifacts" / "b3_connection_v1" / "connection_example.json"
OUT = ROOT / "docs" / "desenho_tela_mapa.html"

PERFIL_LABEL = {"conservador": "Conservador", "equilibrado": "Equilibrado", "arrojado": "Arrojado"}

HTML = r"""<title>Plano de carteira</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
/* Tokens do IBM Carbon Design System v11 (Apache 2.0), lidos do pacote
   @carbon/themes 11.79.0: tema White para o claro, Gray 100 para o escuro.
   Tipografia IBM Plex Sans e IBM Plex Mono, do próprio sistema.

   Duas decisões vêm do Carbon e valem a pena nomear. Canto reto em tudo, sem
   raio nenhum: é a assinatura do sistema e o contrário do arredondado que hoje
   marca praticamente toda interface gerada. E aviso com barra de 3px à esquerda
   em vez de ícone, que informa a gravidade sem pedir atenção.

   Escrito a partir da tela pequena: as regras de base valem para o celular e só
   crescem depois. O contrário — desenhar no monitor e apertar — é o que produz
   alvo de toque de trinta pixels e tabela que sangra para fora da margem. */
:root {
  --bg: #ffffff;         --layer: #f4f4f4;      --layer-2: #ffffff;
  --line: #c6c6c6;       --line-strong: #8d8d8d;
  --fg: #161616;         --fg-2: #525252;       --fg-3: #6f6f6f;
  --on-color: #ffffff;
  --acao: #0f62fe;       --acao-fraco: #edf5ff;   --btn: #0f62fe;
  --erro: #da1e28;       --erro-fraco: #fff1f1;
  --aviso: #f1c21b;      --aviso-fraco: #fcf4d6;
  --ok: #24a148;         --ok-fraco: #defbe6;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #161616;       --layer: #262626;      --layer-2: #393939;
    --line: #525252;     --line-strong: #6f6f6f;
    --fg: #f4f4f4;       --fg-2: #c6c6c6;       --fg-3: #a8a8a8;
    --on-color: #ffffff;
    --acao: #78a9ff;     --acao-fraco: #002d9c;   --btn: #0f62fe;
    --erro: #fa4d56;     --erro-fraco: #520408;
    --aviso: #f1c21b;    --aviso-fraco: #483700;
    --ok: #42be65;       --ok-fraco: #022d0d;
  }
}
:root[data-theme="dark"] {
  --bg: #161616;         --layer: #262626;      --layer-2: #393939;
  --line: #525252;       --line-strong: #6f6f6f;
  --fg: #f4f4f4;         --fg-2: #c6c6c6;       --fg-3: #a8a8a8;
  --on-color: #ffffff;
  --acao: #78a9ff;       --acao-fraco: #002d9c;   --btn: #0f62fe;
  --erro: #fa4d56;       --erro-fraco: #520408;
  --aviso: #f1c21b;      --aviso-fraco: #483700;
  --ok: #42be65;         --ok-fraco: #022d0d;
}

* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font-family: "IBM Plex Sans", system-ui, -apple-system, sans-serif;
  font-size: 1rem; line-height: 1.5; letter-spacing: 0;
  -webkit-font-smoothing: antialiased; overflow-wrap: break-word;
}
.wrap { max-width: 42rem; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
.num { font-family: "IBM Plex Mono", ui-monospace, monospace;
       font-variant-numeric: tabular-nums; letter-spacing: -.01em; }
.neg { color: var(--erro); }
.hidden { display: none; }
::selection { background: var(--btn); color: var(--on-color); }

/* Tipografia na escala do Carbon: label-01, body-01, body-02, heading-03/04. */
.label { font-size: .75rem; line-height: 1.34; letter-spacing: .32px;
         color: var(--fg-3); font-weight: 400; margin: 0; }
h1 { font-size: 1.75rem; line-height: 1.29; font-weight: 400; letter-spacing: 0;
     margin: 0 0 .5rem; text-wrap: balance; }
h2 { font-size: 1.25rem; line-height: 1.4; font-weight: 400; margin: 0 0 .25rem; }
h3 { font-size: 1rem; line-height: 1.5; font-weight: 600; margin: 0; }
.lede { color: var(--fg-2); font-size: .875rem; line-height: 1.43; margin: 0 0 1.5rem; }

header { padding-bottom: 1.5rem; margin-bottom: 1.5rem;
         border-bottom: 1px solid var(--line); }
.topo { display: flex; align-items: center; justify-content: space-between;
        gap: 1rem; margin-bottom: 1rem; }
.marca { font-size: .875rem; font-weight: 600; letter-spacing: .16px; margin: 0; }
.marca span { color: var(--fg-3); font-weight: 400; }
header p:last-child { margin: 0; color: var(--fg-2); font-size: .875rem; line-height: 1.43; }

.tema { font: inherit; font-size: .75rem; letter-spacing: .32px; color: var(--fg-2);
        background: none; border: 1px solid var(--line); border-radius: 0;
        min-height: 2.75rem; padding: 0 .75rem; cursor: pointer;
        display: flex; align-items: center; gap: .5rem; white-space: nowrap; }
.tema:focus-visible { outline: 2px solid var(--acao); outline-offset: -2px; }

/* Indicador de etapa: régua no topo de cada item, como no Carbon. Serve para
   responder "quanto falta", que é a pergunta que faz alguém abandonar. */
.etapas { display: grid; grid-template-columns: repeat(3, 1fr); gap: .25rem;
          list-style: none; margin: 0 0 2.5rem; padding: 0; }
.etapas li { border-top: 2px solid var(--line); padding-top: .5rem;
             font-size: .75rem; letter-spacing: .32px; color: var(--fg-3); }
.etapas li[data-on="1"] { border-top-color: var(--acao); color: var(--fg); font-weight: 600; }
.etapas b { display: block; font-weight: inherit; }

section { margin-bottom: 3rem; }

/* --- conexão --- */
.seguranca { list-style: none; margin: 0 0 1.5rem; padding: 0;
             border-top: 1px solid var(--line); }
.seguranca li { border-bottom: 1px solid var(--line); padding: .75rem 0;
                font-size: .875rem; line-height: 1.43; color: var(--fg-2); }
.seguranca b { color: var(--fg); font-weight: 600; }
details { margin-top: 1.5rem; border-top: 1px solid var(--line); }
details > summary { cursor: pointer; list-style: none; padding: .875rem 0;
                    font-size: .875rem; color: var(--acao); min-height: 2.75rem;
                    display: flex; align-items: center; justify-content: space-between;
                    gap: 1rem; }
details > summary::-webkit-details-marker { display: none; }
details > summary::after { content: "+"; font-family: "IBM Plex Mono", monospace;
                           font-size: 1.125rem; color: var(--fg-3); }
details[open] > summary::after { content: "–"; }
details > summary:focus-visible { outline: 2px solid var(--acao); outline-offset: -2px; }
details > summary b { color: var(--fg); font-weight: 600; }

.cols { display: grid; gap: 1.5rem; margin-top: 0; }
.cols ul { margin: .5rem 0 0; padding: 0; list-style: none; }
.cols li { font-size: .875rem; line-height: 1.43; color: var(--fg-2);
           padding: .5rem 0 .5rem .875rem; border-left: 2px solid var(--line); }
.cols .nao li { border-left-color: var(--erro); }

/* --- painéis --- */
.painel { background: var(--layer); padding: 1.25rem 1rem; }
.quando { display: flex; flex-wrap: wrap; gap: .375rem .75rem; align-items: baseline;
          font-size: .75rem; letter-spacing: .32px; color: var(--fg-3);
          border-bottom: 1px solid var(--line); padding-bottom: .625rem; margin-bottom: .875rem; }
.quando b { color: var(--fg); font-weight: 600; letter-spacing: 0; }
.quando.velho { color: var(--erro); }
.quando.velho b { color: var(--erro); }
.painel .big { font-size: 1.75rem; line-height: 1.29; font-weight: 400; }
.painel p { margin: .5rem 0 0; color: var(--fg-2); font-size: .875rem; line-height: 1.43; }

/* Campo do Carbon: fundo de camada, só borda inferior, altura de 48px. */
.informar { margin-top: 1rem; }
.informar label { display: block; font-size: .75rem; letter-spacing: .32px;
                  color: var(--fg-2); margin-bottom: .5rem; }
.campo { display: flex; flex-wrap: wrap; gap: .5rem; }
.campo input { font: inherit; font-family: "IBM Plex Mono", monospace; font-size: 1rem;
               flex: 1 1 10rem; min-width: 0; min-height: 3rem; padding: 0 1rem;
               color: var(--fg); background: var(--layer); border: 0; border-radius: 0;
               border-bottom: 1px solid var(--line-strong); }
.campo input:focus { outline: 2px solid var(--btn); outline-offset: -2px; }
.campo input[aria-invalid="true"] { border-bottom: 2px solid var(--erro); }
.campo .btn { flex: 0 0 auto; width: auto; min-width: 9rem; padding: .875rem 1rem; }
.informar .ajuda { font-size: .75rem; line-height: 1.34; color: var(--fg-3); margin: .5rem 0 0; }
.informar .ajuda.ruim { color: var(--erro); }
.resolvido { border-left: 3px solid var(--ok); background: var(--ok-fraco);
             padding: 1rem; margin-top: 1.5rem; font-size: .875rem; line-height: 1.43; }
.resolvido p { margin: 0; color: var(--fg-2); }
.resolvido b { color: var(--fg); font-weight: 600; }

.aviso { border-left: 3px solid var(--aviso); background: var(--aviso-fraco);
         padding: 1rem; margin-top: 1.5rem; font-size: .875rem; line-height: 1.43; }
.aviso.erro { border-left-color: var(--erro); background: var(--erro-fraco); }
.aviso p { margin: 0; color: var(--fg-2); }
.aviso b { color: var(--fg); font-weight: 600; }

.barras { margin-top: 1.5rem; }
.barra-linha { margin-bottom: 1rem; }
.barra-linha > span { display: block; font-size: .75rem; letter-spacing: .32px;
                      color: var(--fg-3); margin-bottom: .375rem; }
.legenda { display: flex; flex-wrap: wrap; gap: .5rem 1.25rem; margin-top: .75rem;
           font-size: .75rem; letter-spacing: .32px; color: var(--fg-3); }
.legenda i { display: inline-block; width: .75rem; height: .75rem;
             margin-right: .375rem; vertical-align: -1px; }

/* --- perguntas --- */
.q { padding: 1.25rem 0; border-top: 1px solid var(--line); }
.q:first-of-type { border-top: none; padding-top: 0; }
.q > p { margin: 0 0 .25rem; font-size: 1rem; font-weight: 600; text-wrap: pretty; }
.q .help { color: var(--fg-2); font-size: .875rem; line-height: 1.43; margin: 0 0 1rem; }
.opts { display: flex; flex-direction: column; gap: 1px; background: var(--line); }
.opt { font: inherit; font-size: .875rem; text-align: left; cursor: pointer;
       min-height: 3rem; padding: .75rem 1rem; border: 0; border-radius: 0;
       background: var(--layer); color: var(--fg);
       transition: background .11s, box-shadow .11s; }
.opt:focus-visible { outline: 2px solid var(--acao); outline-offset: -2px; }
.opt[aria-pressed="true"] { background: var(--btn); color: var(--on-color); font-weight: 600; }

.resumo { border-top: 1px solid var(--line); padding-top: 1rem; }
.chips { margin: 0 0 .25rem; font-size: .875rem; }
.chips span + span::before { content: " · "; color: var(--fg-3); }
.link { font: inherit; font-size: .875rem; color: var(--acao); background: none;
        border: 0; padding: .625rem 0; min-height: 2.75rem; cursor: pointer;
        text-decoration: underline; text-underline-offset: 2px; }
.link:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }
.veredito { font-size: .875rem; line-height: 1.43; color: var(--fg-2); margin: 1.5rem 0 0; }
.veredito b { color: var(--fg); font-weight: 600; }
.veredito b.neg { color: var(--erro); }

/* --- os dois planos --- */
.planos { display: grid; gap: 1rem; }
.plano { text-align: left; font: inherit; cursor: pointer; color: var(--fg);
         background: var(--layer); border: 0; border-radius: 0;
         border-left: 3px solid transparent; padding: 1.25rem 1rem;
         display: flex; flex-direction: column; gap: .75rem;
         transition: background .11s, border-color .11s; }
.plano:focus-visible { outline: 2px solid var(--acao); outline-offset: -2px; }
.plano[aria-pressed="true"] { border-left-color: var(--acao); background: var(--acao-fraco); }
.plano .custo { font-size: 2rem; line-height: 1.2; font-weight: 400; }
.plano .custo small { display: block; font-size: .75rem; letter-spacing: .32px;
                      color: var(--fg-3); margin-top: .25rem; }
.plano dl { margin: 0; display: grid; grid-template-columns: auto 1fr;
            gap: .375rem .75rem; font-size: .875rem; }
.plano dt { color: var(--fg-2); } .plano dd { margin: 0; text-align: right; }
.falta { border-left: 3px solid var(--erro); background: var(--bg); padding: .75rem;
         font-size: .8125rem; line-height: 1.4; color: var(--fg-2); }
.falta b { display: block; color: var(--erro); font-weight: 600; margin-bottom: .125rem; }
.selo { font-size: .8125rem; line-height: 1.4; padding: .625rem .75rem; margin-top: auto;
        border-left: 3px solid var(--ok); background: var(--ok-fraco); color: var(--fg); }
.selo.nao { border-left-color: var(--erro); background: var(--erro-fraco); }

/* --- o que muda --- */
.razao { margin-top: 1.5rem; }
.grupo { font-size: .75rem; letter-spacing: .32px; color: var(--fg-3);
         margin: 1.5rem 0 0; padding-bottom: .5rem; border-bottom: 1px solid var(--line); }
.grupo:first-child { margin-top: 0; }
.linha { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .125rem 1rem;
         padding: .75rem 0; border-bottom: 1px solid var(--line); align-items: baseline; }
.linha b { font-weight: 600; font-size: .875rem; }
.linha .porque { grid-column: 1 / -1; color: var(--fg-3); font-size: .8125rem;
                 line-height: 1.4; }
.linha .val { grid-column: 2; grid-row: 1; text-align: right; font-size: .875rem;
              white-space: nowrap; }
.linha .val small { display: block; color: var(--fg-3); font-size: .75rem; }

.conta { margin-top: 1.5rem; background: var(--layer); padding: .25rem 1rem 1rem; }
.conta div { display: flex; flex-wrap: wrap; justify-content: space-between;
             gap: .125rem 1rem; padding: .75rem 0; font-size: .875rem;
             border-bottom: 1px solid var(--line); line-height: 1.43; }
.conta div span:last-child { margin-left: auto; }
.conta .total { font-weight: 600; border-bottom: 0; }
.conta p { margin: 1rem 0 0; font-size: .8125rem; line-height: 1.4; color: var(--fg-3); }

/* Botão do Carbon: retangular, texto à esquerda, altura de 48px. */
.registro { margin-top: 1rem; background: var(--layer); padding: 1rem; }
.registro p { margin: 0 0 .75rem; font-size: .8125rem; line-height: 1.4; color: var(--fg-2); }
.registro pre { margin: 0; overflow-x: auto; font-family: "IBM Plex Mono", monospace;
                font-size: .75rem; line-height: 1.5; color: var(--fg); }

.acoes { margin-top: 1.5rem; display: flex; flex-direction: column; gap: .75rem; }
.btn { font: inherit; font-size: .875rem; text-align: left; cursor: pointer;
       border: 0; border-radius: 0; min-height: 3rem; padding: .875rem 4rem .875rem 1rem;
       background: var(--btn); color: var(--on-color); width: 100%;
       transition: background .11s; }
.btn:focus-visible { outline: 2px solid var(--acao); outline-offset: -4px;
                     box-shadow: inset 0 0 0 1px var(--on-color); }
.btn:disabled { background: var(--layer-2); color: var(--fg-3); cursor: default; }
.acoes span { font-size: .8125rem; line-height: 1.4; color: var(--fg-3); }

footer { border-top: 1px solid var(--line); margin-top: 3rem; padding-top: 1.5rem;
         font-size: .8125rem; line-height: 1.4; color: var(--fg-3); }
footer p { margin: 0 0 .75rem; }
footer code { font-family: "IBM Plex Mono", monospace; font-size: .95em; }
footer a { color: var(--acao); }

@media (min-width: 42rem) {
  .wrap { padding: 3rem 1.5rem 5rem; }
  h1 { font-size: 2.625rem; line-height: 1.199; }
  .lede, header p:last-child, footer p { max-width: 58ch; }
  .cols { grid-template-columns: 1fr 1fr; gap: 2rem; }
  .planos { grid-template-columns: 1fr 1fr; }
  .barra-linha { display: grid; grid-template-columns: 5rem 1fr; gap: 1rem;
                 align-items: center; }
  .barra-linha > span { text-align: right; margin-bottom: 0; }
  .linha .porque { grid-column: 1; }
  .acoes { flex-direction: row; align-items: center; flex-wrap: wrap; }
  .btn { width: auto; min-width: 14rem; }
}
@media (hover: hover) and (pointer: fine) {
  /* Encolher alvo de toque é decisão sobre o ponteiro, não sobre a largura: um
     tablet é largo e continua sendo dedo. */
  .tema { min-height: 2rem; } .link { min-height: 0; }
  .opt:hover { background: var(--layer-2); }
  .opt[aria-pressed="true"]:hover { background: var(--btn); }
  .plano:hover { background: var(--layer-2); }
  .btn:hover:not(:disabled) { filter: brightness(1.12); }
  .tema:hover { border-color: var(--line-strong); color: var(--fg); }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; scroll-behavior: auto !important; }
}
</style>

<div class="wrap">
<header>
  <div class="topo">
    <p class="marca">Benevente <span>· protótipo</span></p>
    <button class="tema" type="button" id="tema" aria-label="Alternar tema claro e escuro">
      <span aria-hidden="true" id="tema-icone"></span><span id="tema-txt">Tema</span>
    </button>
  </div>
  <h1>Plano de carteira</h1>
  <p>Conecte a sua conta da B3, responda quatro perguntas e veja quanto da sua carteira
     já serve. No fim, dois planos com custos bem diferentes.</p>
</header>

<ol class="etapas" id="etapas">
  <li data-on="1"><b>1</b>Conectar</li>
  <li><b>2</b>Perguntas</li>
  <li><b>3</b>Seu plano</li>
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
  <p class="lede">Sem pontuação: cada resposta impõe um limite e vale o mais apertado.
     Assim dá sempre para apontar qual resposta decidiu.</p>
  <div id="qs"></div>
  <div id="resumo" class="resumo hidden">
    <p class="chips" id="chips"></p>
    <button class="link" type="button" id="alterar">Alterar respostas</button>
  </div>
  <p class="veredito" id="veredito"></p>
</section>

<section id="mapa" class="hidden">
  <h2>Sua carteira hoje</h2>
  <p class="lede">Cada posição mostra de onde o dado veio: extrato da B3, Open Finance ou
     lançamento manual.</p>
  <div class="painel">
    <p class="quando" id="quando"></p>
    <div class="big num" id="aderencia"></div>
    <p id="aderencia-txt"></p>
  </div>
  <div class="barras">
    <div class="barra-linha"><span>hoje</span><div id="bar-hoje"></div></div>
    <div class="barra-linha"><span>seu perfil</span><div id="bar-alvo"></div></div>
    <div class="legenda">
      <span><i style="background:var(--btn)"></i>ações</span>
      <span><i style="background:var(--line-strong)"></i>renda fixa e caixa</span>
      <span><i style="background:var(--erro)"></i>fora da estratégia</span>
    </div>
  </div>
  <div class="aviso" id="fgc"></div>
</section>

<section id="planos-sec" class="hidden">
  <h2>Dois planos</h2>
  <p class="lede">Um troca os seus ativos pela seleção da política e protege nas quedas.
     O outro mantém os seus ativos e só protege. A escolha é sua, e as duas ficam
     registradas.</p>
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
    <span>PDF com as contas, o plano que você não escolheu e o campo de assinatura.</span>
  </div>
  <div class="registro hidden" id="registro"></div>
</section>

<footer>
  <p><b>Protótipo.</b> A carteira é sintética. Os números vêm de
     <code>portfolio_mapping.py</code>, o perfil de <code>client_intake.py</code> e a leitura
     da B3 de <code>b3_connection.py</code>. Nenhuma ordem é transmitida por esta tela.</p>
  <p>O custo aparece antes do benefício de propósito, e nenhuma tela deste projeto promete
     patrimônio futuro: o que a Benevente publica é o quanto a própria régua erra.</p>
  <p>Desenho sobre o <a href="https://carbondesignsystem.com/">IBM Carbon Design System</a>
     (Apache 2.0), com IBM Plex Sans e IBM Plex Mono.</p>
</footer>
</div>

<script>
const DADOS = __DADOS__;
const BRL = v => "R$ " + Math.round(v).toLocaleString("pt-BR");
const PCT = (v, c = 1) => (v * 100).toFixed(c).replace(".", ",") + "%";
const RANK = { conservador: 0, equilibrado: 1, arrojado: 2 };
const respostas = {};

const $ = id => document.getElementById(id);
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
// Sem escolha salva a página segue o sistema, que é o certo por padrão. A
// escolha explícita carimba data-theme e ganha das duas media queries.
const temaBtn = $("tema");
const guardado = (() => { try { return localStorage.getItem("tema"); } catch (e) { return null; } })();
const escuroDoSistema = () => matchMedia("(prefers-color-scheme: dark)").matches;
function aplicaTema(valor) {
  if (valor) document.documentElement.setAttribute("data-theme", valor);
  else document.documentElement.removeAttribute("data-theme");
  const escuro = valor ? valor === "dark" : escuroDoSistema();
  $("tema-icone").textContent = escuro ? "☾" : "☀";
  $("tema-txt").textContent = escuro ? "Escuro" : "Claro";
  temaBtn.setAttribute("aria-pressed", String(escuro));
}
aplicaTema(guardado);
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  if (!document.documentElement.hasAttribute("data-theme")) aplicaTema(null);
});
temaBtn.onclick = () => {
  const atual = document.documentElement.getAttribute("data-theme");
  const novo = (atual ? atual === "dark" : escuroDoSistema()) ? "light" : "dark";
  aplicaTema(novo);
  try { localStorage.setItem("tema", novo); } catch (e) { /* janela anônima: segue sem salvar */ }
};

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
    "A B3 manda o que você tem, mas não manda por quanto você comprou — esse dado não " +
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
      "Essa compra é anterior a " + b3.base_starts.split("-").reverse().join("/") +
      ", então não está no histórico que a B3 manda. Sem esse número não dá para calcular " +
      "o imposto dessa venda — e ele não é chutado aqui, porque um imposto chutado tem a " +
      "mesma cara de um imposto calculado.</p>";
    alerta.append(campoDeCusto(ticker, jaSabe));
  }
  mostra("perguntas");
  etapa(1);
  $("perguntas").scrollIntoView({ behavior: "smooth", block: "start" });
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
    (jaSabe > 0 ? "Das compras que a B3 mandou já sabemos " + BRL(jaSabe) + "; falta somar as " +
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
  // precisa de caminho de volta — sem ele, o único recerto é recarregar a página.
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
escolha.forEach(q => {
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
    };
    opts.append(b);
  });
  box.append(opts);
  qsBox.append(box);
});

const resumoBox = $("resumo");
$("alterar").onclick = () => {
  qsBox.classList.remove("hidden");
  resumoBox.classList.add("hidden");
  qsBox.scrollIntoView({ behavior: "smooth", block: "start" });
};

function avaliar() {
  if (Object.keys(respostas).length < escolha.length) {
    $("veredito").textContent = "";
    esconde("mapa", "planos-sec", "razao-sec");
    return;
  }
  // Respondido, o formulário vira uma linha: no celular, deixá-lo aberto obriga
  // a rolar por tudo que já foi respondido para chegar ao resultado.
  qsBox.classList.add("hidden");
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
  $("veredito").innerHTML = "Perfil <b>" + perfil + "</b> — " +
    (causas.length ? causas.map(o => o.note).join("; ")
                   : "nenhuma resposta impôs teto abaixo do máximo") +
    ". A pior queda já medida neste perfil foi de <b class='num neg'>" + PCT(pior) + "</b>.";
  etapa(2);
  if (perfilAtual !== perfil) planoAtual = null;
  render(perfil);
}

/* --- mapa --- */
function render(perfil) {
  perfilAtual = perfil;
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

  const fgc = $("fgc");
  const estouros = Object.entries(a.fgc_breaches || {});
  fgc.style.display = estouros.length ? "block" : "none";
  if (estouros.length) {
    const [nome, valor] = estouros[0];
    fgc.innerHTML = "<p><b>" + BRL(valor - 250000) + " sem cobertura do FGC.</b> " +
      "Você tem " + BRL(valor) + " no conglomerado " + nome + ", e a garantia cobre até " +
      "R$ 250.000 por CPF. Os dois planos mantêm essa posição: é risco de crédito assumido, " +
      "e assumi-lo precisa ser decisão registrada, não distração.</p>";
  }
  planos(perfil, a, b);
}

function barra(id, partes) {
  const cores = ["var(--btn)", "var(--line-strong)", "var(--erro)"];
  const host = $(id);
  host.innerHTML = "";
  host.style.cssText = "display:flex;height:2rem;overflow:hidden;gap:1px";
  partes.forEach((v, i) => {
    if (v <= 0.001) return;
    const s = el("div");
    s.style.cssText = "flex:" + v + ";background:" + cores[i] +
      ";display:grid;place-items:center;font-size:.75rem;color:var(--on-color)";
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
// escolha. Nenhum número atravessa — o gerador refaz as contas com o mesmo
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
    // Prejuízo não é base de imposto, é crédito — mas só dentro da própria
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
  html += "<p>O imposto é calculado por tipo de investimento, pelo preço médio: ganhos e " +
    "prejuízos se compensam dentro do mesmo tipo e nunca entre tipos diferentes." +
    (m.exempt_month_assumed && (m.tax_by_bucket.renda_variavel || {}).realised_gain_brl > 0
      ? " O imposto sobre ações fica em zero porque o total vendido no mês cabe na isenção de " +
        "R$ 20 mil — se houver outra venda no mesmo mês, ela deixa de valer."
      : "") +
    (m.tax_by_bucket.fora_do_escopo
      ? " O zero em Fora da estratégia não é isenção: é uma conta que não é feita aqui, " +
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
    caixa.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  if (rolar) $("razao-sec").scrollIntoView({ behavior: "smooth", block: "start" });
}
</script>
"""


def main() -> None:
    dados = json.loads(SOURCE.read_text(encoding="utf-8"))
    conexao = json.loads(CONEXAO.read_text(encoding="utf-8"))
    magro = {
        "questionnaire": dados["questionnaire"],
        "profiles": {nome: {"adequar": p["adequar"], "adaptar": p["adaptar"]}
                     for nome, p in dados["profiles"].items()},
        "b3": {"base_starts": conexao["base_starts"], "coverage": conexao["coverage"],
               "freshness": conexao["freshness"],
               "consent": {k: v for k, v in conexao["consent"].items()
                           if k in ("escopo", "revogavel_em", "credencial_armazenada")},
               "cost_basis": conexao["cost_basis"], "gaps": conexao["gaps"]},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HTML.replace("__DADOS__", json.dumps(magro, ensure_ascii=False,
                                                        separators=(",", ":"))),
                   encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1024:.1f} KB · "
          f"{len(magro['profiles'])} perfis, "
          f"{len([q for q in magro['questionnaire']['questions'] if q['kind'] == 'escolha'])} perguntas")


if __name__ == "__main__":
    main()
