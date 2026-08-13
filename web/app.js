const profiles = {
  conservador: { equity: 35, issuer: 10, review: "trimestral", mix: [["Ações elegíveis", 35], ["CDI / defensivo", 65]], insight: "A prioridade é preservar margem de segurança. A parcela variável fica limitada e qualquer tese deve justificar o risco adicional." },
  moderado: { equity: 55, issuer: 12, review: "trimestral", mix: [["Ações elegíveis", 55], ["CDI / defensivo", 45]], insight: "Há espaço para ações que passam no filtro, sem transformar retorno passado em promessa. O CDI preserva flexibilidade para revisar a tese." },
  arrojado: { equity: 80, issuer: 15, review: "semestral", mix: [["Ações elegíveis", 80], ["CDI / defensivo", 20]], insight: "Aceita maior oscilação, com mais emissores para tornar o limite de renda variável viável sem eliminar diversificação." }
};

let researchData = null;
let forecastData = null;
let universeData = null;
let currentDecisionData = null;
let fundPresetsData = null;
const comparisonWindows = { 1: 1, 3: 3, 5: 5, 11: 11 };

const modelSteps = {
  policy: { number:"01 · POLÍTICA", title:"A política vem antes do ativo.", text:"O responsável define patrimônio, perfil, horizonte, concentração máxima, limite de renda variável, perda tolerada, custo e frequência de revisão.", uses:"Perfil, horizonte e limites explícitos", blocks:"Pesos que ultrapassem a política", produces:"Uma política versionada por proposta", rule:"<strong>Regra:</strong> sem reconhecimento explícito da política, não há proposta operacional." },
  data: { number:"02 · DADOS", title:"Uma informação só entra quando era pública.", text:"Cada fundamento tem data contábil e data de divulgação. Preços, liquidez, lote e capitalização têm data e fonte registradas.", uses:"CVM ITR/DFP, BCB e dados de mercado", blocks:"Dados futuros, nulos ou sem fonte", produces:"Pacote de dados da decisão", rule:"<strong>Regra:</strong> o documento divulgado depois da decisão é rejeitado." },
  screen: { number:"03 · FILTRO", title:"Primeiro eliminar, depois ranquear.", text:"O filtro determinístico busca valor e qualidade. Para não financeiras: caixa, ROIC, dívida e cobertura; para financeiras: ROE e preço sobre valor patrimonial.", uses:"Liquidez, valor, rentabilidade e solvência", blocks:"Ativos frágeis ou com métrica ausente", produces:"Tela de elegibilidade e motivo de bloqueio", rule:"<strong>Regra:</strong> ausência de dado comparável é reprovação, não uma inferência favorável." },
  optimizer: { number:"04 · OTIMIZAÇÃO", title:"Otimizar não é adivinhar.", text:"Somente os ativos elegíveis entram numa otimização restrita. Os pesos obedecem limites por emissor, exposição a ações e uma reserva residual em CDI.", uses:"Retornos históricos e restrições da política", blocks:"Concentração e ativos reprovados", produces:"Pesos, custos e caixa residual", rule:"<strong>Regra:</strong> uma LLM não define pesos e não pode mudar uma regra rígida." },
  review: { number:"05 · REVISÃO", title:"O resultado é uma proposta, não uma ordem.", text:"A instituição revisa tese, riscos, pesos e custos. Se decidir implementar, registra a operação e confere a nota de corretagem depois.", uses:"Proposta, evidências e custo estimado", blocks:"Execução automática", produces:"Carteira-sombra e registro de decisão", rule:"<strong>Regra:</strong> resultados prospectivos ficam separados do backtest histórico." }
};

let currentProfile = "moderado";
let selectedCurves = new Set();
const extraSeries = { 1: {}, 3: {}, 5: {}, 11: {} };
const addedSeries = new Map();
let chartSource = "ticker";
let chartZoom = 1;
let chartFocus = null;
let chartScale = "linear";
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const colors = { "Benevente Quant AI":"#0f766e", "MVO clássico (elegível)":"#ae8871", "MVO clássico":"#ae8871", "CDI":"#3b779a", "Ibovespa":"#7a8490" };
const extraColors = ["#9c4f2a", "#7856a3", "#b87418", "#2a7c91"];
const formatDateBr = value => {
  const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
  return Number.isNaN(date.valueOf()) ? String(value) : date.toLocaleDateString("pt-BR");
};

function annualCurve(period) {
  if (!researchData || !comparisonWindows[period]) return null;
  const rows = researchData.annual.slice(-comparisonWindows[period]);
  if (!rows.length) return null;
  const dates = [rows[0].decision_date, ...rows.map(item => item.holding_end_exclusive)];
  const series = { "Benevente Quant AI": [100], "MVO clássico (elegível)": [100], CDI: [100] };
  rows.forEach(item => {
    series["Benevente Quant AI"].push(+(series["Benevente Quant AI"].at(-1) * (1 + item.net_return)).toFixed(4));
    series["MVO clássico (elegível)"].push(+(series["MVO clássico (elegível)"].at(-1) * (1 + item.mvo_eligible_net_return)).toFixed(4));
    series.CDI.push(+(series.CDI.at(-1) * (1 + item.cdi_net_return)).toFixed(4));
  });
  const ibovespa = researchData.meta.ibovespa;
  const fullDates = ibovespa?.dates || [];
  const startIndex = fullDates.indexOf(dates[0]);
  if (startIndex >= 0 && ibovespa?.values_base_100?.length >= startIndex + dates.length && fullDates.slice(startIndex, startIndex + dates.length).every((date, index) => date === dates[index])) {
    const window = ibovespa.values_base_100.slice(startIndex, startIndex + dates.length);
    series[ibovespa.label] = window.map(value => +(value / window[0] * 100).toFixed(4));
  }
  return { dates, series };
}
function profileDataset(period) {
  const profileCurve = researchData?.profile_curves?.[activeProfileKey()];
  if (!profileCurve || !comparisonWindows[period]) return annualCurve(period);
  const keep = Math.min(comparisonWindows[period] + 1, profileCurve.dates.length);
  const dates = profileCurve.dates.slice(-keep);
  const series = Object.fromEntries(Object.entries(profileCurve.series).map(([name, values]) => [name, values.slice(-keep)]));
  const ibovespa = researchData?.meta?.ibovespa;
  const startIndex = ibovespa?.dates?.indexOf(dates[0]) ?? -1;
  if (startIndex >= 0 && ibovespa?.values_base_100?.length >= startIndex + dates.length
    && ibovespa.dates.slice(startIndex, startIndex + dates.length).every((date, index) => date === dates[index])) {
    const window = ibovespa.values_base_100.slice(startIndex, startIndex + dates.length);
    series[ibovespa.label] = window.map(value => +(value / window[0] * 100).toFixed(4));
  }
  return {
    dates,
    series,
  };
}
function seriesFor(period) {
  const base = profileDataset(period);
  return { ...(base?.series || {}), ...(extraSeries[period] || {}) };
}
function refreshExtraSeriesForPeriod(period) {
  const data = profileDataset(period);
  if (!data) return;
  extraSeries[period] = {};
  addedSeries.forEach((points, name) => {
    try { extraSeries[period][name] = normalizeSeriesOnCommonWindow(points, data.dates); } catch (_) { /* no common dates */ }
  });
}
function seriesColor(name, index = 0) { return colors[name] || (name.startsWith("Ibovespa") ? colors.Ibovespa : extraColors[index % extraColors.length]); }
function normalizeToDecisionDates(points, dates) {
  const ordered = points.filter(point => point?.date && Number.isFinite(Number(point.value))).map(point => ({ date: String(point.date).slice(0, 10), value: Number(point.value) })).sort((a, b) => a.date.localeCompare(b.date));
  let cursor = 0, latest = null;
  const values = dates.map(date => {
    while (cursor < ordered.length && ordered[cursor].date <= date) latest = ordered[cursor++].value;
    return latest;
  });
  const base = values.find(value => Number.isFinite(value) && value > 0);
  if (!base) throw new Error("A série não possui observação anterior às datas do gráfico.");
  return values.map(value => Number.isFinite(value) && value > 0 ? +(value / base * 100).toFixed(4) : null);
}

