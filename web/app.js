const profiles = {
  conservador: { equity: 35, issuer: 10, review: "trimestral", mix: [["Ações elegíveis", 35], ["CDI / defensivo", 65]], insight: "A prioridade é preservar margem de segurança. A parcela variável fica limitada e qualquer tese deve justificar o risco adicional." },
  moderado: { equity: 55, issuer: 12, review: "trimestral", mix: [["Ações elegíveis", 55], ["CDI / defensivo", 45]], insight: "Há espaço para ações que passam no filtro, sem transformar retorno passado em promessa. O CDI preserva flexibilidade para revisar a tese." },
  arrojado: { equity: 80, issuer: 15, review: "semestral", mix: [["Ações elegíveis", 80], ["CDI / defensivo", 20]], insight: "Aceita maior oscilação, com mais emissores para tornar o limite de renda variável viável sem eliminar diversificação." },
  personalizado: { equity: 55, issuer: 12, review: "definida pela política", mix: [["Ações elegíveis", 55], ["CDI / defensivo", 45]], insight: "Os limites são uma simulação de política. A instituição deve formalizá-los antes de qualquer proposta real." }
};

let researchData = null;
let forecastData = null;
let universeData = null;
const comparisonWindows = { 5: 5, 10: 10, 12: 12, 13: 13 };

const modelSteps = {
  policy: { number:"01 · POLÍTICA", title:"A política vem antes do ativo.", text:"O responsável define patrimônio, perfil, horizonte, concentração máxima, limite de renda variável, perda tolerada, custo e frequência de revisão.", uses:"Perfil, horizonte e limites explícitos", blocks:"Pesos que ultrapassem a política", produces:"Uma política versionada por proposta", rule:"<strong>Regra:</strong> sem reconhecimento explícito da política, não há proposta operacional." },
  data: { number:"02 · DADOS", title:"Uma informação só entra quando era pública.", text:"Cada fundamento tem data contábil e data de disponibilidade. Preços, liquidez, lote e capitalização precisam de snapshot datado e de uma fonte atribuída.", uses:"CVM ITR/DFP, BCB e snapshots de mercado", blocks:"Dados futuros, nulos ou sem fonte", produces:"Pacote datado de entrada", rule:"<strong>Regra:</strong> o documento divulgado depois da decisão é rejeitado no fluxo auditável." },
  screen: { number:"03 · FILTRO", title:"Primeiro eliminar, depois ranquear.", text:"O filtro determinístico busca valor e qualidade. Para não financeiras: caixa, ROIC, dívida e cobertura; para financeiras: ROE e preço sobre valor patrimonial.", uses:"Liquidez, valor, rentabilidade e solvência", blocks:"Ativos frágeis ou com métrica ausente", produces:"Tela de elegibilidade e motivo de bloqueio", rule:"<strong>Regra:</strong> ausência de dado comparável é reprovação, não uma inferência favorável." },
  optimizer: { number:"04 · OTIMIZAÇÃO", title:"Otimizar não é adivinhar.", text:"Somente os ativos elegíveis entram numa otimização restrita. Os pesos obedecem limites por emissor, exposição a ações e uma reserva residual em CDI.", uses:"Retornos históricos e restrições da política", blocks:"Concentração e ativos reprovados", produces:"Pesos, custos e caixa residual", rule:"<strong>Regra:</strong> uma LLM não define pesos e não pode mudar uma regra rígida." },
  review: { number:"05 · REVISÃO HUMANA", title:"O resultado é uma proposta, não uma ordem.", text:"A pessoa responsável revisa tese, riscos, pesos e custos. Se decidir implementar, insere a ordem manualmente e concilia a nota de corretagem depois.", uses:"Proposta, evidências e custo estimado", blocks:"Execução automática", produces:"Carteira-sombra e trilha de auditoria", rule:"<strong>Regra:</strong> resultados prospectivos devem permanecer separados do backtest histórico." }
};

