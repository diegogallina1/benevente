// Both paper pages read the same published decision file the product uses, so
// a number shown to a reviewer is the number the engine wrote. Nothing here is
// hardcoded from a screenshot.
const pct = value => `${value >= 0 ? "+" : ""}${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
const plain = value => `${(value * 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}%`;
const dateBr = value => {
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleDateString("pt-BR");
};

async function renderLivePortfolio() {
  const host = document.querySelector("#live-portfolio");
  if (!host) return;
  let data;
  try {
    data = await (await fetch("./current_decision_2026.json")).json();
  } catch (_) {
    host.innerHTML = "<p>Não foi possível carregar a decisão de 2026.</p>";
    return;
  }
  const monitor = data.monitoring?.profiles?.benevente || Object.values(data.monitoring?.profiles || {})[0];
  const holdings = [...(data.holdings || [])].sort((a, b) => b.weight - a.weight);
  const maxWeight = Math.max(data.cdi_weight || 0, ...holdings.map(item => item.weight), 0.01);
  const bar = (weight, cash) =>
    `<div class="bar${cash ? " cash" : ""}"><i style="width:${Math.max(2, (weight / maxWeight) * 100)}%"></i></div>`;
  const rows = holdings.map(item =>
    `<div class="paper-holding"><b>${item.ticker}</b>${bar(item.weight, false)}<span>${plain(item.weight)}</span></div>`).join("");
  const cash = `<div class="paper-holding"><b>CDI</b>${bar(data.cdi_weight, true)}<span>${plain(data.cdi_weight)}</span></div>`;
  const partial = monitor ? `
    <div class="paper-metrics">
      <div class="paper-metric${monitor.portfolio_partial_return < 0 ? " negative" : ""}">
        <span>Carteira no ano</span><b>${pct(monitor.portfolio_partial_return)}</b>
        <small>até ${dateBr(data.monitoring.through)}</small></div>
      <div class="paper-metric${monitor.equity_price_return < 0 ? " negative" : ""}">
        <span>Parcela de ações</span><b>${pct(monitor.equity_price_return)}</b>
        <small>${plain(monitor.equity_weight)} do capital</small></div>
      <div class="paper-metric"><span>Parcela CDI</span><b>${pct(monitor.cdi_return)}</b>
        <small>${plain(monitor.cdi_weight)} do capital</small></div>
    </div>` : "";
  host.innerHTML = `
    <div class="paper-portfolio">
      <h3>Carteira recomendada para 2026</h3>
      <p>Congelada em ${dateBr(data.decision_date)} com os dados disponíveis naquela data, a partir de
      ${data.universe.eligible_after_screen} ativos aprovados na triagem entre
      ${data.universe.equities_at_decision} ações do universo B3. Status: <b>${data.status.replace(/_/g, " ")}</b>.</p>
      <div class="paper-holdings">${rows}${cash}</div>
      ${partial}
      <p><small>${data.monitoring?.label || ""}</small></p>
    </div>`;
}

renderLivePortfolio();
