(async function () {
  const nodes = document.querySelectorAll("[data-version-metric]");
  if (!nodes.length) return;

  const pct = (value, digits = 1, signed = false) => {
    if (!Number.isFinite(value)) return "—";
    const number = value * 100;
    const prefix = signed && number > 0 ? "+" : "";
    return `${prefix}${number.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
  };

  try {
    const response = await fetch("./annual_research.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Não foi possível carregar a evidência.");
    const data = await response.json();
    const evidence = data.meta.evidence;
    const experiment = data.meta.benevente2;
    const b1 = experiment.full_period_metrics["Benevente 1"];
    const b2 = experiment.training_only_selection.full_period_metrics;
    const references = experiment.full_period_metrics;
    const values = {
      "b1-cagr": pct(b1.cagr),
      "b1-cumulative": pct(b1.cumulative_return, 1, true),
      "b1-drawdown": pct(b1.max_drawdown),
      "b1-volatility": pct(b1.annual_volatility),
      "b1-after-tax": pct(evidence.strategy_cagr_after_tax),
      "b2-cagr": pct(b2.cagr),
      "b2-cumulative": pct(b2.cumulative_return, 1, true),
      "b2-drawdown": pct(b2.max_drawdown),
      "b2-volatility": pct(b2.annual_volatility),
      "cdi-cagr": pct(references.CDI.cagr),
      "mvo-cagr": pct(references.MVO.cagr),
      "ibov-cagr": pct(references.Ibovespa.cagr),
      "b2-holdout-cagr": pct(experiment.training_only_selection.holdout_2019_2025_metrics.cagr),
      "b1-holdout-cagr": pct(experiment.holdout_2019_2025_metrics["Benevente 1"].cagr),
      "b2-covid": pct(experiment.covid_2020_trace_for_training_selected_candidate.annual_returns["Benevente 2"]),
      "b1-covid": pct(experiment.covid_2020_trace_for_training_selected_candidate.annual_returns["Benevente 1"]),
      "b2-pvalue": experiment.training_only_selection.paired_annual_test_2019_2025.p_value.toLocaleString("pt-BR", { minimumFractionDigits: 3, maximumFractionDigits: 3 })
    };
    nodes.forEach((node) => { node.textContent = values[node.dataset.versionMetric] || "—"; });
  } catch (error) {
    nodes.forEach((node) => { node.textContent = "—"; });
    const note = document.querySelector("[data-evidence-error]");
    if (note) note.textContent = "A evidência não pôde ser carregada agora. Consulte a página principal.";
  }
}());
