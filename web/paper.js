// Both paper pages read the same published decision file the product uses, so
// a number shown to a reviewer is the number the engine wrote. Nothing here is
// hardcoded from a screenshot. The two pages address different audiences in
// different languages, so the copy is keyed off the document language.
const PAPER_STRINGS = {
  "pt-BR": {
    locale: "pt-BR",
    title: "Carteira recomendada para 2026",
    frozen: (date, eligible, universe, status) =>
      `Congelada em ${date} com os dados disponíveis naquela data, a partir de ${eligible} ativos aprovados na ` +
      `triagem entre ${universe} ações do universo B3. Status: <b>${status}</b>.`,
    cash: "CDI",
    portfolio: "Carteira no ano",
    equity: "Parcela de ações",
    reserve: "Parcela CDI",
    through: date => `até ${date}`,
    share: value => `${value} do capital`,
    failed: "Não foi possível carregar a decisão de 2026.",
  },
  en: {
    locale: "en-GB",
    title: "Live portfolio for 2026",
    frozen: (date, eligible, universe, status) =>
      `Frozen on ${date} using only information available on that date, selected from ${eligible} assets that ` +
      `cleared the screen out of ${universe} listed equities. Status: <b>${status}</b>.`,
    cash: "Cash (CDI)",
    portfolio: "Portfolio, year to date",
    equity: "Equity sleeve",
    reserve: "Cash sleeve",
    through: date => `through ${date}`,
    share: value => `${value} of capital`,
    failed: "The 2026 decision could not be loaded.",
  },
};

function paperStrings() {
  const lang = (document.documentElement.lang || "pt-BR").toLowerCase();
  return lang.startsWith("en") ? PAPER_STRINGS.en : PAPER_STRINGS["pt-BR"];
}

async function renderLivePortfolio() {
  const host = document.querySelector("#live-portfolio");
  if (!host) return;
  const text = paperStrings();
  const pct = value => `${value >= 0 ? "+" : ""}${(value * 100).toLocaleString(text.locale, { maximumFractionDigits: 2 })}%`;
  const plain = value => `${(value * 100).toLocaleString(text.locale, { maximumFractionDigits: 2 })}%`;
  const formatDate = value => {
    const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
    return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleDateString(text.locale);
  };
  let data;
  try {
    data = await (await fetch("./current_decision_2026.json")).json();
  } catch (_) {
    host.innerHTML = `<p>${text.failed}</p>`;
    return;
  }
  const monitor = data.monitoring?.profiles?.benevente || Object.values(data.monitoring?.profiles || {})[0];
  const holdings = [...(data.holdings || [])].sort((a, b) => b.weight - a.weight);
  const maxWeight = Math.max(data.cdi_weight || 0, ...holdings.map(item => item.weight), 0.01);
  const bar = (weight, cash) =>
    `<div class="bar${cash ? " cash" : ""}"><i style="width:${Math.max(2, (weight / maxWeight) * 100)}%"></i></div>`;
  const rows = holdings.map(item =>
    `<div class="paper-holding"><b>${item.ticker}</b>${bar(item.weight, false)}<span>${plain(item.weight)}</span></div>`).join("");
  const cash = `<div class="paper-holding"><b>${text.cash}</b>${bar(data.cdi_weight, true)}<span>${plain(data.cdi_weight)}</span></div>`;
  const partial = monitor ? `
    <div class="paper-metrics">
      <div class="paper-metric${monitor.portfolio_partial_return < 0 ? " negative" : ""}">
        <span>${text.portfolio}</span><b>${pct(monitor.portfolio_partial_return)}</b>
        <small>${text.through(formatDate(data.monitoring.through))}</small></div>
      <div class="paper-metric${monitor.equity_price_return < 0 ? " negative" : ""}">
        <span>${text.equity}</span><b>${pct(monitor.equity_price_return)}</b>
        <small>${text.share(plain(monitor.equity_weight))}</small></div>
      <div class="paper-metric"><span>${text.reserve}</span><b>${pct(monitor.cdi_return)}</b>
        <small>${text.share(plain(monitor.cdi_weight))}</small></div>
    </div>` : "";
  const note = document.documentElement.lang.toLowerCase().startsWith("en")
    ? "Partial-year equity figures use official B3 closing prices and exclude cash distributions; the cash sleeve uses the official daily CDI series."
    : (data.monitoring?.label || "");
  host.innerHTML = `
    <div class="paper-portfolio">
      <h3>${text.title}</h3>
      <p>${text.frozen(formatDate(data.decision_date), data.universe.eligible_after_screen,
                       data.universe.equities_at_decision, data.status.replace(/_/g, " "))}</p>
      <div class="paper-holdings">${rows}${cash}</div>
      ${partial}
      <p><small>${note}</small></p>
    </div>`;
}

renderLivePortfolio();