function normalizeSeriesOnCommonWindow(points, dates) {
  const normalized = normalizeToDecisionDates(points, dates);
  const firstIndex = normalized.findIndex(value => Number.isFinite(value));
  if (firstIndex < 0 || normalized.length - firstIndex < 2) throw new Error("A série precisa de pelo menos duas datas comuns com a janela selecionada.");
  return normalized.map((value, index) => index < firstIndex ? null : value);
}

function parseQuotaNumber(value) {
  const text = String(value ?? "").trim().replace(/\s/g, "");
  if (!text) return NaN;
  // CVM exports commonly use 1.234,56 while simple provider files use
  // 1234.56. Treat the comma as a decimal separator only when it exists.
  return Number(text.includes(",") ? text.replace(/\./g, "").replace(",", ".") : text);
}

function metricsForSeries(values, dates) {
  const observed = values.map((value, index) => ({ value, index })).filter(item => Number.isFinite(item.value) && item.value > 0);
  if (observed.length < 2) return null;
  const first = observed[0], last = observed.at(-1);
  const years = Math.max((new Date(dates[last.index]) - new Date(dates[first.index])) / 31557600000, 1 / 12);
  const cumulative = last.value / first.value - 1;
  const cagr = Math.pow(1 + cumulative, 1 / years) - 1;
  const returns = observed.slice(1).map((item, position) => item.value / observed[position].value - 1);
  const average = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const volatility = Math.sqrt(returns.reduce((sum, value) => sum + Math.pow(value - average, 2), 0) / Math.max(returns.length - 1, 1)) * Math.sqrt(12);
  let peak = -Infinity, drawdown = 0;
  observed.forEach(item => { peak = Math.max(peak, item.value); drawdown = Math.min(drawdown, item.value / peak - 1); });
  return { cagr, volatility, drawdown };
}

function pct(value, digits = 1) { return `${value >= 0 ? "+" : ""}${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`; }
function plainPct(value, digits = 1) { return `${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`; }
function selectedAnnualDecision() {
  const year = Number(document.querySelector("#decision-year")?.value);
  const profile = researchData?.profiles?.[activeProfileKey()];
  const rows = Array.isArray(profile) ? profile : profile?.annual || researchData?.annual || [];
  return rows.find(item => item.decision_year === year) || rows.at(-1);
}

function activeProfileKey() {
  return ({ conservador: "conservador", moderado: "equilibrado", arrojado: "arrojado" })[currentProfile] || "equilibrado";
}

function activePolicy() {
  const policy = profiles[currentProfile];
  return {
    ...policy,
    equity: Math.max(0, Math.min(100, Number(policy.equity) || 0)),
    issuer: Math.max(1, Math.min(100, Number(policy.issuer) || 1)),
  };
}

function activeProfileRows() {
  const profile = researchData?.profiles?.[activeProfileKey()];
  return Array.isArray(profile) ? profile : profile?.annual || researchData?.annual || [];
}

function renderProfileHistory() {
  const container = document.querySelector("#profile-history");
  if (!container || !researchData) return;
  const rows = activeProfileRows();
  if (!rows.length) { container.innerHTML = ""; return; }
  const label = ({ conservador: "Conservador", moderado: "Equilibrado", arrojado: "Arrojado" })[currentProfile];
  container.innerHTML = `<div class="profile-history-head"><div><span class="control-label">HISTÓRICO DA POLÍTICA</span><b>${label}</b><small>Resultado líquido de cada cesta anual congelada antes do período.</small></div><span>${rows.length} anos completos</span></div><div class="profile-year-grid">${rows.map(row => `<button type="button" class="profile-year ${String(selectedAnnualDecision()?.decision_year) === String(row.decision_year) ? "active" : ""}" data-year="${row.decision_year}"><small>${row.decision_year}</small><b>${pct(row.net_return)}</b><span>MVO ${pct(row.mvo_eligible_net_return)} · CDI ${pct(row.cdi_net_return)}</span></button>`).join("")}</div>`;
  container.querySelectorAll(".profile-year").forEach(button => button.addEventListener("click", () => {
    document.querySelector("#decision-year").value = button.dataset.year;
    renderAssetWorkbench(); renderProfileHistory();
  }));
}

function syncDecisionYears() {
  const select = document.querySelector("#decision-year");
  if (!select || !researchData) return;
  const previous = select.value;
  const rows = activeProfileRows();
  select.innerHTML = rows.map(item => `<option value="${item.decision_year}">${item.decision_year} · ${formatDateBr(item.decision_date)}</option>`).join("");
  select.value = rows.some(item => String(item.decision_year) === previous) ? previous : String(rows.at(-1)?.decision_year || "");
}

