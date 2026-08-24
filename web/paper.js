const LIVE_COPY = {
  "pt-BR": {
    locale: "pt-BR",
    title: { b1: "Benevente 1 em 2026", b2: "Benevente 2 em 2026" },
    subtitle: {
      b1: "Controle anual sem alteração intranual de exposição.",
      b2: "Referência principal com proteção por risco; mesmos cinco ativos do Benevente 1.",
    },
    failed: "O último registro íntegro do acompanhamento não pôde ser carregado.",
    current: "Acompanhamento corrente",
    reconstructed: "Reconstrução retrospectiva até 20/08/2026",
    value: "Patrimônio-sombra",
    return: "Retorno no ciclo",
    drawdown: "Maior queda no ciclo",
    exposure: "Exposição atual em ações",
    b1: "Benevente 1",
    b2: "Benevente 2",
    cdi: "CDI",
    ibov: "Ibovespa (preço)",
    cash: "CDI",
  },
  en: {
    locale: "en-GB",
    title: { b1: "Benevente 1 in 2026", b2: "Benevente 2 in 2026" },
    subtitle: {
      b1: "Annual control with no intrayear exposure changes.",
      b2: "Primary risk-overlay reference; the same five assets selected by Benevente 1.",
    },
    failed: "The latest valid monitoring record could not be loaded.",
    current: "Current monitoring",
    reconstructed: "Retrospective reconstruction through 20 Aug 2026",
    value: "Shadow value",
    return: "Cycle return",
    drawdown: "Maximum cycle drawdown",
    exposure: "Current equity exposure",
    b1: "Benevente 1",
    b2: "Benevente 2",
    cdi: "CDI",
    ibov: "Ibovespa (price)",
    cash: "CDI",
  },
};

function liveCopy() {
  return (document.documentElement.lang || "pt-BR").toLowerCase().startsWith("en")
    ? LIVE_COPY.en : LIVE_COPY["pt-BR"];
}

