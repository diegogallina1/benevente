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
CALIBRACAO = ROOT / "artifacts" / "forecast_calibration_v1" / "calibration.json"
OUT = ROOT / "docs" / "desenho_tela_mapa.html"

PERFIL_LABEL = {"conservador": "Conservador", "equilibrado": "Equilibrado", "arrojado": "Arrojado"}

HTML = r"""<title>Plano de carteira</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap">
<style>
/* Dovetail aplicado ao Benevente. Tokens do guia, adaptados ao layout que já
   existe: canvas quase preto sob uma grade de blueprint, tipo branco, uma única
   faísca indigo.

   Três decisões que o guia obriga e valem nomear.

   O botão primário é branco com texto preto, não colorido. Não é estilo: texto
   branco sobre o indigo #6798ff dá contraste 2,80 e reprova. O guia acerta ao
   reservar o branco para a única superfície de alta luminância da página.

   O guia manda ter um acento só. O produto precisa de vermelho para valor
   negativo, que é requisito de leitura, não decoração — então são dois
   cromáticos e nada mais. Verde e amarelo saíram: o aviso de FGC passou a usar
   a borda de risco, e o selo de histórico usa indigo ou vermelho.

   E o vermelho tem contraste 1,01 contra o indigo: em escala de cinza os dois
   são o mesmo tom. Por isso nenhuma informação depende só da cor — o selo diz
   "foi" ou "NÃO foi" por escrito, e no gráfico a posição do ponto já revela se
   caiu fora da faixa.

   O guia é escuro por definição. O tema claro aqui é adaptação, não parte
   dele: mantém o indigo e inverte a pilha de superfícies. */
:root {
  --canvas: #0a0a0a;   --card: #141414;    --elev: #1e1e1e;
  --line: #313131;     --line-strong: #454545;
  /* Ash para tudo que é secundário, inclusive legenda e metadado, como o guia
     manda; Mist só para desabilitado. Usar Mist em legenda dava 4,25 de
     contraste no tema claro, abaixo do mínimo. */
  --fg: #ffffff;       --fg-2: #a7a7a7;    --fg-3: #7c7c7c;
  --acao: #6798ff;     --acao-fraco: #101a2e;
  --neg: #ff6b6b;      --neg-fraco: #241213;
  --btn: #ffffff;      --btn-fg: #0a0a0a;
  --grade: #1e1e1e;
}
:root[data-theme="light"] {
  --canvas: #ffffff;   --card: #f6f7f9;    --elev: #eceef2;
  --line: #dcdfe5;     --line-strong: #b6bcc6;
  --fg: #0a0a0a;       --fg-2: #52565e;    --fg-3: #767b85;
  --acao: #2f5fd0;     --acao-fraco: #eaf0ff;
  --neg: #c8322f;      --neg-fraco: #fdecec;
  --btn: #0a0a0a;      --btn-fg: #ffffff;
  --grade: #eceef2;
}

* { box-sizing: border-box; }
body {
  margin: 0; color: var(--fg); background: var(--canvas);
  font-family: "Inter", ui-sans-serif, system-ui, -apple-system, sans-serif;
  font-size: 16px; line-height: 1.5; letter-spacing: -.25px;
  font-feature-settings: "liga";
  -webkit-font-smoothing: antialiased; overflow-wrap: break-word;
  /* A grade de blueprint: 1px a cada 48px, recuada o suficiente para orientar
     sem competir. É a assinatura do sistema. */
  background-image:
    linear-gradient(to right, var(--grade) 1px, transparent 1px),
    linear-gradient(to bottom, var(--grade) 1px, transparent 1px);
  background-size: 48px 48px;
  background-attachment: fixed;
}
.wrap { max-width: 1200px; margin: 0 auto; padding: 24px 16px 96px; }
@media (min-width: 42rem) { .wrap { max-width: 42rem; padding: 64px 24px 96px; } }
.num { font-family: "JetBrains Mono", ui-monospace, monospace;
       font-variant-numeric: tabular-nums; letter-spacing: 0; }
.neg { color: var(--neg); }
.hidden { display: none; }
::selection { background: var(--acao); color: var(--canvas); }

/* JetBrains Mono em caixa alta com tracking largo: lê como metadado, não como
   texto corrido. É o que o guia usa para rotular seção. */
.label, .eyebrow {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 12px; line-height: 1.4; letter-spacing: .85px;
  text-transform: uppercase; color: var(--fg-2); font-weight: 400; margin: 0;
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
.marca { font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: .85px;
         text-transform: uppercase; color: var(--fg); margin: 0; }
.marca span { color: var(--fg-2); }
header p:last-child { margin: 0; color: var(--fg-2); font-size: 16px; }

/* Pílula: o guia reserva o raio total para navegação e controles do topo. */
.tema { font: inherit; font-family: "JetBrains Mono", monospace; font-size: 12px;
        letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2);
        background: transparent; border: 1px solid var(--line-strong); border-radius: 9999px;
        min-height: 44px; padding: 0 14px; cursor: pointer;
        display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.tema:focus-visible { outline: 2px solid var(--acao); outline-offset: 2px; }

.etapas { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px;
          list-style: none; margin: 0 0 40px; padding: 0; }
.etapas li { border-top: 1px solid var(--line); padding-top: 8px;
             font-family: "JetBrains Mono", monospace; font-size: 12px;
             letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2); }
.etapas li[data-on="1"] { border-top-color: var(--acao); color: var(--fg); }
.etapas b { display: block; font-weight: 400; color: var(--acao); }

section { margin-bottom: 80px; }

/* --- conexão --- */
.seguranca { list-style: none; margin: 0 0 24px; padding: 0; border-top: 1px solid var(--line); }
.seguranca li { border-bottom: 1px solid var(--line); padding: 16px 0;
                font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.seguranca b { color: var(--fg); font-weight: 500; }
details { margin-top: 24px; border-top: 1px solid var(--line); }
details > summary { cursor: pointer; list-style: none; padding: 16px 0; min-height: 44px;
                    font-family: "JetBrains Mono", monospace; font-size: 12px;
                    letter-spacing: .85px; text-transform: uppercase; color: var(--acao);
                    display: flex; align-items: center; justify-content: space-between; gap: 16px; }
details > summary::-webkit-details-marker { display: none; }
details > summary::after { content: "+"; color: var(--fg-2); font-size: 16px; }
details[open] > summary::after { content: "–"; }
details > summary:focus-visible { outline: 2px solid var(--acao); outline-offset: -2px; }
details > summary b { color: var(--fg); font-weight: 400; }
.cols { display: grid; gap: 24px; margin-top: 0; }
.cols ul { margin: 8px 0 0; padding: 0; list-style: none; }
.cols li { font-size: 14px; line-height: 1.57; color: var(--fg-2);
           padding: 8px 0 8px 16px; border-left: 1px solid var(--line); }
.cols .nao li { border-left-color: var(--neg); }

/* --- superfícies --- */
.painel { background: var(--card); border: 1px solid var(--elev); border-radius: 8px;
          padding: 24px; }
.painel .big { font-size: 40px; line-height: 1.2; letter-spacing: -.84px; font-weight: 500; }
.painel p { margin: 8px 0 0; color: var(--fg-2); font-size: 14px; line-height: 1.57; }
.quando { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: baseline;
          font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: .85px;
          text-transform: uppercase; color: var(--fg-2);
          border-bottom: 1px solid var(--elev); padding-bottom: 16px; margin-bottom: 16px; }
.quando b { color: var(--fg); font-weight: 400; }
.quando.velho, .quando.velho b { color: var(--neg); }

.aviso { border-left: 2px solid var(--acao); background: var(--card); border-radius: 0 8px 8px 0;
         padding: 16px; margin-top: 24px; font-size: 14px; line-height: 1.57; }
.aviso.erro { border-left-color: var(--neg); }
.aviso p { margin: 0; color: var(--fg-2); }
.aviso b { color: var(--fg); font-weight: 500; }

.barras { margin-top: 24px; }
.barra-linha { margin-bottom: 16px; }
.barra-linha > span { display: block; font-family: "JetBrains Mono", monospace;
                      font-size: 12px; letter-spacing: .85px; text-transform: uppercase;
                      color: var(--fg-2); margin-bottom: 8px; }
.legenda { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 16px;
           font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: .85px;
           text-transform: uppercase; color: var(--fg-2); }
.legenda i { display: inline-block; width: 8px; height: 8px; border-radius: 2px;
             margin-right: 8px; vertical-align: 0; }

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
.chips { margin: 0 0 8px; font-family: "JetBrains Mono", monospace; font-size: 12px;
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
.regua { margin-top: 24px; border-top: 1px solid var(--line); padding-top: 24px; }
.regua h3 { margin-bottom: 8px; }
.regua p { margin: 0 0 16px; font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.regua p b { color: var(--fg); font-weight: 500; }
.regua p b.neg { color: var(--neg); }
.regua figure { margin: 16px 0 0; }
.regua svg { display: block; width: 100%; height: auto; }
.regua figcaption { margin-top: 8px; font-size: 12px; line-height: 1.4; color: var(--fg-2); }
.regua .chaves { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: 8px;
                 font-family: "JetBrains Mono", monospace; font-size: 12px;
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
.plano .custo small { display: block; font-family: "JetBrains Mono", monospace;
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
.selo.nao { border-left-color: var(--neg); color: var(--neg); }

/* --- o que muda --- */
.razao { margin-top: 24px; }
.grupo { font-family: "JetBrains Mono", monospace; font-size: 12px; letter-spacing: .85px;
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
.btn:disabled { background: transparent; color: var(--fg-3); border-color: var(--line-strong);
                cursor: default; }
.acoes span { font-size: 12px; line-height: 1.4; color: var(--fg-2); }

.registro { margin-top: 16px; background: var(--card); border: 1px solid var(--elev);
            border-radius: 8px; padding: 24px; }
.registro p { margin: 0 0 16px; font-size: 14px; line-height: 1.57; color: var(--fg-2); }
.registro pre { margin: 0; overflow-x: auto; font-family: "JetBrains Mono", monospace;
                font-size: 12px; line-height: 1.6; color: var(--fg); }

.informar { margin-top: 16px; }
.informar label { display: block; font-family: "JetBrains Mono", monospace; font-size: 12px;
                  letter-spacing: .85px; text-transform: uppercase; color: var(--fg-2);
                  margin-bottom: 8px; }
.campo { display: flex; flex-wrap: wrap; gap: 8px; }
.campo input { font: inherit; font-family: "JetBrains Mono", monospace; font-size: 16px;
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
footer code { font-family: "JetBrains Mono", monospace; }
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
      <span><i style="background:var(--acao)"></i>ações</span>
      <span><i style="background:var(--line-strong)"></i>renda fixa e caixa</span>
      <span><i style="background:var(--neg)"></i>fora da estratégia</span>
    </div>
  </div>
  <div class="aviso" id="fgc"></div>
  <div class="regua" id="regua"></div>
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
// O Dovetail é escuro por definição: o escuro é o padrão, não uma resposta à
// preferência do sistema. O claro continua existindo porque foi pedido antes,
// mas é adaptação — o guia não o traz.
const temaBtn = $("tema");
const guardado = (() => { try { return localStorage.getItem("tema"); } catch (e) { return null; } })();
function aplicaTema(valor) {
  const claro = valor === "light";
  if (claro) document.documentElement.setAttribute("data-theme", "light");
  else document.documentElement.removeAttribute("data-theme");
  $("tema-icone").textContent = claro ? "☀" : "☾";
  $("tema-txt").textContent = claro ? "Claro" : "Escuro";
  temaBtn.setAttribute("aria-pressed", String(!claro));
}
aplicaTema(guardado === "light" ? "light" : "dark");
temaBtn.onclick = () => {
  const novo = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
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
  // acaso — e é justamente o perfil que acertou tudo que precisa dizer isso.
  const ep = Math.round((c.cobertura.standard_error || 0) * 100);
  host.append(el("p", null,
    "<b>Oito anos é pouco.</b> A margem de erro dessa contagem é de cerca de " + ep +
    " pontos, então acertar 6 ou acertar 8 não se distingue de sorte. O que está " +
    "medido aqui é a régua, não uma promessa de resultado — nenhuma tela deste " +
    "produto projeta o seu patrimônio."));
  host.append(grafico(c.anos));
  const chaves = el("div", "chaves",
    "<span><i style='background:var(--line-strong)'></i>faixa projetada em janeiro</span>" +
    "<span><i style='background:var(--acao)'></i>o que aconteceu</span>" +
    "<span><i style='background:var(--neg)'></i>ficou fora da faixa</span>");
  host.append(chaves);
}

function grafico(anos) {
  const L = 30, R = 6, T = 10, B = 22, W = 320, H = 150;
  const baixo = Math.min(...anos.map(a => Math.min(a.p10, a.realised)));
  const alto = Math.max(...anos.map(a => Math.max(a.p90, a.realised)));
  const folga = (alto - baixo) * 0.08;
  const min = baixo - folga, max = alto + folga;
  const y = v => T + (H - T - B) * (1 - (v - min) / (max - min));
  const passo = (W - L - R) / anos.length;
  const x = i => L + passo * (i + 0.5);

  const svg = ["<svg viewBox='0 0 " + W + " " + H + "' role='img' aria-label='" +
    "Para cada ano, a faixa projetada em janeiro e o retorno que de fato aconteceu.'>"];
  // Linha do zero, que é a referência que importa num gráfico de retorno.
  if (min < 0 && max > 0) {
    svg.push("<line x1='" + L + "' x2='" + (W - R) + "' y1='" + y(0) + "' y2='" + y(0) +
      "' stroke='var(--line)' stroke-width='1'/>");
  }
  [min + (max - min) * 0.02, max - (max - min) * 0.02].forEach(v => {
    svg.push("<text x='" + (L - 5) + "' y='" + (y(v) + 3) + "' text-anchor='end' " +
      "font-size='9' fill='var(--fg-2)'>" + Math.round(v * 100) + "%</text>");
  });
  anos.forEach((a, i) => {
    const cx = x(i);
    svg.push("<line x1='" + cx + "' x2='" + cx + "' y1='" + y(a.p10) + "' y2='" + y(a.p90) +
      "' stroke='var(--line-strong)' stroke-width='7' stroke-linecap='butt'/>");
    svg.push("<line x1='" + (cx - 4.5) + "' x2='" + (cx + 4.5) + "' y1='" + y(a.p50) +
      "' y2='" + y(a.p50) + "' stroke='var(--card)' stroke-width='1.5'/>");
    // Anel na cor do fundo: sem ele o ponto tem contraste 1,0 contra a barra no
    // tema escuro, ou seja, some justamente quando cai dentro da faixa — que é
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
  // A barra de ações usa o indigo com texto escuro em cima: branco sobre o
  // indigo dá contraste 2,80 e reprova.
  const cores = ["var(--acao)", "var(--line-strong)", "var(--neg)"];
  const host = $(id);
  host.innerHTML = "";
  host.style.cssText = "display:flex;height:2rem;overflow:hidden;gap:1px";
  partes.forEach((v, i) => {
    if (v <= 0.001) return;
    const s = el("div");
    s.style.cssText = "flex:" + v + ";background:" + cores[i] +
      ";display:grid;place-items:center;font-size:12px;color:var(--canvas)";
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


#: O site tem CSP com ``script-src 'self'``: script embutido é bloqueado. Por
#: isso a versão publicada separa o JavaScript num arquivo, enquanto o artefato
#: continua num documento só. Mesma fonte, dois empacotamentos.
SITE_HTML = ROOT / "web" / "app.html"
SITE_JS = ROOT / "web" / "plano.js"

#: Trava de conveniência, não de segurança. O conteúdo é sintético e a
#: comparação roda no navegador — qualquer pessoa que abra o código passa. Serve
#: para o visitante casual não cair numa tela inacabada, e nada além disso.
SENHA_SHA256 = "4c073be62dd2eeca3d94f45932aef78e01d815664e90d0144b7ed10978f8b801"

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
    <div class="topo"><p class="marca">Benevente <span>· protótipo</span></p></div>
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
    magro = {
        "questionnaire": dados["questionnaire"],
        "profiles": {nome: {"adequar": p["adequar"], "adaptar": p["adaptar"]}
                     for nome, p in dados["profiles"].items()},
        "b3": {"base_starts": conexao["base_starts"], "coverage": conexao["coverage"],
               "freshness": conexao["freshness"],
               "consent": {k: v for k, v in conexao["consent"].items()
                           if k in ("escopo", "revogavel_em", "credencial_armazenada")},
               "cost_basis": conexao["cost_basis"], "gaps": conexao["gaps"]},
        # Calibração: o que se publica não é a projeção, é o quanto ela erra.
        "calibracao": {
            perfil: {"anos": [{k: dados[k] for k in ("year", "p10", "p50", "p90",
                                                     "realised", "inside")}
                              for dados in r["years"]],
                     "cobertura": r["coverage"],
                     "vies_pp": r["median_bias_pp"]}
            for perfil, r in calibracao["profiles"].items()
        },
    }
    pagina = HTML.replace("__DADOS__", json.dumps(magro, ensure_ascii=False,
                                                  separators=(",", ":")))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(pagina, encoding="utf-8")

    # --- versão do site: mesmo conteúdo, script fora do documento ---
    marcacao, script = _partes(pagina)
    corpo = marcacao.replace('<div class="wrap">', TRAVA + '<div class="wrap hidden" id="app">', 1)
    corte = corpo.index("</style>") + len("</style>")
    SITE_HTML.write_text(
        CABECALHO_SITE + corpo[:corte] + "\n</head>\n<body>\n" + corpo[corte:]
        + '\n<script src="./plano.js"></script>\n</body>\n</html>\n',
        encoding="utf-8")
    SITE_JS.write_text(
        "// Gerado por tools/build_mapa_prototype.py. Não edite à mão.\n"
        "// Separado do documento porque a CSP do site é script-src 'self'.\n"
        + _TRAVA_JS.replace("__SHA__", SENHA_SHA256) + script, encoding="utf-8")

    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size / 1024:.1f} KB · "
          f"{len(magro['profiles'])} perfis, "
          f"{len([q for q in magro['questionnaire']['questions'] if q['kind'] == 'escolha'])} perguntas")
    # Carimba na hora. O gerador reescreve app.html a cada execução com a
    # referência crua, e quem rodasse só o gerador publicaria uma página apontando
    # para o hash antigo do script — a correção não chegaria a navegador com
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
        SITE_HTML.write_text(carimbado, encoding="utf-8")

    print(f"{SITE_HTML.relative_to(ROOT)} + {SITE_JS.relative_to(ROOT)}: "
          f"{(SITE_HTML.stat().st_size + SITE_JS.stat().st_size) / 1024:.1f} KB")


_TRAVA_JS = r"""
/* Trava de conveniência, não de segurança. A comparação roda no navegador e o
   conteúdo é sintético: quem abrir o código passa. Ela existe para o visitante
   casual não cair numa tela inacabada. Nada real pode ser protegido assim —
   se um dia esta página mostrar carteira de cliente, a trava tem de sair e dar
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
