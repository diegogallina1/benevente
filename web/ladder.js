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

/* Explorador de composição do Benevente Alpha.
 *
 * Uma escada só é auditável se o leitor puder ver o que cada perfil carregou,
 * quanto, por que entrou e o que aconteceu depois. O retorno realizado fica numa
 * coluna à parte de propósito: é o único número que a decisão não podia ter
 * usado, e misturá-lo com o score e o retorno de doze meses — que eram
 * observáveis em janeiro — apagaria justamente a fronteira que o método defende.
 */
(async function () {
  const hosts = document.querySelectorAll("[data-alpha-composition]");
  if (!hosts.length) return;

  const pct = (value, digits = 2) => Number.isFinite(Number(value))
    ? `${(Number(value) * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`
    : "—";
  const LABELS = { conservador: "Conservador", equilibrado: "Equilibrado", arrojado: "Arrojado" };
  const ACTIONS = {
    entered: "entrou", maintained: "mantido", increased: "aumentou",
    reduced: "reduziu", exited: "saiu", not_held: "fora",
  };

  let data;
  try {
    const response = await fetch("./alpha_composition.json", { cache: "no-store" });
    if (!response.ok) throw new Error("indisponível");
    data = await response.json();
  } catch (_) {
    hosts.forEach(host => { host.textContent = "A composição auditável não pôde ser carregada agora."; });
    return;
  }

  const years = data.profiles.conservador.map(item => item.decision_year).sort((a, b) => b - a);
  let activeProfile = "equilibrado";
  let activeYear = years[0];

  const render = host => {
    const block = (data.profiles[activeProfile] || []).find(item => item.decision_year === activeYear);
    if (!block) { host.textContent = "Sem decisão registrada para esta combinação."; return; }
    const rows = block.positions.map(row => `<tr>
        <th scope="row">${row.ticker.replace(".SA", "")}</th>
        <td>${pct(row.weight)}</td>
        <td><span class="alpha-action alpha-${row.action}">${ACTIONS[row.action] || row.action}</span></td>
        <td>${row.score === null ? "—" : row.score.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 })}</td>
        <td>${pct(row.trailing_12m, 1)}</td>
        <td>${pct(row.trailing_vol, 1)}</td>
        <td class="alpha-after">${pct(row.realised_next_year, 1)}</td>
      </tr>`).join("");

    host.innerHTML = `
      <div class="alpha-controls">
        <div role="group" aria-label="Perfil">${Object.keys(LABELS).map(key =>
          `<button type="button" data-profile="${key}" class="${key === activeProfile ? "on" : ""}">${LABELS[key]}</button>`).join("")}</div>
        <label>Decisão de <select data-year>${years.map(year =>
          `<option value="${year}"${year === activeYear ? " selected" : ""}>${year}</option>`).join("")}</select></label>
      </div>
      <div class="alpha-split">
        <span style="width:${(block.domestic_equity * 100).toFixed(2)}%">Ações BR ${pct(block.domestic_equity, 0)}</span>
        <span style="width:${(block.global_sleeve * 100).toFixed(2)}%">Global ${pct(block.global_sleeve, 0)}</span>
        <span style="width:${(block.cash * 100).toFixed(2)}%">CDI ${pct(block.cash, 0)}</span>
      </div>
      <div class="ladder-wrap"><table class="ladder-table alpha-table">
        <caption>${LABELS[activeProfile]} · decisão de ${block.decision_date} · ${block.positions.length} emissores</caption>
        <thead><tr>
          <th scope="col">Emissor</th><th scope="col">Peso</th><th scope="col">Ação</th>
          <th scope="col">Score</th><th scope="col">12m antes</th><th scope="col">Vol. 12m</th>
          <th scope="col">Retorno seguinte</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
      <p class="ladder-note">As quatro primeiras colunas eram observáveis em janeiro, na data da decisão.
      <b>Retorno seguinte</b> é o que aconteceu depois e está separado de propósito: é o único número que a
      decisão não podia ter usado.</p>`;

    host.querySelectorAll("[data-profile]").forEach(button => {
      button.addEventListener("click", () => { activeProfile = button.dataset.profile; render(host); });
    });
    host.querySelector("[data-year]")?.addEventListener("change", event => {
      activeYear = Number(event.target.value); render(host);
    });
  };

  hosts.forEach(render);
})();