function linePath(values, width, height, minimum, maximum) {
  const span = maximum - minimum || 1;
  return values.map((value, index) => {
    const x = values.length === 1 ? 0 : index / (values.length - 1) * width;
    const y = height - (value - minimum) / span * height;
    return `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function liveChart(rows, primary, copy) {
  const width = 820;
  const height = 220;
  const keys = [
    [primary, primary === "benevente2" ? copy.b2 : copy.b1, "#0c8076"],
    [primary === "benevente2" ? "portfolio" : "benevente2", primary === "benevente2" ? copy.b1 : copy.b2, "#65a99e"],
    ["cdi", copy.cdi, "#3b779a"],
    ["ibovespa_price", copy.ibov, "#7a8490"],
  ];
  const all = keys.flatMap(([key]) => rows.map(row => Number(row[key])).filter(Number.isFinite));
  const rawMin = Math.min(...all);
  const rawMax = Math.max(...all);
  const padding = Math.max((rawMax - rawMin) * 0.10, 1);
  const minimum = rawMin - padding;
  const maximum = rawMax + padding;
  const grid = [0, 0.5, 1].map(fraction => {
    const y = height * fraction;
    const value = maximum - (maximum - minimum) * fraction;
    return `<line x1="0" y1="${y}" x2="${width}" y2="${y}"/><text x="4" y="${Math.max(12, y - 5)}">${(value - 100).toLocaleString(copy.locale, { maximumFractionDigits: 1 })}%</text>`;
  }).join("");
  const paths = keys.map(([key, label, colour]) =>
    `<path data-chart-key="${key}" d="${linePath(rows.map(row => Number(row[key])), width, height, minimum, maximum)}" stroke="${colour}"><title>${label}</title></path>`
  ).join("");
  const legend = keys.map(([key, label, colour]) => {
    const result = Number(rows.at(-1)[key]) - 100;
    return `<span><i style="background:${colour}"></i>${label} <b>${result >= 0 ? "+" : ""}${result.toLocaleString(copy.locale, { maximumFractionDigits: 2 })}%</b></span>`;
  }).join("");
  const firstDate = new Date(`${rows[0].date}T12:00:00`).toLocaleDateString(copy.locale);
  const lastDate = new Date(`${rows.at(-1).date}T12:00:00`).toLocaleDateString(copy.locale);
  return `<div class="live-chart" data-live-chart>
    <div class="live-chart-legend">${legend}</div>
    <div class="live-chart-readout" aria-live="polite">${lastDate}</div>
    <svg class="live-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="Desempenho em 2026, base 100">
      <g class="live-grid">${grid}</g>${paths}
      <line class="live-cursor" x1="${width}" x2="${width}" y1="0" y2="${height}"/>
      <rect class="live-hit" x="0" y="0" width="${width}" height="${height}"/>
    </svg>
    <div class="live-chart-axis"><span>${firstDate}</span><span>Retorno acumulado desde 02/01/2026</span><span>${lastDate}</span></div>
  </div>`;
}

function attachLiveChart(host, rows, primary, copy) {
  const svg = host.querySelector(".live-chart-svg");
  const cursor = host.querySelector(".live-cursor");
  const readout = host.querySelector(".live-chart-readout");
  if (!svg || !cursor || !readout) return;
  const names = {
    benevente2: copy.b2, portfolio: copy.b1, cdi: copy.cdi,
    ibovespa_price: copy.ibov,
  };
  svg.addEventListener("pointermove", event => {
    const bounds = svg.getBoundingClientRect();
    const fraction = Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width));
    const index = Math.round(fraction * (rows.length - 1));
    const row = rows[index];
    const x = fraction * 820;
    cursor.setAttribute("x1", x.toFixed(2));
    cursor.setAttribute("x2", x.toFixed(2));
    const order = [primary, primary === "benevente2" ? "portfolio" : "benevente2", "cdi", "ibovespa_price"];
    const values = order.map(key => `${names[key]} ${(Number(row[key]) - 100).toLocaleString(copy.locale, { signDisplay: "always", maximumFractionDigits: 2 })}%`);
    readout.textContent = `${new Date(`${row.date}T12:00:00`).toLocaleDateString(copy.locale)} · ${values.join(" · ")}`;
  });
}

function fullPortfolioPanel(data, mode, copy) {
  const definition = data.portfolio_definitions?.[mode === "b1" ? "benevente1" : "benevente2"];
  if (!definition?.target_allocation) return "";
  const pct = value => `${(Number(value) * 100).toLocaleString(copy.locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%`;
  const money = value => Number(value).toLocaleString(copy.locale, { style: "currency", currency: "BRL" });
  const rows = definition.target_allocation.map(item => {
    const difference = Number(item.difference_from_benevente1 || 0);
    const action = mode === "b1" || Math.abs(difference) < 0.000001
      ? "Manter"
      : `${difference > 0 ? "Aumentar" : "Reduzir"} ${pct(Math.abs(difference))}`;
    const actionClass = difference > 0 ? "increase" : difference < 0 ? "reduce" : "hold";
    return `<tr><td><strong>${item.ticker}</strong></td><td>${pct(item.weight)}</td><td>${money(item.amount_for_brl_100k)}</td><td><span class="allocation-action ${actionClass}">${action}</span></td></tr>`;
  }).join("");
  const state = mode === "b2" ? data.portfolio_definitions.benevente2.state_for_next_session : "anual";
  const decisions = mode === "b2" ? data.benevente2_overlay.risk_decisions.map(item => {
    const labels = { 0: "normal", 1: "alerta", 2: "severo" };
    const explanation = item.observed_on
      ? `Sinal observado em ${new Date(`${item.observed_on}T12:00:00`).toLocaleDateString(copy.locale)}. ${item.reason}.`
      : "Início do ciclo.";
    return `<li><time>${new Date(`${item.effective_on}T12:00:00`).toLocaleDateString(copy.locale)}</time><div><strong>${labels[item.to_state]} · ${pct(item.target_equity_weight)} em ações</strong><p>${explanation} O restante acompanha CDI.</p></div></li>`;
  }).join("") : `<li><time>${new Date(`${data.decision_date}T12:00:00`).toLocaleDateString(copy.locale)}</time><div><strong>Carteira anual registrada</strong><p>Os cinco ativos e os pesos permanecem até a próxima decisão anual.</p></div></li>`;
  return `<div class="live-allocation-full">
    <div class="allocation-heading"><div><span>ALVO PARA A PRÓXIMA SESSÃO</span><h4>Carteira completa · estado ${state}</h4></div><small>Simulação com R$ 100.000</small></div>
    <div class="allocation-table-wrap"><table class="allocation-table"><thead><tr><th>Ativo</th><th>Peso-alvo</th><th>Valor-alvo</th><th>Decisão</th></tr></thead><tbody>${rows}</tbody></table></div>
    <div class="risk-decision-log"><h4>${mode === "b2" ? "Decisões de risco em 2026" : "Decisão vigente em 2026"}</h4><ol>${decisions}</ol></div>
    <p class="allocation-disclaimer">Referência para carteira-sombra. A tabela não considera sua posição atual, impostos pessoais, suitability ou quantidade mínima negociável e não transmite ordens.</p>
  </div>`;
}

async function renderLivePortfolio(host, data, decision) {
  const copy = liveCopy();
  const mode = host.dataset.liveStrategy === "b1" ? "b1" : "b2";
  const primaryKey = mode === "b2" ? "benevente2" : "portfolio";
  const summaryKey = mode === "b2" ? "benevente2_reconstructed_return" : "portfolio_return";
  const drawdownKey = mode === "b2" ? "benevente2_maximum_drawdown" : "maximum_drawdown";
  const pct = value => `${Number(value) >= 0 ? "+" : ""}${(Number(value) * 100).toLocaleString(copy.locale, { maximumFractionDigits: 2 })}%`;
  const plain = value => `${(Number(value) * 100).toLocaleString(copy.locale, { maximumFractionDigits: 2 })}%`;
  const money = value => Number(value).toLocaleString(copy.locale, { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  const date = value => new Date(`${value}T12:00:00`).toLocaleDateString(copy.locale);
  const holdings = [...decision.holdings].sort((a, b) => b.weight - a.weight);
  const equity = holdings.reduce((total, item) => total + Number(item.weight), 0);
  const currentEquity = mode === "b2" ? data.benevente2_overlay.current_equity_weight : equity;
  const status = mode === "b2" ? copy.reconstructed : copy.current;
  const maxWeight = Math.max(decision.cdi_weight, ...holdings.map(item => item.weight));
  const holdingRows = holdings.map(item => {
    const live = data.holdings.find(row => row.ticker === item.ticker);
    return `<div class="paper-holding"><b>${item.ticker}</b><div class="bar"><i style="width:${item.weight / maxWeight * 100}%"></i></div><span>${plain(item.weight)} · ${pct(live?.total_return || 0)}</span></div>`;
  }).join("");
  const isVersionPage = host.hasAttribute("data-live-portfolio");
  host.innerHTML = `<div class="paper-portfolio live-portfolio-card">
    <div class="live-card-head"><div><span class="live-status">${status}</span><h3>${copy.title[mode]}</h3><p>${copy.subtitle[mode]} Decisão de ${date(data.decision_date)}, dados até ${date(data.through)}.</p></div><a class="live-version-tab" href="./benevente-${mode === "b2" ? "1" : "2"}.html">Ver ${mode === "b2" ? copy.b1 : copy.b2} →</a></div>
    <div class="paper-metrics live-metrics">
      <div class="paper-metric${data.summary[summaryKey] < 0 ? " negative" : ""}"><span>${copy.return}</span><b>${pct(data.summary[summaryKey])}</b><small>${mode === "b2" ? status : copy.current}</small></div>
      <div class="paper-metric"><span>${copy.value}</span><b>${money(100000 * (1 + data.summary[summaryKey]))}</b><small>capital inicial ${money(data.initial_capital_brl)}</small></div>
      <div class="paper-metric${data.summary[drawdownKey] < 0 ? " negative" : ""}"><span>${copy.drawdown}</span><b>${pct(data.summary[drawdownKey])}</b><small>do pico ao vale diário</small></div>
      <div class="paper-metric"><span>${copy.exposure}</span><b>${plain(currentEquity)}</b><small>${mode === "b2" ? `estado ${data.benevente2_overlay.current_risk_state}` : "peso anual constante"}</small></div>
    </div>
    ${liveChart(data.series, primaryKey, copy)}
    ${isVersionPage ? fullPortfolioPanel(data, mode, copy) : `<details class="live-holdings"><summary>Ver os cinco ativos e pesos de janeiro</summary><div class="paper-holdings">${holdingRows}<div class="paper-holding"><b>${copy.cash}</b><div class="bar cash"><i style="width:${decision.cdi_weight / maxWeight * 100}%"></i></div><span>${plain(decision.cdi_weight)} · ${pct(data.summary.cdi_return)}</span></div></div></details>`}
    <p class="live-quality">Fechamentos ajustados de fonte pública secundária e CDI oficial do BCB. Números provisórios até a conciliação integral B3/CVM. A rotina não troca ativos, não altera a seleção anual e não usa LLM para calcular retornos.</p>
  </div>`;
  attachLiveChart(host, data.series, primaryKey, copy);
}

(async function initialiseLivePortfolio() {
  const hosts = [...document.querySelectorAll("#live-portfolio, [data-live-portfolio]")];
  if (!hosts.length) return;
  const copy = liveCopy();
  try {
    const [liveResponse, decisionResponse] = await Promise.all([
      fetch("./live_performance.json", { cache: "no-store" }),
      fetch("./current_decision_2026.json", { cache: "no-store" }),
    ]);
    if (!liveResponse.ok || !decisionResponse.ok) throw new Error(copy.failed);
    const [data, decision] = await Promise.all([liveResponse.json(), decisionResponse.json()]);
    hosts.forEach(host => renderLivePortfolio(host, data, decision));
  } catch (_) {
    hosts.forEach(host => { host.innerHTML = `<p class="live-error">${copy.failed}</p>`; });
  }
}());
