// A carteira do ano corrente na home. Lê os documentos que o monitor diário
// publica — um por perfil — e mostra o que cada livro carrega e quanto rendeu
// desde a decisão de janeiro. Não recalcula nada: se o número aqui divergir do
// arquivo, é o arquivo que manda.
(() => {
  const host = document.querySelector("#carteira-2026-cards");
  if (!host) return;
  const note = document.querySelector("#carteira-2026-note");
  const LABELS = { conservador: "Conservador", equilibrado: "Equilibrado", arrojado: "Arrojado" };
  const pct = (v, d = 2) => `${(v * 100).toLocaleString("pt-BR", { minimumFractionDigits: d, maximumFractionDigits: d })}%`;
  const escapeHtml = value => String(value).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const dateBr = iso => iso ? iso.split("-").reverse().join("/") : "—";

  const load = async name => {
    const response = await fetch(`./${name}`, { cache: "no-store" });
    if (!response.ok) throw new Error(name);
    return response.json();
  };

  Promise.all([
    load("live_profiles_2026.json"),
    ...Object.keys(LABELS).map(p => load(`live_performance_${p}.json`)),
    ...Object.keys(LABELS).map(p => load(`current_decision_2026_${p}.json`)),
  ]).then(([summary, ...rest]) => {
    const perfis = Object.keys(LABELS);
    const live = Object.fromEntries(perfis.map((p, i) => [p, rest[i]]));
    const books = Object.fromEntries(perfis.map((p, i) => [p, rest[perfis.length + i]]));

    host.innerHTML = `<div class="carteira-2026-grid">${perfis.map(p => {
      const l = live[p], b = books[p];
      const acoes = b.holdings.filter(h => h.ticker !== "IVVB11");
      const retorno = l.summary.portfolio_return;
      const nomes = acoes.map(h => escapeHtml(h.ticker)).join(" · ");
      return `<article class="carteira-2026-card">
        <header><b>${LABELS[p]}</b><small>${pct(b.declared.maximum_equity_weight, 0)} em ações · ${acoes.length} emissores</small></header>
        <strong class="${retorno >= 0 ? "up" : "down"}">${retorno >= 0 ? "+" : ""}${pct(retorno)}</strong>
        <span class="carteira-2026-since">desde ${dateBr(b.decision_date)} · até ${dateBr(l.through)}</span>
        <p class="carteira-2026-names">${nomes}</p>
        <p class="carteira-2026-split">Ações ${pct(acoes.reduce((t, h) => t + h.weight, 0), 0)} · S&amp;P 500 ${pct(b.holdings.filter(h => h.ticker === "IVVB11").reduce((t, h) => t + h.weight, 0), 0)} · CDI ${pct(b.cdi_weight, 0)}</p>
      </article>`;
    }).join("")}</div>`;

    if (note) {
      note.textContent = `Decisão de ${dateBr(summary.decision_date)} sob a política ${summary.policy}, `
        + `congelada por ${summary.approved_by}. Retorno parcial a preço de fechamento da B3, sem ajuste de `
        + `proventos: subestima ações que pagaram dividendos. A amostra confirmatória da política começa no `
        + `primeiro pregão de 2027 — este ano é reconstrução acompanhada, não validação prospectiva.`;
    }
  }).catch(() => {
    host.innerHTML = `<p class="carteira-2026-names">O acompanhamento de 2026 não pôde ser carregado agora.</p>`;
  });
})();
