/* Renders the declared profile ladder from the frozen v2 registration.
 *
 * The site used to state one curve because there was one published strategy.
 * There are now three declared policies, so a page that shows a single number
 * would be showing a strategy nobody can choose. Every value here comes from
 * ladder_v2.json, which is generated from the registration itself.
 */
(async function () {
  const hosts = document.querySelectorAll("[data-ladder]");
  const sealNodes = document.querySelectorAll("[data-ladder-seal]");
  if (!hosts.length && !sealNodes.length) return;

  const pct = (value, digits = 2) => {
    if (!Number.isFinite(Number(value))) return "—";
    return `${(Number(value) * 100).toLocaleString("pt-BR", {
      minimumFractionDigits: digits, maximumFractionDigits: digits,
    })}%`;
  };
  const count = (value, digits = 1) => Number(value).toLocaleString("pt-BR", {
    minimumFractionDigits: digits, maximumFractionDigits: digits,
  });
  const LABELS = { conservador: "Conservador", equilibrado: "Equilibrado", arrojado: "Arrojado" };

  const fail = message => {
    hosts.forEach(host => { host.textContent = message; host.classList.add("ladder-error"); });
    sealNodes.forEach(node => { node.textContent = "—"; });
  };

  let data;
  try {
    const response = await fetch("./ladder_v2.json", { cache: "no-store" });
    if (!response.ok) throw new Error("indisponível");
    data = await response.json();
  } catch (_) {
    fail("A escada declarada não pôde ser carregada agora.");
    return;
  }

  /* The registration is written in English because it is a machine artefact
   * read by auditors; the page is read by people in Portuguese. Translating a
   * known year is safe, and falling back to the raw string keeps the page from
   * inventing one if the registration ever says something else. */
  const confirmatory = raw => {
    const match = /(\d{4})/.exec(String(raw || ""));
    return match ? `primeiro pregão de ${match[1]}` : String(raw || "—");
  };

  sealNodes.forEach(node => {
    const field = node.dataset.ladderSeal;
    const values = {
      sha: String(data.registration_sha256 || "").slice(0, 16),
      approved: data.approved_by || "—",
      window: `${data.window.first_decision_year}–${data.window.last_decision_year}`,
      confirmatory: confirmatory(data.confirmatory_sample_starts),
    };
    node.textContent = values[field] || "—";
  });

  hosts.forEach(host => {
    const mode = host.dataset.ladder === "benevente2" ? "benevente2" : "benevente1";
    const rows = Object.keys(LABELS).filter(key => data.profiles[key]).map(key => {
      const item = data.profiles[key];
      const metrics = item[mode];
      const declared = item.declared;
      return `<tr>
        <th scope="row">${LABELS[key]}</th>
        <td>${pct(declared.maximum_equity_weight, 0)}</td>
        <td>${declared.top_assets}</td>
        <td>${pct(declared.global_share_of_portfolio, 0)}</td>
        <td class="ladder-strong">${pct(metrics.cagr)}</td>
        <td>${pct(metrics.annual_volatility)}</td>
        <td class="ladder-strong">${pct(metrics.max_drawdown)}</td>
      </tr>`;
    }).join("");

    const references = ["CDI", "Ibovespa"].filter(name => data.references[name]?.cagr !== undefined)
      .map(name => `<tr class="ladder-reference">
        <th scope="row">${name}</th><td>—</td><td>—</td><td>—</td>
        <td>${pct(data.references[name].cagr)}</td>
        <td>${pct(data.references[name].annual_volatility)}</td>
        <td>${pct(data.references[name].max_drawdown)}</td>
      </tr>`).join("");

    const spread = Object.keys(LABELS).filter(key => data.profiles[key])
      .map(key => `${LABELS[key]}: ${count(data.profiles[key].average_positions)} emissores em `
        + `${count(data.profiles[key].average_sectors)} setores`).join(" · ");

    host.innerHTML = `<div class="ladder-wrap"><table class="ladder-table">
        <caption>${mode === "benevente2"
          ? "Seleção anual, perna global e proteção intranual"
          : "Seleção anual e perna global, sem proteção intranual"} · ${data.window.first_decision_year}–${data.window.last_decision_year}</caption>
        <thead><tr>
          <th scope="col">Perfil</th><th scope="col">Ações</th><th scope="col">Emissores</th>
          <th scope="col">Global</th><th scope="col">Retorno a.a.</th>
          <th scope="col">Volatilidade</th><th scope="col">Maior queda</th>
        </tr></thead>
        <tbody>${rows}${references}</tbody>
      </table></div>
      <p class="ladder-note">Média observada: ${spread}. Nenhum setor da CVM ultrapassa três emissores.</p>`;
  });
})();