function renderAssetWorkbench() {
  if (!researchData) return;
  const decision = selectedAnnualDecision();
  if (!decision) return;
  const profileRun = researchData.profiles?.[activeProfileKey()];
  const holdingsSource = (!Array.isArray(profileRun) && profileRun?.holdings) || researchData.holdings;
  const transitionsSource = (!Array.isArray(profileRun) && profileRun?.transitions) || researchData.transitions;
  const holdings = holdingsSource.filter(item => item.decision_year === decision.decision_year);
  const transitions = transitionsSource.filter(item => item.decision_year === decision.decision_year);
  const equities = holdings.filter(item => item.ticker !== "TITULO_CDI");
  const equityWeight = equities.reduce((sum, item) => sum + item.weight, 0);
  const transitionByTicker = Object.fromEntries(transitions.map(item => [item.ticker, item]));
  document.querySelector("#dossier-policy").textContent = `Regra anual de ${String(researchData.meta.strategy || "valor e qualidade").toLowerCase()}. Até ${plainPct(decision.target_equity_weight)} em renda variável e ${plainPct(researchData.meta.protocol.maximum_asset_weight)} por emissor. O retorno foi apurado depois de ${formatDateBr(decision.decision_date)} e não influenciou a escolha.`;
  const coverage = researchData.meta.coverage;
  const source = researchData.meta.source_tier === "public_reproducible_research" ? "fonte pública de pesquisa" : "fonte qualificada";
  const series = coverage.price_tickers ? `${coverage.price_tickers.toLocaleString("pt-BR")} séries ajustadas` : "séries ajustadas";
  document.querySelector("#research-status").innerHTML = `<b>Pesquisa reproduzível, ainda não validada para uso institucional.</b><span>O painel usa ${series}, CDI do BCB e ${coverage.fundamental_snapshots?.toLocaleString("pt-BR") || "—"} demonstrações CVM disponíveis em cada decisão. Proventos, JCP e eventos societários ainda exigem reconciliação B3/CVM ou fonte licenciada.</span>`;
  document.querySelector("#asset-summary").innerHTML = `<div><small>DECISÃO</small><strong>${formatDateBr(decision.decision_date)}</strong><span>Carteira mantida até ${formatDateBr(decision.holding_end_exclusive)}.</span></div><div><small>RENDA VARIÁVEL</small><strong>${plainPct(equityWeight)}</strong><span>${equities.length} ativo(s) elegível(is). CDI completa a alocação.</span></div><div><small>RESULTADO POSTERIOR</small><strong>${pct(decision.net_return)}</strong><span>Após custo estimado de ${money.format(decision.estimated_cost_brl)}.</span></div>`;
  document.querySelector("#asset-grid").innerHTML = holdings.map(item => {
    const transition = transitionByTicker[item.ticker];
    const isCdi = item.ticker === "TITULO_CDI";
    const status = isCdi ? "Parcela CDI" : (item.decision_action_pt || "Mantido");
    const signal = item.trailing_12m_return_at_decision == null ? "Não aplicável" : plainPct(item.trailing_12m_return_at_decision);
    const volatility = item.trailing_12m_volatility_at_decision == null ? "Não aplicável" : plainPct(item.trailing_12m_volatility_at_decision);
    const currentReason = transition?.reason_pt || "Mantido segundo a política e a revisão anual.";
    const actionClass = ({ Entrada: "entered", Aumento: "increased", Redução: "reduced", Saída: "exited" })[status] || (isCdi ? "defensive" : "maintained");
    return `<article class="asset-card ${isCdi ? "defensive" : ""}"><div class="asset-card-top"><div><small>${isCdi ? "PARCELA DEFENSIVA" : "ATIVO ELEGÍVEL"}</small><h3>${isCdi ? "CDI" : item.ticker.replace(".SA", "")}</h3></div><span class="asset-status ${actionClass}">${status}</span></div><div class="asset-metrics"><div><small>PESO</small><b>${plainPct(item.weight)}</b></div><div><small>12M ANTERIOR</small><b>${signal}</b></div><div><small>VOL. 12M</small><b>${volatility}</b></div></div><p><b>Critério:</b> ${item.decision_rationale_pt || item.decision_rationale}</p><p><b>Revisão:</b> ${currentReason}</p><div class="asset-return"><b>Resultado observado depois da decisão</b>${pct(item.realised_next_year_return)} no período anual. Mostrado para avaliar a regra, não para justificar a entrada.</div><div class="asset-weight"><span>Score na decisão: ${item.value_quality_score == null ? "—" : item.value_quality_score.toLocaleString("pt-BR", {minimumFractionDigits:2,maximumFractionDigits:2})}</span><strong>${item.decision_action_pt || ""}</strong></div></article>`;
  }).join("");
  const panel = document.querySelector("#asset-action-panel");
  panel.classList.add("active");
  panel.innerHTML = `<div><span class="action-label">COMO LER</span><b>Escolha antes, resultado depois.</b><p>O dossiê separa o que estava disponível em janeiro da rentabilidade observada no ano.</p></div><div><span class="action-label">PRÓXIMA REVISÃO</span><b>${formatDateBr(decision.holding_end_exclusive)}</b><p>Reavaliar elegibilidade, dados CVM, liquidez, custos e pesos. Não é instrução de compra ou venda.</p></div>`;
}

function refreshDecisionStudio() {
  if (!researchData) return;
  syncDecisionYears();
  renderAssetWorkbench();
  renderProfileHistory();
  renderComparison(currentPeriod);
  renderCurrentDecision();
  renderForecast();
}