let currentProfile = "moderado";
let curveData = {};
let selectedCurves = new Set();
const extraSeries = { 5: {}, 10: {}, 12: {}, 13: {} };
let chartSource = "ticker";
let chartZoom = 1;
let chartFocus = null;
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const format = value => `${value.toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2})}%`;
const colors = { "Benevente Quant AI":"#0f766e", "MVO clássico (elegível)":"#ae8871", "MVO clássico":"#ae8871", "CDI":"#3b779a", "Ibovespa":"#7a8490" };
const extraColors = ["#9c4f2a", "#7856a3", "#b87418", "#2a7c91"];

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
  return { dates, series };
}
function chartDataset(period) { return annualCurve(period) || curveData[period]; }
function seriesFor(period) { return { ...(chartDataset(period)?.series || {}), ...(extraSeries[period] || {}) }; }
function seriesColor(name, index = 0) { return colors[name] || extraColors[index % extraColors.length]; }
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

// Esta amostra existe apenas para demonstrar a interface de revisão. Os campos
// foram deliberadamente marcados como sintéticos no pipeline e não podem virar
// uma recomendação atual sem um novo snapshot CVM/B3 ponto-no-tempo.
const demoAssets = [
  { ticker:"BBAS3", sector:"Financeiro", score:79.6, pe:"P/L 5,5", quality:"ROE 19,0%", liquidity:"R$ 40 bi/dia", why:"Preço sobre patrimônio e rentabilidade passam na régua financeira.", risk:"Risco de controlador e ciclo de crédito." },
  { ticker:"ITUB4", sector:"Financeiro", score:60.2, pe:"P/L 9,0", quality:"ROE 18,0%", liquidity:"R$ 90 bi/dia", why:"Rentabilidade e liquidez atendem aos filtros do recorte.", risk:"Sensível a crédito, juros e múltiplo." },
  { ticker:"BBDC4", sector:"Financeiro", score:59.2, pe:"P/L 8,5", quality:"ROE 14,0%", liquidity:"R$ 50 bi/dia", why:"Métrica de valor e ROE cumprem a regra financeira.", risk:"Execução operacional e ciclo de provisões." },
  { ticker:"PETR4", sector:"Energia", score:58.2, pe:"P/L 10,0", quality:"ROIC 18,0%", liquidity:"R$ 80 bi/dia", why:"Caixa, retorno sobre capital e alavancagem passam no filtro.", risk:"Commodity, câmbio e interferência estatal." },
  { ticker:"VALE3", sector:"Materiais", score:57.1, pe:"P/L 8,0", quality:"ROIC 15,0%", liquidity:"R$ 70 bi/dia", why:"Valor, geração de caixa e cobertura de juros atendem ao corte.", risk:"Minério, China e risco socioambiental." },
  { ticker:"WEGE3", sector:"Industrial", score:51.0, pe:"P/L 30,0", quality:"ROIC 20,0%", liquidity:"R$ 20 bi/dia", why:"Qualidade e balanço passam; o múltiplo reduz a pontuação relativa.", risk:"Prêmio de valuation e crescimento esperado." },
  { ticker:"ABEV3", sector:"Consumo", score:34.7, pe:"P/L 16,0", quality:"ROIC 12,0%", liquidity:"R$ 30 bi/dia", why:"Liquidez e solvência passam, com menor pontuação de valor/qualidade.", risk:"Crescimento, concorrência e pressão de margens." },
  { ticker:"RENT3", sector:"Consumo", score:0, pe:"P/L 22,0", quality:"Dívida 4,5x", liquidity:"R$ 20 bi/dia", why:"Reprovado antes da otimização.", risk:"FCF abaixo do mínimo, dívida elevada e cobertura insuficiente.", blocked:true }
];
let assetProfile = "moderado";
let customPolicy = { equity: 55, issuer: 12, drawdown: 22 };

function demoWeights(profile) {
  const equity = profile === "personalizado" ? customPolicy.equity : profiles[profile].equity;
  const issuer = profile === "personalizado" ? customPolicy.issuer : profiles[profile].issuer;
  const eligible = demoAssets.filter(asset => !asset.blocked);
  const totalScore = eligible.reduce((sum, asset) => sum + asset.score, 0);
  const weights = Object.fromEntries(eligible.map(asset => [asset.ticker, Math.min(+(equity * asset.score / totalScore).toFixed(1), issuer)]));
  return { weights, residual: +(100 - Object.values(weights).reduce((sum, value) => sum + value, 0)).toFixed(1), issuer };
}

