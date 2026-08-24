(async function () {
  const metricNodes = document.querySelectorAll("[data-version-metric]");
  const decisionHosts = document.querySelectorAll("[data-strategy-decisions]");
  document.querySelectorAll(".comparison-matrix tbody tr").forEach(row => {
    if (row.cells?.[0]?.textContent.trim() !== "Status" || row.cells.length < 3) return;
    row.cells[1].textContent = "Base anual da pesquisa";
    row.cells[2].textContent = "Estratégia principal em acompanhamento";
  });
  if (!metricNodes.length && !decisionHosts.length) return;

  const pct = (value, digits = 1, signed = false) => {
    if (!Number.isFinite(Number(value))) return "—";
    const number = Number(value) * 100;
    const prefix = signed && number > 0 ? "+" : "";
    return `${prefix}${number.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
  };
  const date = value => new Date(`${value}T12:00:00`).toLocaleDateString("pt-BR");
  const money = value => Number(value).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
  const stateLabel = { normal: "Normal", alerta: "Alerta", severo: "Severo" };

  function renderAllocation(allocation) {
    return allocation.map(item => `<span><b>${item.ticker === "TITULO_CDI" ? "CDI" : item.ticker}</b> ${pct(item.weight, 2)}</span>`).join("");
  }

  function renderTransition(item) {
    const signal = [
      Number.isFinite(item.observed_market_drawdown) ? `queda ${pct(item.observed_market_drawdown, 1)}` : "",
      Number.isFinite(item.observed_market_volatility) ? `volatilidade ${pct(item.observed_market_volatility, 1)}` : "",
    ].filter(Boolean).join(" · ");
    return `<li><time>${date(item.effective_on)}</time><div><strong>${stateLabel[item.from_state]} → ${stateLabel[item.to_state]}</strong><p>${item.reason}. Meta de ${pct(item.target_equity_weight, 0)} em ações${signal ? ` · ${signal}` : ""}.</p><div class="transition-allocation">${renderAllocation(item.target_allocation)}</div></div></li>`;
  }

  function renderDecisionLedger(host, ledger) {
    const mode = host.dataset.strategyDecisions === "b2" ? "b2" : "b1";
    const rows = [...ledger.annual_decisions].reverse().map(item => {
      const strategyReturn = mode === "b2" ? item.benevente2_return : item.benevente1_return;
      const riskSummary = mode === "b2"
        ? `<span>${item.days_alert} dias em alerta</span><span>${item.days_severe} dias em estado severo</span>`
        : `<span>Cesta mantida até ${date(item.holding_end_exclusive)}</span>`;
      const transitions = mode === "b2" && item.risk_transitions.length
        ? `<div class="historical-transitions"><h5>Alterações de exposição</h5><ol>${item.risk_transitions.map(renderTransition).join("")}</ol></div>`
        : mode === "b2" ? `<p class="no-transition">Não houve mudança de estado de risco neste ciclo.</p>` : "";
      return `<details class="annual-decision"${item.year === 2025 ? " open" : ""}>
        <summary><div><strong>${item.year}</strong><span>decisão em ${date(item.decision_date)}</span></div><div class="annual-result"><b>${pct(strategyReturn, 1, true)}</b><small>${mode === "b2" ? "Benevente 2" : "Benevente 1"}</small></div></summary>
        <div class="annual-decision-body">
          <div class="annual-comparison"><span>CDI <b>${pct(item.cdi_return, 1, true)}</b></span><span>MVO <b>${pct(item.mvo_return, 1, true)}</b></span><span>Ibovespa <b>${pct(item.ibovespa_return, 1, true)}</b></span></div>
          <div class="annual-allocation">${renderAllocation(item.allocation)}</div>
          <div class="annual-meta">${riskSummary}<span>${item.eligible_universe_size} ativos elegíveis</span><span>custo estimado ${money(item.estimated_cost_brl)}</span></div>
          ${transitions}
        </div>
      </details>`;
    }).join("");
    host.innerHTML = `<div class="decision-ledger-intro"><span>2015–2025</span><strong>11 carteiras anuais · ${mode === "b2" ? "38 alterações de risco registradas" : "pesos registrados antes de cada resultado"}</strong></div>${rows}`;
  }

  try {
    const [evidenceResponse, ledgerResponse] = await Promise.all([
      fetch("./annual_research.json", { cache: "no-store" }),
      fetch("./strategy_decisions.json", { cache: "no-store" }),
    ]);
    if (!evidenceResponse.ok || !ledgerResponse.ok) throw new Error("Não foi possível carregar a evidência.");
    const [data, ledger] = await Promise.all([evidenceResponse.json(), ledgerResponse.json()]);
    const evidence = data.meta.evidence;
    const experiment = data.meta.benevente2;
    const b1 = experiment.full_period_metrics["Benevente 1"];
    const b2 = experiment.training_only_selection.full_period_metrics;
    const references = experiment.full_period_metrics;
    const values = {
      "b1-cagr": pct(b1.cagr), "b1-cumulative": pct(b1.cumulative_return, 1, true),
      "b1-drawdown": pct(b1.max_drawdown), "b1-volatility": pct(b1.annual_volatility),
      "b1-after-tax": pct(evidence.strategy_cagr_after_tax), "b2-cagr": pct(b2.cagr),
      "b2-cumulative": pct(b2.cumulative_return, 1, true), "b2-drawdown": pct(b2.max_drawdown),
      "b2-volatility": pct(b2.annual_volatility), "cdi-cagr": pct(references.CDI.cagr),
      "cdi-cumulative": pct(references.CDI.cumulative_return, 1, true),
      "mvo-cagr": pct(references.MVO.cagr), "ibov-cagr": pct(references.Ibovespa.cagr),
      "ibov-cumulative": pct(references.Ibovespa.cumulative_return, 1, true),
      "b2-holdout-cagr": pct(experiment.training_only_selection.holdout_2019_2025_metrics.cagr),
      "b1-holdout-cagr": pct(experiment.holdout_2019_2025_metrics["Benevente 1"].cagr),
      "b2-covid": pct(experiment.covid_2020_trace_for_training_selected_candidate.annual_returns["Benevente 2"]),
      "b1-covid": pct(experiment.covid_2020_trace_for_training_selected_candidate.annual_returns["Benevente 1"]),
      "b2-pvalue": experiment.training_only_selection.paired_annual_test_2019_2025.p_value.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 }),
    };
    metricNodes.forEach(node => { node.textContent = values[node.dataset.versionMetric] || "—"; });
    decisionHosts.forEach(host => renderDecisionLedger(host, ledger));
    document.querySelectorAll("[data-tax-sensitivity]").forEach(host => {
      const rows = experiment.intrayear_tax_estimate?.capital_sensitivity || [];
      const selected = rows.filter(item => [50000, 100000, 250000, 1000000].includes(Number(item.initial_capital_brl)));
      host.innerHTML = selected.map(item => `<tr><td>${money(item.initial_capital_brl)}</td><td>${money(item.estimated_incremental_tax_brl)}</td><td>${pct(item.cagr_after_incremental_tax)}</td><td>${money(item.estimated_terminal_wealth_after_incremental_tax_brl)}</td></tr>`).join("");
    });
  } catch (_) {
    metricNodes.forEach(node => { node.textContent = "—"; });
    decisionHosts.forEach(host => { host.innerHTML = "<p class=\"live-error\">O histórico de decisões não pôde ser carregado.</p>"; });
    const note = document.querySelector("[data-evidence-error]");
    if (note) note.textContent = "A evidência não pôde ser carregada agora. Consulte a página principal.";
  }
}());