function pctPlain(value) { return Number.isFinite(value) ? `${(value * 100).toLocaleString("pt-BR", {maximumFractionDigits: 1})}%` : "—"; }
function signedScenario(value) { return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${pctPlain(value)}` : "—"; }

function renderForecast() {
  if (!forecastData || !researchData) return;
  const profileName = ({ conservador: "Conservador", moderado: "Equilibrado", arrojado: "Arrojado" })[currentProfile] || "Equilibrado";
  const returns = activeProfileRows().map(item => item.net_return).filter(Number.isFinite).sort((a, b) => a - b);
  const quantile = probability => returns.length ? returns[Math.round((returns.length - 1) * probability)] : NaN;
  const portfolio = {
    historical_downside_p20: quantile(.2),
    historical_median_return: quantile(.5),
    historical_upside_p80: quantile(.8),
    historical_observations: returns.length,
  };
  document.querySelector("#scenario-profile-label").textContent = `CENÁRIOS HISTÓRICOS · ${profileName.toUpperCase()}`;
  document.querySelector("#scenario-summary").innerHTML = [
    ["CENÁRIO ADVERSO · P20", signedScenario(portfolio.historical_downside_p20)],
    ["MEDIANA HISTÓRICA", signedScenario(portfolio.historical_median_return)],
    ["CENÁRIO FAVORÁVEL · P80", signedScenario(portfolio.historical_upside_p80)],
  ].map(([label, value]) => `<div><small>${label}</small><b>${value}</b></div>`).join("");
  const values = [portfolio.historical_downside_p20, portfolio.historical_median_return, portfolio.historical_upside_p80].filter(Number.isFinite);
  const min = Math.min(-.15, ...values), max = Math.max(.20, ...values);
  const point = value => `${Math.min(98, Math.max(2, (value - min) / Math.max(max - min, .01) * 96 + 2))}%`;
  document.querySelector("#scenario-chart").innerHTML = `<div class="scenario-track"></div><div class="scenario-range" style="left:${point(portfolio.historical_downside_p20)};right:${100-Number.parseFloat(point(portfolio.historical_upside_p80))}%"></div>${[
    [portfolio.historical_downside_p20, "P20"], [portfolio.historical_median_return, "mediana"], [portfolio.historical_upside_p80, "P80"]
  ].map(([value, label]) => `<span class="scenario-marker" style="left:${point(value)}">${label}<i></i>${signedScenario(value)}</span>`).join("")}<div class="scenario-scale"><span>${signedScenario(min)}</span><span>retorno anual histórico condicional</span><span>${signedScenario(max)}</span></div>`;
  document.querySelector("#scenario-caption").textContent = `Distribuição dos ${portfolio.historical_observations} retornos anuais líquidos da política ${profileName}. Custos e CDI residual pertencem ao protocolo de carteira; não é previsão de rentabilidade.`;
  document.querySelector("#scenario-limitations").innerHTML = forecastData.limitations.map(note => `<span>${note}</span>`).join("");
}

function renderCurrentDecision() {
  if (!currentDecisionData) return;
  const { universe, holdings, monitoring, decision_date: date } = currentDecisionData;
  const policy = activePolicy();
  const requestedEquity = Math.min(policy.equity / 100, 1);
  const feasibleEquity = Math.min(requestedEquity, holdings.length * policy.issuer / 100);
  const visibleHoldings = holdings.map(asset => ({ ...asset, weight: feasibleEquity / holdings.length })).filter(asset => asset.weight > .0001);
  const cdiWeight = Math.max(0, 1 - visibleHoldings.reduce((sum, asset) => sum + asset.weight, 0));
  const capital = Number(document.querySelector("#wealth")?.value) || 0;
  const priceReturn = monitoring?.portfolio_price_return;
  const profileName = ({ conservador: "Conservadora", moderado: "Equilibrada", arrojado: "Arrojada" })[currentProfile] || "Equilibrada";
  const requestedLabel = ({ conservador: "Conservador", moderado: "Equilibrado", arrojado: "Arrojado" })[currentProfile] || "Equilibrado";
  const hasComparableMonitoring = currentProfile === "moderado";
  document.querySelector("#current-decision-heading").innerHTML = `Carteira ${profileName}<br /><em>em janeiro de 2026.</em>`;
  document.querySelector("#current-decision-intro").textContent = `Triagem feita em ${formatDateBr(date)}, com dados públicos, liquidez e concentração. A IA explica a decisão; pesos e critérios seguem a regra.`;
  document.querySelector("#current-decision-label").textContent = `CARTEIRA-CANDIDATA · ${requestedLabel.toUpperCase()}`;
  document.querySelector("#current-decision-summary").innerHTML = [
    ["DECISÃO", formatDateBr(date)],
    ["AÇÕES", pctPlain(1 - cdiWeight)],
    ["RESULTADO PARCIAL", hasComparableMonitoring && Number.isFinite(priceReturn) ? signedScenario(priceReturn) : "Indisponível"],
  ].map(([label, value]) => `<div><small>${label}</small><b>${value}</b></div>`).join("");
  document.querySelector("#current-decision-assets").innerHTML = [...visibleHoldings.map(asset => `<article class="suggestion-asset"><div class="suggestion-row"><div><small>ATIVO SELECIONADO</small><b>${asset.ticker}</b></div><div><small>PESO · ${money.format(capital * asset.weight)}</small><strong>${pctPlain(asset.weight)}</strong></div></div><p>${asset.why}</p></article>`), cdiWeight > .0001 ? `<article class="suggestion-asset"><div class="suggestion-row"><div><small>RESERVA DEFENSIVA</small><b>CDI</b></div><div><small>PESO · ${money.format(capital * cdiWeight)}</small><strong>${pctPlain(cdiWeight)}</strong></div></div><p>Reserva resultante do teto de renda variável da política selecionada.</p></article>` : ""].join("");
  const feasibility = feasibleEquity < requestedEquity ? ` Com os ${holdings.length} ativos processados nesta prévia, a exposição atingida é ${pctPlain(feasibleEquity)}; o restante fica em CDI.` : "";
  const monitoringText = hasComparableMonitoring
    ? ` Até ${formatDateBr(monitoring?.through || date)}: ${monitoring?.label || "resultado parcial indisponível"}.`
    : " O resultado parcial está disponível apenas para os pesos do perfil Equilibrado; o site não reaproveita esse número para outro perfil.";
  document.querySelector("#current-decision-caption").textContent = `Perfil ${requestedLabel}: teto de ${policy.equity}% em renda variável e ${policy.issuer}% por emissor. Os pesos da candidata refletem esse perfil.${feasibility}${monitoringText}`;
}

function moneyCompact(value) { return new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL",notation:"compact",maximumFractionDigits:1}).format(value || 0); }
function renderUniverse() {
  if (!universeData) return;
  const byClass = universeData.coverage_by_class;
  document.querySelector("#universe-summary").innerHTML = [[universeData.instrument_count, "instrumentos negociados"], [byClass.equity || 0, "ações"], [byClass.etf || 0, "ETFs / fundos listados"], [byClass.bdr || 0, "BDRs"], [byClass.fii || 0, "FIIs / Fiagros"]].map(([value, label]) => `<div><b>${value.toLocaleString("pt-BR")}</b><span>${label}</span></div>`).join("");
  const selectedTickers = new Set((currentDecisionData?.holdings || []).map(asset => `${asset.ticker}.SA`));
  const update = () => {
    const query = document.querySelector("#universe-search").value.trim().toUpperCase();
    const assetClass = document.querySelector("#universe-class").value;
    const minimumLiquidity = Number(document.querySelector("#universe-liquidity").value);
    const rows = universeData.instruments.filter(item => (assetClass === "all" || item.asset_class === assetClass) && item.average_daily_value_brl >= minimumLiquidity && (!query || `${item.ticker} ${item.issuer_name} ${item.specification}`.includes(query))).slice(0, 250);
    document.querySelector("#universe-table").innerHTML = rows.map(item => {
      const selected = selectedTickers.has(item.ticker);
      const status = selected ? "Selecionado em janeiro de 2026"
        : item.asset_class === "equity" ? "Candidato: requer vínculo CVM, histórico e triagem"
        : item.asset_class === "etf" ? "Disponível no comparador. Alocação por índice pendente"
        : item.asset_class === "fii" ? "Disponível no catálogo. Módulo imobiliário pendente"
        : item.asset_class === "bdr" ? "Disponível no comparador. Módulo internacional pendente"
        : "Requer mandato e regra específicos";
      const classLabel = ({ equity: "Ação", etf: "ETF", bdr: "BDR", fii: "FII / Fiagro", other: "Outro" })[item.asset_class] || item.asset_class;
      return `<tr><td>${item.ticker.replace(".SA", "")}</td><td><span class="universe-class">${classLabel}</span></td><td>${item.issuer_name}</td><td>${money.format(item.close_price_brl)}</td><td>${moneyCompact(item.average_daily_value_brl)}</td><td><span class="universe-status ${selected ? "covered" : "blocked"}">${status}</span></td></tr>`;
    }).join("") || `<tr><td colspan="6">Nenhum instrumento atende aos filtros selecionados.</td></tr>`;
    document.querySelector("#universe-foot").textContent = `Exibindo ${rows.length} de ${universeData.instrument_count.toLocaleString("pt-BR")} instrumentos da base de ${formatDateBr(universeData.observed_at)}. ${universeData.eligibility_note}`;
  };
  ["#universe-search", "#universe-class", "#universe-liquidity"].forEach(selector => document.querySelector(selector).addEventListener(selector === "#universe-search" ? "input" : "change", update));
  update();
}

const wealth = document.querySelector("#wealth"), wealthOut = document.querySelector("#wealth-output");
wealth.addEventListener("input", () => { wealthOut.value = money.format(wealth.value); renderCurrentDecision(); });
document.querySelectorAll(".choice").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".choice").forEach(item => item.classList.remove("active"));
  button.classList.add("active"); currentProfile = button.dataset.profile;
  selectedCurves = new Set(); chartZoom = 1; chartFocus = null;
  document.querySelector("#proposal-form").requestSubmit();
}));
document.querySelector("#proposal-form").addEventListener("submit", event => {
  event.preventDefault();
  const profile = profiles[currentProfile];
  const requestedEquity = Math.max(0, Math.min(100, Number(profile.equity) || 0));
  const issuerCap = Math.max(1, Math.min(100, Number(profile.issuer) || 1));
  // This illustration assumes four selected issuers.  It shows the attainable
  // allocation instead of silently treating a policy ceiling as a target.
  const requiredIssuers = requestedEquity === 0 ? 0 : Math.ceil(requestedEquity / issuerCap);
  // The live B3 discovery universe has hundreds of equities. The lab should
  // not create a false CDI residue merely because its visual sample contains
  // four issuers; enough diversified slots are assumed for the policy ceiling.
  const availableIllustrativeIssuers = Math.max(4, requiredIssuers || 4);
  const effectiveEquity = Math.min(requestedEquity, issuerCap * availableIllustrativeIssuers);
  const safeEquity = Number.isFinite(effectiveEquity) ? effectiveEquity : 0;
  const mix = [["Ações elegíveis", safeEquity], ["CDI / defensivo", 100 - safeEquity]];
  const capNote = effectiveEquity < requestedEquity
    ? ` Com ${availableIllustrativeIssuers} emissores ilustrativos e teto de ${issuerCap}% por emissor, a exposição efetiva fica em ${effectiveEquity}%; o restante permanece defensivo.`
    : " A exposição é um teto de política, não uma meta ou previsão de retorno.";
  document.querySelector("#proposal-empty").classList.add("hidden");
  document.querySelector("#proposal-content").classList.remove("hidden");
  document.querySelector("#profile-label").textContent = currentProfile === "moderado" ? "equilibrado" : currentProfile;
  document.querySelector("#equity-weight").textContent = `${safeEquity}%`;
  document.querySelector("#fixed-weight").textContent = `${100-safeEquity}%`;
  document.querySelector("#review-cycle").textContent = profile.review;
  document.querySelector("#proposal-insight").textContent = profile.insight + capNote + (requestedEquity === 100 ? " Sem reserva defensiva, a política precisa de validação reforçada de liquidez e tolerância a perda." : "");
  document.querySelector("#weight-list").innerHTML = mix.map(([name, weight]) => `<div class="weight-row"><span>${name}</span><div class="bar"><i style="width:${weight}%"></i></div><b>${weight}%</b></div>`).join("");
  refreshDecisionStudio();
});

function renderCurveToggles(period) {
  const series = seriesFor(period), names = Object.keys(series);
  if (!selectedCurves.size || [...selectedCurves].some(name => !names.includes(name))) selectedCurves = new Set(names);
  document.querySelector("#curve-toggles").innerHTML = names.map((name, index) => `<button type="button" class="curve-toggle ${selectedCurves.has(name) ? "active" : ""}" data-kind="${name}" style="--series-color:${seriesColor(name, index)}"><i></i>${name}</button>`).join("");
  document.querySelectorAll(".curve-toggle").forEach(button => button.addEventListener("click", () => {
    const name = button.dataset.kind;
    selectedCurves.has(name) ? selectedCurves.delete(name) : selectedCurves.add(name);
    renderCurveToggles(period); renderLineChart(period);
  }));
}

function renderLineChart(period) {
  const data = profileDataset(period), allSeries = seriesFor(period);
  const lineLayer = document.querySelector("#line-chart-lines"), gridLayer = document.querySelector("#line-chart-grid"), labelLayer = document.querySelector("#line-chart-labels"), directLabelLayer = document.querySelector("#line-chart-direct-labels");
  const selected = [...selectedCurves].filter(name => allSeries[name]);
  if (!data || !selected.length) { lineLayer.innerHTML = gridLayer.innerHTML = labelLayer.innerHTML = directLabelLayer.innerHTML = ""; return; }
  const totalPoints = data.dates.length;
  const visiblePoints = Math.max(3, Math.ceil(totalPoints / chartZoom));
  const focus = chartFocus == null ? totalPoints - 1 : chartFocus;
  const startIndex = Math.max(0, Math.min(totalPoints - visiblePoints, focus - Math.floor(visiblePoints / 2)));
  const endIndex = Math.min(totalPoints, startIndex + visiblePoints);
  const dates = data.dates.slice(startIndex, endIndex);
  const visibleSeries = Object.fromEntries(selected.map(name => [name, allSeries[name].slice(startIndex, endIndex)]));
  const values = selected.flatMap(name => visibleSeries[name].filter(value => Number.isFinite(value) && value > 0));
  if (!values.length) { lineLayer.innerHTML = gridLayer.innerHTML = labelLayer.innerHTML = directLabelLayer.innerHTML = ""; return; }
  const transformed = value => chartScale === "log" ? Math.log(value) : value;
  const transformedValues = values.map(transformed);
  const rawMin = Math.min(...transformedValues), rawMax = Math.max(...transformedValues);
  const min = chartScale === "log" ? rawMin : Math.floor(rawMin / 25) * 25;
  const max = chartScale === "log" ? rawMax : Math.ceil(rawMax / 25) * 25;
  const width=900, height=410, left=54, right=144, top=18, bottom=38, plotW=width-left-right, plotH=height-top-bottom;
  const x = index => left + index * plotW / Math.max(dates.length - 1, 1);
  const y = value => top + (max - transformed(value)) * plotH / Math.max(max-min, .0001);
  const grid = Array.from({length:5}, (_, index) => min + index * (max-min) / 4).map(value => {
    const rawValue = chartScale === "log" ? Math.exp(value) : value;
    const yPosition = top + (max - value) * plotH / Math.max(max-min, .0001);
    return `<line class="line-grid" x1="${left}" x2="${width-right}" y1="${yPosition}" y2="${yPosition}"/><text class="line-grid-label" x="4" y="${yPosition + 3}">${(rawValue - 100).toLocaleString("pt-BR", {maximumFractionDigits:0})}%</text>`;
  }).join("");
  const dateLabels = [0, Math.floor((dates.length-1)/2), dates.length-1].map(index => `<text class="line-grid-label" text-anchor="${index===0?"start":index===dates.length-1?"end":"middle"}" x="${x(index)}" y="${height-5}">${formatDateBr(dates[index])}</text>`).join("");
  lineLayer.innerHTML = selected.map((name, seriesIndex) => {
    let active = false;
    const path = visibleSeries[name].map((value,index) => { if (!Number.isFinite(value)) { active = false; return ""; } const command = active ? "L" : "M"; active = true; return `${command}${x(index).toFixed(2)},${y(value).toFixed(2)}`; }).join(" ");
    return `<path class="line-path" data-series="${name}" stroke="${seriesColor(name, seriesIndex)}" d="${path}"/>`;
  }).join("");
  directLabelLayer.innerHTML = selected.map((name, seriesIndex) => {
    const series = visibleSeries[name], lastIndex = series.reduce((result, value, index) => Number.isFinite(value) ? index : result, -1);
    if (lastIndex < 0) return "";
    const returnPct = (series[lastIndex] / 100 - 1) * 100;
    return `<g class="line-direct-label"><circle cx="${x(lastIndex)}" cy="${y(series[lastIndex])}" r="4" fill="${seriesColor(name, seriesIndex)}"/><text x="${x(lastIndex) + 9}" y="${y(series[lastIndex]) - 5}" fill="${seriesColor(name, seriesIndex)}">${name}</text><text x="${x(lastIndex) + 9}" y="${y(series[lastIndex]) + 11}" fill="#607480">${returnPct >= 0 ? "+" : ""}${returnPct.toLocaleString("pt-BR", {maximumFractionDigits:1})}%</text></g>`;
  }).join("");
  gridLayer.innerHTML = grid; labelLayer.innerHTML = `${dateLabels}<text class="line-axis-title" x="15" y="${top + plotH / 2}" transform="rotate(-90 15 ${top + plotH / 2})">Retorno acumulado (%)</text><text class="line-axis-title" text-anchor="middle" x="${left + plotW / 2}" y="${height - 1}">Data de observação</text>`;
  document.querySelector("#chart-return-summary").innerHTML = selected.map((name, index) => {
    const series = allSeries[name].slice(startIndex, endIndex);
    const first = series.find(value => Number.isFinite(value));
    const last = [...series].reverse().find(value => Number.isFinite(value));
    const returnPct = (last / first - 1) * 100;
    return `<span style="--series-color:${seriesColor(name, index)}"><i></i><b>${name}</b><strong>${returnPct >= 0 ? "+" : ""}${returnPct.toLocaleString("pt-BR", {maximumFractionDigits:1})}%</strong></span>`;
  }).join("");
  const start = dates[0], end = dates.at(-1);
  document.querySelector("#chart-zoom-status").textContent = chartZoom === 1 ? "Visão completa" : `${dates.length} pontos visíveis`;
  document.querySelector("#line-chart-caption").textContent = `${selected.length} série(s) visível(is) · ${formatDateBr(start)} a ${formatDateBr(end)} · retorno acumulado em %. Escala ${chartScale === "log" ? "logarítmica" : "linear"}. Use a roda do mouse para ampliar e arraste para deslocar.`;
  const inspect = event => {
    const rect = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - rect.left) * width / rect.width;
    const index = Math.max(0, Math.min(dates.length - 1, Math.round((viewX - left) / plotW * (dates.length - 1))));
    const cursor = document.querySelector("#line-chart-cursor"); cursor.classList.remove("hidden"); cursor.setAttribute("x1", x(index)); cursor.setAttribute("x2", x(index)); cursor.setAttribute("y1", top); cursor.setAttribute("y2", height-bottom);
    document.querySelector("#chart-inspector").innerHTML = `<b>${formatDateBr(dates[index])}</b> · ${selected.map(name => `${name}: <b>${Number.isFinite(visibleSeries[name][index]) ? pct(visibleSeries[name][index] / visibleSeries[name].find(Number.isFinite) - 1) : "—"}</b>`).join(" &nbsp;|&nbsp; ")}`;
  };
  const chart = document.querySelector("#line-chart");
  let dragStart = null;
  chart.onmousemove = event => { inspect(event); if (dragStart != null) { const delta = event.clientX - dragStart; if (Math.abs(delta) > 8) { chartFocus = Math.max(0, Math.min(totalPoints - 1, focus - Math.round(delta / 35))); dragStart = event.clientX; renderLineChart(period); } } };
  chart.onmousedown = event => { dragStart = event.clientX; };
  chart.onmouseup = () => { dragStart = null; };
  chart.onmouseleave = () => { dragStart = null; };
  chart.onclick = inspect;
  chart.onwheel = event => { event.preventDefault(); chartZoom = Math.max(1, Math.min(5, chartZoom + (event.deltaY < 0 ? 1 : -1))); chartFocus = startIndex + Math.round((event.offsetX / chart.clientWidth) * Math.max(dates.length - 1, 0)); renderLineChart(period); };
}

function wealthStats(returns) {
  const wealth = returns.reduce((value, item) => value * (1 + item), 1);
  return { cumulative: wealth - 1, cagr: Math.pow(wealth, 1 / returns.length) - 1 };
}
function renderComparison(period) {
  if (!researchData) return;
  refreshExtraSeriesForPeriod(period);
  const length = comparisonWindows[period];
  const rows = activeProfileRows().slice(-length);
  const benevente = wealthStats(rows.map(item => item.net_return));
  const mvo = wealthStats(rows.map(item => item.mvo_eligible_net_return));
  const cdi = wealthStats(rows.map(item => item.cdi_net_return));
  const winCdi = rows.filter(item => item.net_return > item.cdi_net_return).length;
  const winMvo = rows.filter(item => item.net_return > item.mvo_eligible_net_return).length;
  const start = rows[0].decision_date, end = rows.at(-1).holding_end_exclusive;
  const versusCdi = benevente.cumulative - cdi.cumulative, versusMvo = benevente.cumulative - mvo.cumulative;
  document.querySelector("#period-description").textContent = `${formatDateBr(start)} a ${formatDateBr(end)} · ${rows.length} decisões anuais com custos deduzidos.`;
  document.querySelector("#comparison-summary").textContent = `Benevente ${plainPct(benevente.cumulative)} acumulado. Diferença para CDI ${pct(versusCdi)}. Diferença para MVO clássico ${pct(versusMvo)}.`;
  const baseRows = [["Benevente Quant AI", benevente, versusMvo >= 0 ? "Acima do MVO" : "Abaixo do MVO"], ["MVO clássico (elegível)", mvo, "Mesmo universo"], ["CDI", cdi, "Reserva defensiva"]];
  const extras = Object.entries(extraSeries[period] || {}).map(([name, values]) => {
    const metrics = metricsForSeries(values, profileDataset(period).dates);
    const firstAvailable = values.findIndex(value => Number.isFinite(Number(value)));
    const note = firstAvailable >= 0 ? `Disponível desde ${formatDateBr(profileDataset(period).dates[firstAvailable])}` : "Série adicionada";
    return metrics ? [name, { cumulative: values.at(-1) / values.find(Number.isFinite) - 1, cagr: metrics.cagr }, note] : null;
  }).filter(Boolean);
  document.querySelector("#comparison-table").innerHTML = [...baseRows, ...extras].map(([name, stats, note]) => `<tr><td>${name}</td><td><b>${plainPct(stats.cumulative)}</b><small>${plainPct(stats.cagr)}<br />a.a.</small></td><td>${note}</td></tr>`).join("");
  document.querySelector("#research-note").textContent = `Na janela de ${rows.length} ano(s), o Benevente ${versusCdi >= 0 ? "superou" : "ficou abaixo do"} CDI em ${plainPct(Math.abs(versusCdi))} e ${versusMvo >= 0 ? "superou" : "ficou abaixo do"} MVO clássico em ${plainPct(Math.abs(versusMvo))}. Não é garantia de retorno.`;
  renderCurveToggles(period); renderLineChart(period);
}
let currentPeriod = "3";
document.querySelectorAll(".period:not(.unavailable)").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll(".period").forEach(item=>item.classList.remove("active"));button.classList.add("active");selectedCurves=new Set();chartZoom=1;chartFocus=null;currentPeriod=button.dataset.period;renderComparison(currentPeriod)}));
document.querySelector("#chart-zoom-in").addEventListener("click", () => { chartZoom = Math.min(5, chartZoom + 1); renderLineChart(currentPeriod); });
document.querySelector("#chart-zoom-out").addEventListener("click", () => { chartZoom = Math.max(1, chartZoom - 1); renderLineChart(currentPeriod); });
document.querySelector("#chart-zoom-reset").addEventListener("click", () => { chartZoom = 1; chartFocus = null; renderLineChart(currentPeriod); });
document.querySelectorAll(".chart-scale").forEach(button => button.addEventListener("click", () => { document.querySelectorAll(".chart-scale").forEach(item => item.classList.remove("active")); button.classList.add("active"); chartScale = button.dataset.scale; renderLineChart(currentPeriod); }));
document.querySelectorAll(".chart-source").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".chart-source").forEach(item => item.classList.remove("active")); button.classList.add("active"); chartSource = button.dataset.source;
  document.querySelector("#chart-symbol-label").classList.toggle("hidden", chartSource !== "ticker");
  document.querySelector("#fund-preset-label").classList.toggle("hidden", chartSource !== "fund");
  document.querySelector("#fund-cnpj-label").classList.toggle("hidden", chartSource !== "fund");
  document.querySelector("#fund-name-label").classList.toggle("hidden", chartSource !== "fund");
  document.querySelector("#fund-file-label").classList.toggle("hidden", chartSource !== "fund");
  document.querySelector("#chart-add-help").textContent = chartSource === "ticker"
    ? "Busca preços ajustados do ticker na janela selecionada e normaliza em base 100. Fonte: Yahoo Finance. Valide com fonte institucional antes de usar na análise."
    : "Use um fundo sugerido ou informe CNPJ e CSV oficial de cotas. Um fundo não é benchmark oficial nem recomendação.";
}));
document.querySelectorAll(".quick-ticker").forEach(button => button.addEventListener("click", () => {
  document.querySelector("#chart-symbol").value = button.dataset.ticker;
  document.querySelector("#chart-add-form").requestSubmit();
}));
document.querySelectorAll(".fund-preset-button").forEach(button => button.addEventListener("click", () => {
  document.querySelector("#fund-cnpj").value = button.dataset.fundCnpj;
  document.querySelector("#fund-name").value = button.dataset.fundName;
  const preset = (fundPresetsData?.funds || []).find(item => item.cnpj === button.dataset.fundCnpj);
  if (!preset) { document.querySelector("#chart-add-help").textContent = "Referência ainda não está disponível nesta cópia."; return; }
  const data = profileDataset(currentPeriod);
  try {
    addedSeries.set(preset.name, preset.points);
    refreshExtraSeriesForPeriod(currentPeriod);
    selectedCurves = new Set(Object.keys(seriesFor(currentPeriod))); renderComparison(currentPeriod);
    document.querySelector("#chart-add-help").textContent = `${preset.name} adicionado com cotas CVM. ${preset.limitation}`;
  } catch (error) { document.querySelector("#chart-add-help").textContent = error.message || "Não foi possível alinhar as cotas do fundo."; }
}));
document.querySelector("#chart-add-form").addEventListener("submit", async event => {
  event.preventDefault();
  const help = document.querySelector("#chart-add-help"), data = profileDataset(currentPeriod);
  if (!data) return;
  try {
    if (chartSource === "ticker") {
      const symbol = document.querySelector("#chart-symbol").value.trim().toUpperCase();
      if (!symbol) throw new Error("Informe um ticker B3, por exemplo PETR4.");
      help.textContent = "Consultando série de preço ajustado…";
      const request = await fetch(`/api/chart-series?symbol=${encodeURIComponent(symbol)}&start=${data.dates[0]}&end=${data.dates.at(-1)}`);
      const payload = await request.json(); if (!request.ok) throw new Error(payload.error || "Não foi possível carregar o ticker.");
      addedSeries.set(payload.symbol.replace(".SA", ""), payload.points);
      refreshExtraSeriesForPeriod(currentPeriod);
    } else {
      const file = document.querySelector("#fund-file").files[0];
      if (!file) {
        const cnpj = document.querySelector("#fund-cnpj").value.replace(/\D/g, "");
        const name = document.querySelector("#fund-name").value.trim() || `Fundo CVM ${cnpj}`;
        const preset = (fundPresetsData?.funds || []).find(item => item.cnpj === cnpj);
        if (preset) {
          addedSeries.set(preset.name, preset.points);
          refreshExtraSeriesForPeriod(currentPeriod);
          selectedCurves = new Set(Object.keys(seriesFor(currentPeriod))); renderComparison(currentPeriod);
          help.textContent = `${preset.name} adicionado com cotas oficiais CVM na janela selecionada.`;
          return;
        }
        if (!cnpj) throw new Error("Escolha um fundo sugerido, informe o CNPJ ou importe o CSV de cotas.");
        throw new Error(`${name}: importe o CSV oficial de cotas CVM para comparar este CNPJ nesta sessão.`);
      }
      const source = (await file.text()).trim();
      const delimiter = source.split(/\r?\n/, 1)[0].includes(";") ? ";" : ",";
      const rows = source.split(/\r?\n/).map(line => line.split(delimiter).map(cell => cell.trim().replace(/^"|"$/g, "")));
      const header = rows.shift().map(item => item.toLowerCase());
      const dateIndex = header.findIndex(item => ["date", "data", "dt_comptc"].includes(item));
      const quotaIndex = header.findIndex(item => ["quota", "cota", "vl_quota", "valor"].includes(item));
      if (dateIndex < 0 || quotaIndex < 0) throw new Error("O CSV precisa ter colunas date/data e quota/cota/valor.");
      const points = rows.map(row => ({ date: row[dateIndex], value: parseQuotaNumber(row[quotaIndex]) })).filter(point => point.date && Number.isFinite(point.value));
      if (points.length < 2) throw new Error("O arquivo não contém cotas válidas suficientes.");
      addedSeries.set(`Fundo importado: ${file.name.replace(/\.csv$/i, "")}`, points);
      refreshExtraSeriesForPeriod(currentPeriod);
    }
    selectedCurves = new Set(Object.keys(seriesFor(currentPeriod))); renderComparison(currentPeriod);
    help.textContent = "Série adicionada. Use as chaves para mostrar ou ocultar linhas e clique no gráfico para inspecionar datas.";
  } catch (error) { help.textContent = error.message || "Não foi possível adicionar a série."; }
});
document.querySelector("#decision-year").addEventListener("change", renderAssetWorkbench);

document.querySelector("#demo-request-form").addEventListener("submit", async event => {
  event.preventDefault();
  const form = event.currentTarget;
  const response = document.querySelector("#demo-form-response");
  const button = form.querySelector("button");
  button.disabled = true;
  response.textContent = "Enviando solicitação…";
  try {
    const request = await fetch("/api/demo-request", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(Object.fromEntries(new FormData(form))) });
    const payload = await request.json();
    if (!request.ok) throw new Error(payload.error || "Não foi possível registrar a solicitação.");
    response.textContent = "Solicitação registrada. A equipe retornará pelo e-mail informado.";
    form.reset();
  } catch (error) {
    response.textContent = error.message || "Não foi possível enviar. Tente novamente em alguns instantes.";
  } finally { button.disabled = false; }
});

function renderModel(step) { const item=modelSteps[step]; document.querySelector("#model-detail").innerHTML=`<span class="detail-number">${item.number}</span><h3>${item.title}</h3><p>${item.text}</p><div class="detail-grid"><div><small>USA</small><b>${item.uses}</b></div><div><small>BLOQUEIA</small><b>${item.blocks}</b></div><div><small>PRODUZ</small><b>${item.produces}</b></div><div><small>RESPONSÁVEL</small><b>Instituição e revisor humano</b></div></div><p class="detail-rule">${item.rule}</p>`; }
document.querySelectorAll(".model-step").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll(".model-step").forEach(item=>item.classList.remove("active"));button.classList.add("active");renderModel(button.dataset.step)}));

renderModel("policy");
Promise.all([fetch("./annual_research.json"), fetch("./forecast_research.json"), fetch("./b3_universe.json"), fetch("./current_decision_2026.json"), fetch("./fund_presets.json")]).then(async ([research, forecast, universe, currentDecision, fundPresets]) => {
  if (!research.ok || !forecast.ok || !universe.ok || !currentDecision.ok || !fundPresets.ok) throw new Error("research unavailable");
  researchData = await research.json(); forecastData = await forecast.json(); universeData = await universe.json(); currentDecisionData = await currentDecision.json(); fundPresetsData = await fundPresets.json();
  extraSeries[1] = {}; extraSeries[3] = {}; extraSeries[5] = {}; extraSeries[11] = {};
  document.querySelector("#proposal-form").requestSubmit();
  renderUniverse();
}).catch(() => { document.querySelector("#line-chart-caption").textContent = "Arquivos de pesquisa indisponíveis nesta cópia. Consulte o ambiente local para reproduzir a análise."; document.querySelector("#research-status").textContent = "Dados de pesquisa indisponíveis."; });