function pct(value, digits = 1) { return `${value >= 0 ? "+" : ""}${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`; }
function plainPct(value, digits = 1) { return `${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`; }
function selectedAnnualDecision() {
  const year = Number(document.querySelector("#decision-year")?.value);
  return researchData?.annual.find(item => item.decision_year === year) || researchData?.annual.at(-1);
}
function renderAssetWorkbench() {
  if (!researchData) return;
  const decision = selectedAnnualDecision();
  if (!decision) return;
  const holdings = researchData.holdings.filter(item => item.decision_year === decision.decision_year);
  const transitions = researchData.transitions.filter(item => item.decision_year === decision.decision_year);
  const equities = holdings.filter(item => item.ticker !== "TITULO_CDI");
  const equityWeight = equities.reduce((sum, item) => sum + item.weight, 0);
  const transitionByTicker = Object.fromEntries(transitions.map(item => [item.ticker, item]));
  document.querySelector("#dossier-policy").textContent = `Execução histórica: qualidade + valor + momento; até ${plainPct(decision.target_equity_weight)} em renda variável e ${plainPct(researchData.meta.protocol.maximum_asset_weight)} por emissor. O retorno abaixo foi realizado depois de ${decision.decision_date}; não foi usado para decidir.`;
  const coverage = researchData.meta.coverage;
  document.querySelector("#research-status").innerHTML = `<b>Status dos dados: execução histórica auditada.</b><span>O explorador cobre ${coverage.b3_instruments?.toLocaleString("pt-BR") || "todos os"} instrumentos B3 do snapshot atual (${coverage.b3_equities_current || "—"} ações). O backtest ainda usa ${coverage.issuers} emissores com fundamentos CVM ponto-no-tempo completos; os demais exigem mapeamento emissor–CNPJ, ITR/DFP histórico e tratamento de eventos societários.</span>`;
  document.querySelector("#asset-summary").innerHTML = `<div><small>DECISÃO</small><strong>${decision.decision_date}</strong><span>Carteira mantida até ${decision.holding_end_exclusive}.</span></div><div><small>RENDA VARIÁVEL</small><strong>${plainPct(equityWeight)}</strong><span>${equities.length} ativo(s) elegível(is); CDI ficou como reserva.</span></div><div><small>RESULTADO POSTERIOR</small><strong>${pct(decision.net_return)}</strong><span>Líquido de custo estimado de ${money.format(decision.estimated_cost_brl)}.</span></div>`;
  document.querySelector("#asset-grid").innerHTML = holdings.map(item => {
    const transition = transitionByTicker[item.ticker];
    const isCdi = item.ticker === "TITULO_CDI";
    const status = isCdi ? "Reserva de liquidez" : (item.decision_action_pt || "Sem alteração");
    const signal = item.trailing_12m_return_at_decision == null ? "Não aplicável" : plainPct(item.trailing_12m_return_at_decision);
    const volatility = item.trailing_12m_volatility_at_decision == null ? "Não aplicável" : plainPct(item.trailing_12m_volatility_at_decision);
    const currentReason = transition?.reason_pt || "Mantido segundo a política e a revisão anual.";
    return `<article class="asset-card ${isCdi ? "defensive" : ""}"><div class="asset-card-top"><div><small>${isCdi ? "RESERVA DEFENSIVA" : "ATIVO ELEGÍVEL"}</small><h3>${isCdi ? "CDI" : item.ticker.replace(".SA", "")}</h3></div><span class="asset-status ${isCdi ? "defensive" : ""}">${status}</span></div><div class="asset-metrics"><div><small>PESO</small><b>${plainPct(item.weight)}</b></div><div><small>12M ANTERIOR</small><b>${signal}</b></div><div><small>VOL. 12M</small><b>${volatility}</b></div></div><p><b>Decisão:</b> ${item.decision_rationale_pt || item.decision_rationale}</p><p><b>Registro de troca:</b> ${currentReason}</p><div class="asset-return"><b>Resultado realizado após a decisão</b>${pct(item.realised_next_year_return)} no período anual. Exibido para avaliação, não para justificar a entrada.</div><div class="asset-weight"><span>Score disponível na decisão: ${item.value_quality_score == null ? "—" : item.value_quality_score.toLocaleString("pt-BR", {minimumFractionDigits:2,maximumFractionDigits:2})}</span><strong>${item.decision_action_pt || ""}</strong></div></article>`;
  }).join("");
  const panel = document.querySelector("#asset-action-panel");
  panel.classList.add("active");
  panel.innerHTML = `<div><span class="action-label">COMO LER</span><b>Decisão antes; resultado depois.</b><p>O dossiê separa informação disponível em janeiro da rentabilidade realizada durante o ano. Assim é possível auditar se uma troca foi defensável sem olhar o futuro.</p></div><div><span class="action-label">PRÓXIMA REVISÃO</span><b>${decision.holding_end_exclusive}</b><p>Reavaliar elegibilidade, dados CVM, liquidez, custos e pesos efetivamente desviados. Não é instrução atual de compra ou venda.</p></div>`;
}

