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
OUT = ROOT / "docs" / "desenho_tela_mapa.html"

PERFIL_LABEL = {"conservador": "Conservador", "equilibrado": "Equilibrado", "arrojado": "Arrojado"}

HTML = """<title>Plano de carteira</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap">
<style>
/* Escrito a partir da tela pequena: as regras de base valem para o celular e
   só crescem em telas maiores. O contrário — desenhar no monitor e depois
   apertar — é o que produz alvo de toque de trinta pixels e tabela que sangra
   para fora da margem. */
:root {
  --ground: #FBFBF9;  --panel: #FFFFFF;   --ink: #15191D;    --muted: #67707A;
  --line: #E1E2DE;    --accent: #0B6B63;  --accent-soft: #E6F0EE;
  --down: #B23A30;    --down-soft: #F7EAE8; --warn: #8A6A1F; --warn-soft: #FAF2DF;
  --shadow: 0 1px 2px rgba(20,25,30,.05);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground: #101315; --panel: #171B1E;  --ink: #E7EAEC;    --muted: #949CA4;
    --line: #262B2F;   --accent: #4FBFB2; --accent-soft: #16302E;
    --down: #E4776A;   --down-soft: #2E1D1B; --warn: #D8B45E; --warn-soft: #2C2415;
    --shadow: none;
  }
}
:root[data-theme="dark"] {
  --ground: #101315; --panel: #171B1E;  --ink: #E7EAEC;    --muted: #949CA4;
  --line: #262B2F;   --accent: #4FBFB2; --accent-soft: #16302E;
  --down: #E4776A;   --down-soft: #2E1D1B; --warn: #D8B45E; --warn-soft: #2C2415;
  --shadow: none;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--ground); color: var(--ink);
  font-family: "Plus Jakarta Sans", system-ui, -apple-system, sans-serif;
  font-size: 16px; line-height: 1.55; -webkit-font-smoothing: antialiased;
  overflow-wrap: break-word;
}
.wrap { max-width: 40rem; margin: 0 auto; padding: 1.75rem 1.15rem 4rem; }
.num { font-family: "DM Mono", ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.neg { color: var(--down); }
.hidden { display: none; }

header { border-bottom: 1px solid var(--line); padding-bottom: 1.25rem; margin-bottom: 2rem; }
.eyebrow { font-size: .7rem; letter-spacing: .1em; text-transform: uppercase;
           color: var(--muted); font-weight: 600; margin: 0 0 .45rem; }
h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: -.02em; margin: 0 0 .4rem;
     text-wrap: balance; }
header p { margin: 0; color: var(--muted); font-size: .92rem; }

section { margin-bottom: 2.5rem; }
h2 { font-size: 1.05rem; font-weight: 700; letter-spacing: -.01em; margin: 0 0 .3rem; }
.lede { color: var(--muted); font-size: .88rem; margin: 0 0 1.25rem; }

/* --- perguntas --- */
.q { border-top: 1px solid var(--line); padding: 1.15rem 0; }
.q:first-of-type { border-top: none; padding-top: .25rem; }
.q > p { margin: 0 0 .2rem; font-weight: 600; font-size: 1rem; text-wrap: pretty; }
.q .help { color: var(--muted); font-size: .84rem; margin: 0 0 .85rem; }
.opts { display: flex; flex-direction: column; gap: .5rem; }
.opt { font: inherit; font-size: .92rem; text-align: left; cursor: pointer;
       min-height: 2.75rem; padding: .7rem 1rem;
       border: 1px solid var(--line); border-radius: 10px; background: var(--panel);
       color: var(--ink); transition: border-color .12s, background .12s; }
.opt:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.opt[aria-pressed="true"] { background: var(--accent-soft); border-color: var(--accent);
                            color: var(--accent); font-weight: 600; }
.cap { font-size: .85rem; color: var(--muted); margin: 1rem 0 0; }
.cap b { color: var(--ink); font-weight: 600; }
/* Respondido, o formulário vira uma linha. No celular, deixá-lo aberto obriga a
   rolar por tudo que já foi respondido para chegar ao resultado. */
.chips { margin: 0 0 .5rem; font-size: .88rem; color: var(--ink); }
.chips span + span::before { content: " · "; color: var(--muted); }
.link { font: inherit; font-size: .85rem; font-weight: 600; color: var(--accent);
        background: none; border: 0; padding: .6rem 0; min-height: 2.75rem; cursor: pointer;
        text-decoration: underline; text-underline-offset: 3px; }
.link:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

/* --- resultado --- */
.verdict { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
           padding: 1.1rem 1.2rem; box-shadow: var(--shadow); }
.verdict .big { font-size: 1.4rem; font-weight: 700; letter-spacing: -.02em; }
.verdict p { margin: .35rem 0 0; color: var(--muted); font-size: .86rem; }

.bars { margin: 1.5rem 0 0; }
.barrow { margin-bottom: .85rem; }
.barrow > span { display: block; font-size: .78rem; color: var(--muted); margin-bottom: .3rem; }
.legend { display: flex; flex-wrap: wrap; gap: .4rem 1rem; margin-top: .75rem;
          font-size: .78rem; color: var(--muted); }
.legend i { display: inline-block; width: .65rem; height: .65rem; border-radius: 2px;
            margin-right: .35rem; vertical-align: -1px; }

.alert { margin-top: 1.35rem; background: var(--warn-soft); border-radius: 10px;
         padding: .9rem 1.05rem; font-size: .86rem; }
.alert b { color: var(--ink); }
.alert p { margin: 0; color: var(--muted); }

/* --- as duas escolhas --- */
.doors { display: grid; gap: .85rem; }
.door { text-align: left; font: inherit; cursor: pointer; background: var(--panel);
        border: 1px solid var(--line); border-radius: 12px; padding: 1.05rem 1.15rem;
        color: var(--ink); display: flex; flex-direction: column; gap: .55rem;
        transition: border-color .12s, box-shadow .12s; box-shadow: var(--shadow); }
.door:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.door[aria-pressed="true"] { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
.door h3 { margin: 0; font-size: 1rem; font-weight: 700; letter-spacing: -.01em; }
.door .cost { font-size: 1.5rem; font-weight: 700; letter-spacing: -.02em; }
.door .cost small { display: block; font-size: .76rem; font-weight: 500; color: var(--muted);
                    letter-spacing: 0; line-height: 1.35; }
.door dl { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: .3rem .7rem;
           font-size: .84rem; }
.door dt { color: var(--muted); } .door dd { margin: 0; text-align: right; }
.flag { font-size: .8rem; border-radius: 7px; padding: .5rem .7rem; margin-top: auto;
        line-height: 1.4; }
.flag.ok { background: var(--accent-soft); color: var(--accent); font-weight: 600; }
.flag.no { background: var(--down-soft); color: var(--down); font-weight: 600; }

/* --- o que muda --- */
.ledger { margin-top: 1.75rem; }
.grp { font-size: .72rem; letter-spacing: .09em; text-transform: uppercase; color: var(--muted);
       font-weight: 700; margin: 1.35rem 0 .4rem; }
.grp:first-child { margin-top: 0; }
.row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: .2rem .9rem;
       padding: .7rem 0; border-top: 1px solid var(--line); align-items: baseline; }
.row b { font-weight: 600; font-size: .95rem; }
.row .why { grid-column: 1 / -1; color: var(--muted); font-size: .8rem; }
.row .val { grid-column: 2; grid-row: 1; text-align: right; font-size: .95rem;
            white-space: nowrap; }
.row .val small { display: block; color: var(--muted); font-size: .74rem; }

.bill { margin-top: 1.75rem; border: 1px solid var(--line); border-radius: 12px;
        background: var(--panel); padding: 1rem 1.15rem; box-shadow: var(--shadow); }
.bill div { display: flex; flex-wrap: wrap; justify-content: space-between; gap: .1rem .9rem;
            padding: .55rem 0; font-size: .88rem; }
.bill div + div { border-top: 1px solid var(--line); }
.bill div span:last-child { margin-left: auto; }
.bill .tot { font-weight: 700; }
.bill p { margin: .85rem 0 0; font-size: .8rem; color: var(--muted); }

.cta { margin-top: 1.5rem; display: flex; flex-direction: column; gap: .7rem; }
.btn { font: inherit; font-size: .95rem; font-weight: 600; cursor: pointer; border-radius: 10px;
       min-height: 2.9rem; padding: .75rem 1.15rem; width: 100%;
       border: 1px solid var(--accent); background: var(--accent); color: var(--ground); }
.btn:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }
.cta span { font-size: .82rem; color: var(--muted); }

footer { border-top: 1px solid var(--line); margin-top: 2.5rem; padding-top: 1.15rem;
         font-size: .8rem; color: var(--muted); }
footer p { margin: 0 0 .6rem; }
footer code { font-family: "DM Mono", monospace; font-size: .95em; }

/* Só a partir do tablet o layout ganha colunas. Até lá tudo empilha, que é
   como a tela é de fato usada. */
@media (min-width: 40rem) {
  .wrap { padding: 2.75rem 1.5rem 5rem; }
  h1 { font-size: 1.85rem; }
  header p, .lede, footer p { max-width: 56ch; }
  .opts { flex-direction: row; flex-wrap: wrap; }
  .opt { padding: .6rem 1rem; font-size: .88rem; border-radius: 999px; }
  .barrow { display: grid; grid-template-columns: 4.5rem 1fr; gap: .8rem; align-items: center; }
  .barrow > span { text-align: right; margin-bottom: 0; }
  .doors { grid-template-columns: 1fr 1fr; gap: 1rem; }
  .row .why { grid-column: 1; }
  .cta { flex-direction: row; align-items: center; flex-wrap: wrap; }
  .btn { width: auto; }
}
/* Encolher o alvo de toque é decisão sobre o ponteiro, não sobre a largura: um
   tablet é largo e continua sendo dedo. Só onde existe mouse os controles
   ficam compactos e ganham estado de hover. */
@media (hover: hover) and (pointer: fine) {
  .opt, .link { min-height: 0; }
  .btn { min-height: 0; padding: .65rem 1.15rem; }
  .opt:hover, .door:hover { border-color: var(--accent); }
}
@media (prefers-reduced-motion: reduce) {
  * { transition: none !important; scroll-behavior: auto !important; }
}
</style>

<div class="wrap">
<header>
  <p class="eyebrow">Benevente · protótipo</p>
  <h1>Plano de carteira</h1>
  <p>Quatro perguntas definem o seu perfil. Depois você vê quanto da sua carteira já serve
     e escolhe entre dois planos.</p>
</header>

<section id="perguntas">
  <h2>Quatro perguntas</h2>
  <p class="lede">Sem pontuação: cada resposta impõe um limite e vale o mais apertado. Por isso
     dá sempre para apontar qual resposta decidiu.</p>
  <div id="qs"></div>
  <div id="resumo" class="hidden">
    <p class="chips" id="chips"></p>
    <button class="link" type="button" id="alterar">Alterar respostas</button>
  </div>
  <p class="cap" id="veredito"></p>
</section>

<section id="mapa" class="hidden">
  <h2>Sua carteira hoje</h2>
  <p class="lede">Lida do extrato da B3, do Open Finance e do que foi lançado à mão. Cada linha
     carrega de onde veio.</p>
  <div class="verdict">
    <div class="big num" id="aderencia"></div>
    <p id="aderencia-txt"></p>
  </div>
  <div class="bars">
    <div class="barrow"><span>hoje</span><div id="bar-hoje"></div></div>
    <div class="barrow"><span>seu perfil</span><div id="bar-alvo"></div></div>
    <div class="legend">
      <span><i style="background:var(--accent)"></i>ações</span>
      <span><i style="background:var(--muted)"></i>renda fixa e caixa</span>
      <span><i style="background:var(--down)"></i>fora do escopo</span>
    </div>
  </div>
  <div class="alert" id="fgc"></div>
</section>

<section id="portas" class="hidden">
  <h2>Dois planos</h2>
  <p class="lede">Um aplica o método inteiro e paga o imposto agora. O outro quase não custa e
     aplica metade. A escolha é sua, e as duas ficam registradas.</p>
  <div class="doors" id="doors"></div>
</section>

<section id="razao" class="hidden">
  <h2 id="razao-h"></h2>
  <p class="lede" id="razao-lede"></p>
  <div class="ledger" id="ledger"></div>
  <div class="bill" id="bill"></div>
  <div class="cta">
    <button class="btn" type="button">Baixar o dossiê do plano</button>
    <span>PDF com as contas, o plano que você não escolheu e o campo de assinatura.</span>
  </div>
</section>

<footer>
  <p><b>Protótipo.</b> A carteira é sintética. Os números vêm de
     <code>portfolio_mapping.py</code> e o perfil, de <code>client_intake.py</code>. Nenhuma ordem
     é transmitida por esta tela.</p>
  <p>O custo aparece antes do benefício de propósito. E nenhuma tela deste projeto promete
     patrimônio futuro: o que a Benevente publica é o quanto a própria régua erra.</p>
</footer>
</div>

<script>
const DADOS = __DADOS__;
const BRL = v => "R$ " + Math.round(v).toLocaleString("pt-BR");
const PCT = (v, c = 1) => (v * 100).toFixed(c).replace(".", ",") + "%";
const RANK = { conservador: 0, equilibrado: 1, arrojado: 2 };
const respostas = {};
let caminho = null;

const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html !== undefined) n.innerHTML = html;
  return n;
};

/* --- perguntas --- */
const escolha = DADOS.questionnaire.questions.filter(q => q.kind === "escolha");
const qs = document.getElementById("qs");
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
  qs.append(box);
});

const qsBox = document.getElementById("qs");
const resumoBox = document.getElementById("resumo");
document.getElementById("alterar").onclick = () => {
  qsBox.classList.remove("hidden");
  resumoBox.classList.add("hidden");
  qsBox.scrollIntoView({ behavior: "smooth", block: "start" });
};

function avaliar() {
  const veredito = document.getElementById("veredito");
  if (Object.keys(respostas).length < escolha.length) {
    veredito.textContent = "";
    ["mapa", "portas", "razao"].forEach(id => document.getElementById(id).classList.add("hidden"));
    return;
  }
  qsBox.classList.add("hidden");
  resumoBox.classList.remove("hidden");
  document.getElementById("chips").innerHTML =
    escolha.map(q => "<span>" + respostas[q.key].brief + "</span>").join("");
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
  veredito.innerHTML = "Perfil <b>" + perfil + "</b> — " +
    (causas.length ? causas.map(o => o.note).join("; ")
                   : "nenhuma resposta impôs teto abaixo do máximo") +
    ". A pior queda medida deste perfil foi de <b class='num neg'>" + PCT(pior) + "</b>.";
  render(perfil);
}

/* --- mapa --- */
function render(perfil) {
  const p = DADOS.profiles[perfil];
  const a = p.adequar, b = p.adaptar;
  ["mapa", "portas"].forEach(id => document.getElementById(id).classList.remove("hidden"));
  document.getElementById("razao").classList.add("hidden");
  caminho = null;

  document.getElementById("aderencia").textContent = PCT(a.alignment) + " já serve";
  document.getElementById("aderencia-txt").textContent =
    "De " + BRL(a.total_brl) + ", essa parte já está de acordo com o que a política declara para " +
    "o perfil " + perfil + ". É o resto que os dois planos tratam de forma diferente.";

  const fora = b.out_of_scope_brl / b.total_brl;
  barra("bar-hoje", [b.equity_before, 1 - b.equity_before - fora, fora]);
  barra("bar-alvo", [b.equity_budget, 1 - b.equity_budget, 0]);

  const fgc = document.getElementById("fgc");
  const estouros = Object.entries(a.fgc_breaches || {});
  fgc.style.display = estouros.length ? "flex" : "none";
  if (estouros.length) {
    const [nome, valor] = estouros[0];
    fgc.innerHTML = "<p><b>" + BRL(valor - 250000) + " sem cobertura do FGC.</b> " +
      "Você tem " + BRL(valor) + " no conglomerado " + nome + ", e a garantia cobre até " +
      "R$ 250.000 por CPF. Os dois planos mantêm essa posição: é risco de crédito assumido, e " +
      "assumi-lo precisa ser decisão registrada, não distração.</p>";
  }
  portas(perfil, a, b);
}

function barra(id, partes) {
  const cores = ["var(--accent)", "var(--muted)", "var(--down)"];
  const host = document.getElementById(id);
  host.innerHTML = "";
  host.style.cssText = "display:flex;height:26px;border-radius:5px;overflow:hidden;gap:2px";
  partes.forEach((v, i) => {
    if (v <= 0.001) return;
    const s = el("div");
    s.style.cssText = "flex:" + v + ";background:" + cores[i] +
      ";display:grid;place-items:center;font-size:.7rem;font-weight:600;color:var(--ground)";
    s.textContent = v > 0.08 ? PCT(v, 0) : "";
    s.title = PCT(v);
    host.append(s);
  });
}

/* --- portas --- */
function portas(perfil, a, b) {
  const host = document.getElementById("doors");
  host.innerHTML = "";
  [["adequar", a], ["adaptar", b]].forEach(([chave, m]) => {
    const d = el("button", "door");
    d.type = "button";
    d.setAttribute("aria-pressed", "false");
    d.append(
      el("h3", null, m.path_label),
      // "0,00% do patrimônio" lê como erro de formatação, não como "quase nada".
      el("div", "cost num", BRL(m.transition_total_brl) +
        "<small>custo hoje · " + (m.transition_cost_pct < 0.0001
          ? "menos de 0,01%" : PCT(m.transition_cost_pct, 2)) + " do patrimônio</small>"),
      el("dl", null,
        "<dt>Movimenta</dt><dd class='num'>" + BRL(m.turnover_brl) + "</dd>" +
        "<dt>Imposto</dt><dd class='num'>" + BRL(m.transition_tax_brl) + "</dd>" +
        "<dt>Módulos</dt><dd>" + m.modules.length + " de 2</dd>"),
      el("div", "flag " + (m.track_record_applies ? "ok" : "no"),
        m.track_record_applies
          ? "O histórico publicado descreve esta carteira"
          : "O histórico publicado NÃO descreve esta carteira"));
    d.onclick = () => {
      caminho = chave;
      host.querySelectorAll(".door").forEach(x => x.setAttribute("aria-pressed", "false"));
      d.setAttribute("aria-pressed", "true");
      razao(perfil, chave);
    };
    host.append(d);
  });
}

/* --- a razão do caminho escolhido --- */
function razao(perfil, chave) {
  const m = DADOS.profiles[perfil][chave];
  const outro = DADOS.profiles[perfil][chave === "adequar" ? "adaptar" : "adequar"];
  const sec = document.getElementById("razao");
  sec.classList.remove("hidden");
  document.getElementById("razao-h").textContent = m.path_label;
  document.getElementById("razao-lede").textContent = m.honesty;

  const grupos = [["vender", "Sai"], ["reduzir", "Reduz"], ["comprar", "Entra"], ["manter", "Fica"]];
  const led = document.getElementById("ledger");
  led.innerHTML = "";
  grupos.forEach(([acao, titulo]) => {
    const linhas = m.moves.filter(x => x.action === acao);
    if (!linhas.length) return;
    led.append(el("p", "grp", titulo + " · " + linhas.length));
    linhas.forEach(x => {
      const r = el("div", "row");
      const delta = x.delta_brl;
      r.append(
        el("b", null, x.ticker),
        el("div", "val num" + (delta < 0 ? " neg" : ""),
          (delta === 0 ? BRL(x.from_brl) : (delta > 0 ? "+" : "−") + BRL(Math.abs(delta))) +
          "<small>" + BRL(x.from_brl) + " → " + BRL(x.to_brl) + "</small>"),
        // O motivo primeiro: é ele que responde "por que essa linha existe".
        // A nota vem depois porque é consequência, não causa.
        el("div", "why", x.reason + (x.notes && x.notes.length ? " · " + x.notes[0] : "")));
      led.append(r);
    });
  });

  const bill = document.getElementById("bill");
  let html = "<div><span>Execução</span><span class='num'>" +
    BRL(m.transition_cost_brl) + "</span></div>";
  Object.entries(m.tax_by_bucket).forEach(([cesta, d]) => {
    const nome = { renda_variavel: "Renda variável", renda_fixa: "Renda fixa",
                   fora_do_escopo: "Fora do escopo" }[cesta] || cesta;
    html += "<div><span>" + nome + " · imposto sobre " + BRL(d.realised_gain_brl) +
      " apurados</span><span class='num'>" + BRL(d.tax_brl) + "</span></div>";
  });
  html += "<div class='tot'><span>Total, pago uma vez</span><span class='num'>" +
    BRL(m.transition_total_brl) + "</span></div>";
  // Todo zero na coluna de imposto precisa dizer por que é zero. Sem isso, a
  // isenção mensal e uma conta não feita ficam com a mesma aparência.
  const ganhoRV = (m.tax_by_bucket.renda_variavel || {}).realised_gain_brl || 0;
  html += "<p>Apurado por cesta, ao custo médio: ganhos e prejuízos se compensam dentro da cesta " +
    "e nunca entre cestas." +
    (m.exempt_month_assumed && ganhoRV > 0
      ? " O imposto sobre ações fica em zero porque o total vendido no mês cabe na isenção de " +
        "R$ 20 mil — se houver outra venda no mesmo mês, ela deixa de valer."
      : "") +
    (m.tax_by_bucket.fora_do_escopo
      ? " O zero na cesta fora do escopo não é isenção: é uma conta que não é feita aqui, porque " +
        "cripto tem regime próprio."
      : "") +
    " O outro plano custaria " + BRL(outro.transition_total_brl) + ".</p>";
  bill.innerHTML = html;
  sec.scrollIntoView({ behavior: "smooth", block: "start" });
}
</script>
"""


def main() -> None:
    dados = json.loads(SOURCE.read_text(encoding="utf-8"))
    magro = {
        "questionnaire": dados["questionnaire"],
        "profiles": {nome: {"adequar": p["adequar"], "adaptar": p["adaptar"]}
                     for nome, p in dados["profiles"].items()},
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