function pctPlain(value) { return Number.isFinite(value) ? `${(value * 100).toLocaleString("pt-BR", {maximumFractionDigits: 1})}%` : "—"; }
function signedScenario(value) { return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${pctPlain(value)}` : "—"; }

function renderForecast() {
  if (!forecastData) return;
  const portfolio = forecastData.portfolio;
  document.querySelector("#suggestion-decision").textContent = `DECISÃO ${forecastData.decision_date}`;
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
  document.querySelector("#scenario-caption").textContent = `${forecastData.label}. Base: ${portfolio.historical_observations} decisões anuais anteriores da regra; custos e CDI residual pertencem ao protocolo de carteira, não aos retornos isolados de ativos.`;
  document.querySelector("#suggestion-assets").innerHTML = forecastData.assets.map(asset => `<article class="suggestion-asset"><div class="suggestion-row"><div><small>ATIVO HISTÓRICO ELEGÍVEL</small><b>${asset.ticker}</b></div><div><small>PESO NO CICLO</small><strong>${pctPlain(asset.weight)}</strong></div></div><div class="suggestion-row"><span>Faixa histórica própria: ${signedScenario(asset.historical_downside_p20)} a ${signedScenario(asset.historical_upside_p80)}</span><span>${asset.historical_observations} observações</span></div><p>${asset.why}</p></article>`).join("");
  document.querySelector("#scenario-limitations").innerHTML = forecastData.limitations.map(note => `<span>${note}</span>`).join("");
}

function moneyCompact(value) { return new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL",notation:"compact",maximumFractionDigits:1}).format(value || 0); }
function renderUniverse() {
  if (!universeData) return;
  const byClass = universeData.coverage_by_class;
  document.querySelector("#universe-summary").innerHTML = [[universeData.instrument_count, "instrumentos negociados"], [byClass.equity || 0, "ações"], [byClass.etf || 0, "ETFs / fundos listados"], [byClass.bdr || 0, "BDRs"], [byClass.fii || 0, "FIIs / Fiagros"]].map(([value, label]) => `<div><b>${value.toLocaleString("pt-BR")}</b><span>${label}</span></div>`).join("");
  const selectedTickers = new Set((forecastData?.assets || []).map(asset => `${asset.ticker}.SA`));
  const update = () => {
    const query = document.querySelector("#universe-search").value.trim().toUpperCase();
    const assetClass = document.querySelector("#universe-class").value;
    const minimumLiquidity = Number(document.querySelector("#universe-liquidity").value);
    const rows = universeData.instruments.filter(item => (assetClass === "all" || item.asset_class === assetClass) && item.average_daily_value_brl >= minimumLiquidity && (!query || `${item.ticker} ${item.issuer_name} ${item.specification}`.includes(query))).slice(0, 250);
    document.querySelector("#universe-table").innerHTML = rows.map(item => {
      const selected = selectedTickers.has(item.ticker);
      const status = selected ? "Selecionado no último ciclo histórico" : item.asset_class === "equity" ? "Aguarda fundamentos CVM ponto-no-tempo" : "Requer módulo e mandato específicos";
      const classLabel = ({ equity: "Ação", etf: "ETF", bdr: "BDR", fii: "FII / Fiagro", other: "Outro" })[item.asset_class] || item.asset_class;
      return `<tr><td>${item.ticker.replace(".SA", "")}</td><td><span class="universe-class">${classLabel}</span></td><td>${item.issuer_name}</td><td>${money.format(item.close_price_brl)}</td><td>${moneyCompact(item.average_daily_value_brl)}</td><td><span class="universe-status ${selected ? "covered" : "blocked"}">${status}</span></td></tr>`;
    }).join("") || `<tr><td colspan="6">Nenhum instrumento atende aos filtros selecionados.</td></tr>`;
    document.querySelector("#universe-foot").textContent = `Exibindo ${rows.length} de ${universeData.instrument_count.toLocaleString("pt-BR")} instrumentos do snapshot ${universeData.observed_at}. ${universeData.eligibility_note}`;
  };
  ["#universe-search", "#universe-class", "#universe-liquidity"].forEach(selector => document.querySelector(selector).addEventListener(selector === "#universe-search" ? "input" : "change", update));
  update();
}

const wealth = document.querySelector("#wealth"), wealthOut = document.querySelector("#wealth-output");
const horizon = document.querySelector("#horizon"), horizonOut = document.querySelector("#horizon-output");
wealth.addEventListener("input", () => wealthOut.value = money.format(wealth.value));
horizon.addEventListener("input", () => horizonOut.value = `${horizon.value} ${horizon.value === "1" ? "ano" : "anos"}`);
document.querySelectorAll(".choice").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".choice").forEach(item => item.classList.remove("active"));
  button.classList.add("active"); currentProfile = button.dataset.profile;
  document.querySelector("#lab-custom-policy").classList.toggle("hidden", currentProfile !== "personalizado");
  assetProfile = currentProfile;
}));
document.querySelectorAll("#lab-custom-policy input").forEach(input => input.addEventListener("input", () => {
  customPolicy = { ...customPolicy, [input.id.replace("lab-", "").replace("-", "")]: Number(input.value) };
  customPolicy.issuer = Math.min(customPolicy.issuer, customPolicy.equity);
  document.querySelector("#lab-equity-output").value = `${customPolicy.equity}%`;
  document.querySelector("#lab-issuer-output").value = `${customPolicy.issuer}%`;
  document.querySelector("#lab-drawdown-output").value = `${customPolicy.drawdown}%`;
}));
document.querySelector("#proposal-form").addEventListener("submit", event => {
  event.preventDefault();
  const profile = profiles[currentProfile];
  const requestedEquity = currentProfile === "personalizado" ? customPolicy.equity : profile.equity;
  const issuerCap = currentProfile === "personalizado" ? customPolicy.issuer : profile.issuer;
  // This illustration assumes four selected issuers.  It shows the attainable
  // allocation instead of silently treating a policy ceiling as a target.
  const requiredIssuers = requestedEquity === 0 ? 0 : Math.ceil(requestedEquity / issuerCap);
  // The live B3 discovery universe has hundreds of equities. The lab should
  // therefore not create a false CDI residue merely because its visual sample
  // contains only eight names: a 100% custom equity ceiling means at least the
  // required number of diversified slots.
  const availableIllustrativeIssuers = Math.max(4, requiredIssuers || 4);
  const effectiveEquity = Math.min(requestedEquity, issuerCap * availableIllustrativeIssuers);
  const mix = [["Ações elegíveis", effectiveEquity], ["CDI / defensivo", 100 - effectiveEquity]];
  const capNote = effectiveEquity < requestedEquity
    ? ` Com ${availableIllustrativeIssuers} emissores ilustrativos e teto de ${issuerCap}% por emissor, a exposição efetiva fica em ${effectiveEquity}%; o restante permanece defensivo.`
    : " A exposição é um teto de política, não uma meta ou previsão de retorno.";
  document.querySelector("#proposal-empty").classList.add("hidden");
  document.querySelector("#proposal-content").classList.remove("hidden");
  document.querySelector("#profile-label").textContent = currentProfile === "moderado" ? "moderado" : currentProfile;
  document.querySelector("#equity-weight").textContent = `${effectiveEquity}%`;
  document.querySelector("#fixed-weight").textContent = `${100-effectiveEquity}%`;
  document.querySelector("#review-cycle").textContent = profile.review;
  document.querySelector("#proposal-insight").textContent = profile.insight + capNote + (requestedEquity === 100 ? " Sem reserva defensiva, a política precisa de validação reforçada de liquidez e tolerância a perda." : "");
  document.querySelector("#weight-list").innerHTML = mix.map(([name, weight]) => `<div class="weight-row"><span>${name}</span><div class="bar"><i style="width:${weight}%"></i></div><b>${weight}%</b></div>`).join("");
  document.querySelector("#proposal-result").scrollIntoView({behavior:"smooth",block:"nearest"});
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
  const data = chartDataset(period), allSeries = seriesFor(period);
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
  const values = selected.flatMap(name => visibleSeries[name].filter(value => Number.isFinite(value)));
  const min = Math.floor(Math.min(...values) / 25) * 25, max = Math.ceil(Math.max(...values) / 25) * 25;
  const width=900, height=410, left=54, right=144, top=18, bottom=38, plotW=width-left-right, plotH=height-top-bottom;
  const x = index => left + index * plotW / Math.max(dates.length - 1, 1);
  const y = value => top + (max - value) * plotH / Math.max(max-min, 1);
  const grid = Array.from({length:5}, (_, index) => min + index * (max-min) / 4).map(value => `<line class="line-grid" x1="${left}" x2="${width-right}" y1="${y(value)}" y2="${y(value)}"/><text class="line-grid-label" x="4" y="${y(value)+3}">${Math.round(value)}</text>`).join("");
  const dateLabels = [0, Math.floor((dates.length-1)/2), dates.length-1].map(index => `<text class="line-grid-label" text-anchor="${index===0?"start":index===dates.length-1?"end":"middle"}" x="${x(index)}" y="${height-5}">${dates[index].slice(0,7)}</text>`).join("");
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
  gridLayer.innerHTML = grid; labelLayer.innerHTML = dateLabels;
  document.querySelector("#chart-return-summary").innerHTML = selected.map((name, index) => {
    const last = [...allSeries[name]].reverse().find(value => Number.isFinite(value));
    const returnPct = (last / 100 - 1) * 100;
    return `<span style="--series-color:${seriesColor(name, index)}"><i></i><b>${name}</b><strong>${returnPct >= 0 ? "+" : ""}${returnPct.toLocaleString("pt-BR", {maximumFractionDigits:1})}%</strong></span>`;
  }).join("");
  const start = dates[0], end = dates.at(-1);
  document.querySelector("#chart-zoom-status").textContent = chartZoom === 1 ? "Visão completa" : `${dates.length} pontos visíveis`;
  document.querySelector("#line-chart-caption").textContent = `${selected.length} série(s) visível(is) · ${start} a ${end} · patrimônio normalizado em 100. Clique, amplie ou arraste para inspecionar.`;
  const inspect = event => {
    const rect = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - rect.left) * width / rect.width;
    const index = Math.max(0, Math.min(dates.length - 1, Math.round((viewX - left) / plotW * (dates.length - 1))));
    const cursor = document.querySelector("#line-chart-cursor"); cursor.classList.remove("hidden"); cursor.setAttribute("x1", x(index)); cursor.setAttribute("x2", x(index)); cursor.setAttribute("y1", top); cursor.setAttribute("y2", height-bottom);
    document.querySelector("#chart-inspector").innerHTML = `<b>${dates[index]}</b> · ${selected.map(name => `${name}: <b>${Number.isFinite(visibleSeries[name][index]) ? visibleSeries[name][index].toLocaleString("pt-BR", {minimumFractionDigits:1, maximumFractionDigits:1}) : "—"}</b>`).join(" &nbsp;|&nbsp; ")}`;
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
  const length = comparisonWindows[period];
  const rows = researchData.annual.slice(-length);
  const benevente = wealthStats(rows.map(item => item.net_return));
  const mvo = wealthStats(rows.map(item => item.mvo_eligible_net_return));
  const cdi = wealthStats(rows.map(item => item.cdi_net_return));
  const winCdi = rows.filter(item => item.net_return > item.cdi_net_return).length;
  const winMvo = rows.filter(item => item.net_return > item.mvo_eligible_net_return).length;
  const start = rows[0].decision_date, end = rows.at(-1).holding_end_exclusive;
  const versusCdi = benevente.cumulative - cdi.cumulative, versusMvo = benevente.cumulative - mvo.cumulative;
  document.querySelector("#period-description").textContent = `${start} a ${end} · ${rows.length} decisões anuais, custos de rebalanceamento deduzidos.`;
  document.querySelector("#comparison-summary").textContent = `Benevente: ${plainPct(benevente.cumulative)} acumulado. Contra CDI: ${pct(versusCdi)}; contra MVO clássico elegível: ${pct(versusMvo)}.`;
  const baseRows = [["Benevente Quant AI", benevente, `${winCdi}/${rows.length} vs CDI`, versusMvo >= 0 ? "acima do MVO" : "abaixo do MVO"], ["MVO clássico (elegível)", mvo, `${winMvo}/${rows.length} perdas para Benevente`, "mesmo universo"], ["CDI", cdi, `${rows.length - winCdi}/${rows.length} anos à frente`, "referência defensiva"]];
  const extras = Object.entries(extraSeries[period] || {}).map(([name, values]) => { const metrics = metricsForSeries(values, chartDataset(period).dates); return metrics ? [name, { cumulative: values.at(-1) / values.find(Number.isFinite) - 1, cagr: metrics.cagr }, "série importada", "comparação visual"] : null; }).filter(Boolean);
  document.querySelector("#comparison-table").innerHTML = [...baseRows, ...extras].map(([name, stats, wins, note]) => `<tr><td>${name}</td><td><b>${plainPct(stats.cumulative)}</b><small>${plainPct(stats.cagr)} a.a.</small></td><td>${wins}</td><td>${note}</td></tr>`).join("");
  document.querySelector("#research-note").textContent = `Leitura correta da janela de ${rows.length} anos: o Benevente ${versusCdi >= 0 ? "superou" : "ficou abaixo do"} CDI em ${plainPct(Math.abs(versusCdi))} e ${versusMvo >= 0 ? "superou" : "ficou abaixo do"} MVO clássico elegível em ${plainPct(Math.abs(versusMvo))}. Isso não comprova alfa persistente nem constitui recomendação.`;
  renderCurveToggles(period); renderLineChart(period);
}
let currentPeriod = "5";
document.querySelectorAll(".period:not(.unavailable)").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll(".period").forEach(item=>item.classList.remove("active"));button.classList.add("active");selectedCurves=new Set();chartZoom=1;chartFocus=null;currentPeriod=button.dataset.period;renderComparison(currentPeriod)}));
document.querySelector("#chart-zoom-in").addEventListener("click", () => { chartZoom = Math.min(5, chartZoom + 1); renderLineChart(currentPeriod); });
document.querySelector("#chart-zoom-out").addEventListener("click", () => { chartZoom = Math.max(1, chartZoom - 1); renderLineChart(currentPeriod); });
document.querySelector("#chart-zoom-reset").addEventListener("click", () => { chartZoom = 1; chartFocus = null; renderLineChart(currentPeriod); });
document.querySelectorAll(".chart-source").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".chart-source").forEach(item => item.classList.remove("active")); button.classList.add("active"); chartSource = button.dataset.source;
  document.querySelector("#chart-symbol-label").classList.toggle("hidden", chartSource !== "ticker");
  document.querySelector("#fund-file-label").classList.toggle("hidden", chartSource !== "fund");
  document.querySelector("#chart-add-help").textContent = chartSource === "ticker"
    ? "Busca preços ajustados do ticker no período selecionado e normaliza em base 100. Fonte: Yahoo Finance; valide com a fonte institucional antes de usar em comitê."
    : "Importe um CSV de cotas já obtido da CVM ou da instituição, com colunas date/data e quota/cota/valor. A série ficará apenas nesta sessão do navegador.";
}));
document.querySelector("#chart-add-form").addEventListener("submit", async event => {
  event.preventDefault();
  const help = document.querySelector("#chart-add-help"), data = chartDataset(currentPeriod);
  if (!data) return;
  try {
    if (chartSource === "ticker") {
      const symbol = document.querySelector("#chart-symbol").value.trim().toUpperCase();
      if (!symbol) throw new Error("Informe um ticker B3, por exemplo PETR4.");
      help.textContent = "Consultando série de preço ajustado…";
      const request = await fetch(`/api/chart-series?symbol=${encodeURIComponent(symbol)}&start=${data.dates[0]}&end=${data.dates.at(-1)}`);
      const payload = await request.json(); if (!request.ok) throw new Error(payload.error || "Não foi possível carregar o ticker.");
      extraSeries[currentPeriod][payload.symbol.replace(".SA", "")] = normalizeToDecisionDates(payload.points, data.dates);
    } else {
      const file = document.querySelector("#fund-file").files[0];
      if (!file) throw new Error("Selecione um CSV de cotas do fundo.");
      const source = (await file.text()).trim();
      const delimiter = source.split(/\r?\n/, 1)[0].includes(";") ? ";" : ",";
      const rows = source.split(/\r?\n/).map(line => line.split(delimiter).map(cell => cell.trim().replace(/^"|"$/g, "")));
      const header = rows.shift().map(item => item.toLowerCase());
      const dateIndex = header.findIndex(item => ["date", "data", "dt_comptc"].includes(item));
      const quotaIndex = header.findIndex(item => ["quota", "cota", "vl_quota", "valor"].includes(item));
      if (dateIndex < 0 || quotaIndex < 0) throw new Error("O CSV precisa ter colunas date/data e quota/cota/valor.");
      const points = rows.map(row => ({ date: row[dateIndex], value: parseQuotaNumber(row[quotaIndex]) })).filter(point => point.date && Number.isFinite(point.value));
      if (points.length < 2) throw new Error("O arquivo não contém cotas válidas suficientes.");
      extraSeries[currentPeriod][`Fundo importado: ${file.name.replace(/\.csv$/i, "")}`] = normalizeToDecisionDates(points, data.dates);
    }
    selectedCurves = new Set(Object.keys(seriesFor(currentPeriod))); renderComparison(currentPeriod);
    help.textContent = "Série adicionada. Use as chaves acima para mostrar ou ocultar linhas e clique no gráfico para inspecionar datas.";
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
Promise.all([fetch("./horizon_curves.json"), fetch("./annual_research.json"), fetch("./forecast_research.json"), fetch("./b3_universe.json")]).then(async ([curves, research, forecast, universe]) => {
  if (!curves.ok || !research.ok || !forecast.ok || !universe.ok) throw new Error("research unavailable");
  curveData = await curves.json(); researchData = await research.json(); forecastData = await forecast.json(); universeData = await universe.json();
  extraSeries[13] = {};
  const select = document.querySelector("#decision-year");
  select.innerHTML = researchData.annual.map(item => `<option value="${item.decision_year}">${item.decision_year} · ${item.decision_date}</option>`).join("");
  select.value = String(researchData.annual.at(-1).decision_year);
  renderAssetWorkbench(); renderForecast(); renderUniverse(); renderComparison(5);
}).catch(() => { document.querySelector("#line-chart-caption").textContent = "Arquivos de pesquisa indisponíveis nesta cópia. Consulte o ambiente local para reproduzir a análise."; document.querySelector("#research-status").textContent = "Dados de pesquisa indisponíveis."; });
