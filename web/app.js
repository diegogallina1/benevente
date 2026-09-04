const profiles = {
  conservador: { equity: 35, issuer: 4.667, review: "anual", mix: [["Ações", 35], ["CDI / defensivo", 65]], insight: "Exposição menor a ações, com doze emissores e o restante em CDI. O limite do perfil é aplicado antes da otimização." },
  moderado: { equity: 55, issuer: 11, review: "anual", mix: [["Ações", 55], ["CDI / defensivo", 45]], insight: "Até 55% em ações entre oito emissores. A configuração do ano é escolhida por Sharpe sobre os anos já encerrados, nunca sobre o ano avaliado." },
  arrojado: { equity: 75, issuer: 24, review: "anual", mix: [["Ações", 75], ["CDI / defensivo", 25]], insight: "Até 75% em ações entre cinco emissores. Com o teto por ativo em 24%, os cinco ficam no limite e a cesta vira peso igual, o que reduz a inclinação para as maiores convicções." }
};

let researchData = null;
let ladderEvidence = null;
let forecastData = null;
let universeData = null;
let currentDecisionData = null;
let fundPresetsData = null;
let finalStrategyData = null;
const comparisonWindows = { 1: 1, 2: 2, 3: 3, 5: 5, 11: 99 };

const modelSteps = {
  policy: { number:"01 · POLÍTICA", title:"A política vem antes do ativo.", text:"O responsável define patrimônio, perfil, limite de ações, concentração por emissor, custos e revisão anual.", uses:"Perfil e limites explícitos", blocks:"Pesos acima da política", produces:"Uma política reproduzível", rule:"<strong>Regra:</strong> sem política, não há carteira." },
  data: { number:"02 · DADOS", title:"A decisão usa somente o que já era público.", text:"Em janeiro, o motor combina demonstrações ITR/DFP já divulgadas, histórico de preços, liquidez e CDI. Cada arquivo tem origem, data e hash registrados.", uses:"B3, CVM e Banco Central", blocks:"Informação divulgada depois da decisão", produces:"Base anual verificável", rule:"<strong>Regra:</strong> o retorno do ano avaliado nunca participa da escolha." },
  screen: { number:"03 · FILTRO FUNDAMENTAL", title:"Qualidade e segurança vêm antes do ranking.", text:"Empresas operacionais e bancos são avaliados por métricas compatíveis com seus demonstrativos. Liquidez, rentabilidade, geração de caixa, solvência e disponibilidade dos dados eliminam casos não comparáveis.", uses:"ROIC ou ROE, caixa, dívida, valuation e liquidez", blocks:"Dados ausentes, fragilidade financeira e baixa negociabilidade", produces:"Universo elegível da revisão", rule:"<strong>Regra:</strong> ausência de evidência não vira aprovação." },
  optimizer: { number:"01 · CÁLCULO", title:"Valor, qualidade e momento formam a cesta.", text:"As configurações candidatas combinam fatores, número de posições e orçamento de ações. A configuração do ano é escolhida pelo Sharpe dos anos já encerrados; os ativos recebem pesos proporcionais à pontuação dentro das regras, e o CDI recebe o saldo.", uses:"Fatores fundamentais e de mercado, custos e limites", blocks:"Escolha baseada no retorno futuro", produces:"Carteira anual e custo de rebalanceamento", rule:"<strong>Comparação:</strong> o MVO é calculado separadamente sobre o mesmo universo elegível. Ele não escolhe a carteira Benevente." },
  explanation: { number:"02 · EXPLICAÇÃO", title:"A linguagem recebe uma decisão já fechada.", text:"O modelo recebe somente fatos aprovados sobre a cesta, transforma-os em uma justificativa legível e destaca riscos e perguntas para revisão. Ele não consulta retornos futuros, não muda a lista de ativos e não define pesos.", uses:"Fatos aprovados e referências do dossiê", blocks:"Números inventados e alteração da carteira", produces:"Tese, riscos e perguntas de revisão", rule:"<strong>Avaliação:</strong> fidelidade, completude, cobertura de riscos e ausência de números inventados são medidas separadamente do retorno." },
  risk: { number:"05 · CONTROLE DE RISCO", title:"O Benevente 2 pode reduzir exposição durante o ano.", text:"A cesta fundamentalista não muda. Se queda ou volatilidade do Ibovespa cruzarem níveis predefinidos, parte da carteira migra temporariamente para CDI no pregão seguinte. Em paralelo, o Gemini classifica notícias e fatos relevantes para alertar o revisor, sem mudar pesos.", uses:"Ibovespa até o fechamento anterior e radar de eventos", blocks:"Reação com informação futura e ordem automática", produces:"Exposição entre 35% e o peso anual, mais alertas humanos", rule:"<strong>Status:</strong> extensão de risco acompanhada em carteira-sombra desde 2026. O histórico continua retrospectivo e o radar não entra no retorno publicado." },
  review: { number:"03 · DECISÃO", title:"O resultado é uma proposta, não uma ordem.", text:"O revisor humano confere tese, riscos, pesos e custos. Se decidir implementar, registra a operação e confere a nota de corretagem depois.", uses:"Proposta, evidências e custo estimado", blocks:"Execução automática", produces:"Carteira-sombra e registro de decisão", rule:"<strong>Regra:</strong> resultados prospectivos ficam separados do backtest histórico." }
};

let currentProfile = "moderado";
let currentDossierStrategy = "b1";
let selectedCurves = new Set();
const extraSeries = { 1: {}, 2: {}, 3: {}, 5: {}, 11: {} };
const addedSeries = new Map();
let chartSource = "ticker";
let chartZoom = 1;
let chartFocus = null;
let chartScale = "linear";
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
// Os três perfis declarados, pelo nome com que as séries chegam. Serve de
// discriminador em toda parte que precise separar política de referência.
// Os degraus da escada, com o rótulo que a evidência publica. Escrever a lista
// à mão fez a heurística do caixa quebrar quando a escada ganhou um quarto
// degrau: sobravam dois nomes onde ela precisa de um. A ordem é do mais
// apertado ao mais solto, como no questionário.
const PROFILE_SERIES = ["Ultraconservador", "Conservador", "Equilibrado", "Arrojado"];
// O caixa é a série que não é perfil nem mercado. Descobri-la em vez de fixá-la
// pelo nome é o que impede que a próxima política renomeie o instrumento e
// apague o resumo da home sem que nenhum teste perceba.
const MARKET_SERIES = ["Ibovespa", "BOVA11"];
const cashSeriesName = names =>
  names.find(name => !PROFILE_SERIES.includes(name) && !MARKET_SERIES.includes(name));
const colors = { "Ultraconservador":"#a8d5cb", "Conservador":"#7fc0b4", "Equilibrado":"#20a486", "Arrojado":"#0f766e", "Benevente":"#0f766e", "Benevente 1":"#0f766e", "Benevente 2":"#20a486", "Benevente Wealth System":"#0f766e", "Benevente Wealth System (MVO)":"#0f766e", "Benevente Quant AI":"#0f766e", "Benevente após IR":"#5aa79c", "MVO anual":"#ae8871", "MVO de referência":"#ae8871", "MVO clássico (elegível)":"#ae8871", "MVO clássico":"#ae8871", "CDI":"#3b779a", "Tesouro Selic":"#3b779a", "CDI após IR":"#8fb3c8", "Ibovespa":"#7a8490" };
// Any string that reaches innerHTML has to be escaped, including strings the
// user typed into the compare box and the name of a file they imported. Nothing
// here is persisted or shared, so the exposure is to the person's own browser
// rather than to other visitors, but an unescaped sink is an unescaped sink and
// the fix costs one function.
const escapeHtml = value => String(value ?? "").replace(/[&<>"'`]/g, character => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;", "`": "&#96;",
}[character]));
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
  // Every track is compounded on the same decision dates. The MVO reference is
  // now an independent optimisation over the eligible universe, and the market
  // references come from the run itself instead of a separately aligned blob.
  const tracks = {
    "Benevente 1": "net_return",
    "Benevente 2": "benevente2_return",
    "MVO de referência": "mvo_eligible_net_return",
    "CDI": "cdi_net_return",
    "Ibovespa": "benchmark_IBOVESPA",
  };
  const series = {};
  Object.entries(tracks).forEach(([name, column]) => {
    if (!rows.every(item => Number.isFinite(Number(item[column])))) return;
    series[name] = [100];
    rows.forEach(item => series[name].push(+(series[name].at(-1) * (1 + Number(item[column]))).toFixed(4)));
  });
  return { dates, series };
}
// Month ends of the exact daily book value. Eleven January points could not
// show a drawdown or when a year turned; the raw daily series reads as a smear
// at page width. Roughly a hundred monthly points is the readable middle.
function monthlyDataset(period) {
  const curve = researchData?.monthly_curve;
  const years = comparisonWindows[period];
  if (!curve?.dates?.length || !years) return null;
  const last = new Date(`${curve.dates.at(-1)}T12:00:00`);
  const cutoff = new Date(last);
  cutoff.setFullYear(cutoff.getFullYear() - years);
  const evaluationStart = curve.evaluation_starts ? new Date(`${curve.evaluation_starts}T12:00:00`) : null;
  const effectiveCutoff = evaluationStart && evaluationStart > cutoff ? evaluationStart : cutoff;
  let start = curve.dates.findIndex(date => new Date(`${date}T12:00:00`) >= effectiveCutoff);
  if (start < 0) start = 0;
  if (curve.dates.length - start < 3) start = Math.max(0, curve.dates.length - 3);
  const dates = curve.dates.slice(start);
  const series = {};
  Object.entries(curve.series).forEach(([name, values]) => {
    const window = values.slice(start);
    const base = window.find(value => Number.isFinite(value) && value > 0);
    if (base) series[name] = window.map(value => Number.isFinite(value) ? +(value / base * 100).toFixed(4) : null);
  });
  const phases = Array.isArray(curve.phases) ? curve.phases.slice(start) : null;
  return Object.keys(series).length
    ? { dates, series, granularity: "monthly", phases, evaluationStarts: curve.evaluation_starts, note: curve.selection_note }
    : null;
}

// Catmull-Rom through the points, converted to cubic Bezier. Control points are
// clamped inside each segment's own range so a smooth curve never invents a
// peak or a trough the data does not contain.
function smoothPath(points) {
  if (points.length < 2) return "";
  if (points.length === 2) return `M${points[0].x},${points[0].y} L${points[1].x},${points[1].y}`;
  const clamp = (value, a, b) => Math.min(Math.max(value, Math.min(a, b)), Math.max(a, b));
  let path = `M${points[0].x.toFixed(2)},${points[0].y.toFixed(2)}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const p0 = points[index - 1] || points[index];
    const p1 = points[index];
    const p2 = points[index + 1];
    const p3 = points[index + 2] || p2;
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = clamp(p1.y + (p2.y - p0.y) / 6, p1.y, p2.y);
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = clamp(p2.y - (p3.y - p1.y) / 6, p1.y, p2.y);
    path += ` C${c1x.toFixed(2)},${c1y.toFixed(2)} ${c2x.toFixed(2)},${c2y.toFixed(2)} ${p2.x.toFixed(2)},${p2.y.toFixed(2)}`;
  }
  return path;
}

function profileDataset(period) {
  const monthly = monthlyDataset(period);
  if (monthly) return monthly;
  return annualCurve(period);
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
  // ``cumulative`` travels with the rest so a caller working from a plotted
  // series does not have to recover it from a second, unrelated source.
  return { cagr, cumulative, volatility, drawdown };
}

function pct(value, digits = 1) { return `${value >= 0 ? "+" : ""}${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`; }
function plainPct(value, digits = 1) { return `${(value * 100).toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`; }
function selectedAnnualDecision() {
  const year = Number(document.querySelector("#decision-year")?.value);
  const rows = researchData?.annual || [];
  return rows.find(item => item.decision_year === year) || rows.at(-1);
}

function activeProfileKey() {
  return ({ conservador: "conservador", moderado: "equilibrado", arrojado: "arrojado" })[currentProfile] || "equilibrado";
}

function activeProfileLabel() {
  return "Carteira Benevente";
}

function activePolicy() {
  const policy = profiles[currentProfile];
  // Os tetos vêm do artefato da política, não da tabela acima. Escritos à mão,
  // eles discordavam do registro: o teto por ativo aparecia como 10%, 17,6% e
  // 15% enquanto a política declara 4,67%, 11% e 24%. Número repetido em dois
  // lugares é a forma mais barata de publicar dois números diferentes, e aqui
  // ele decide os pesos que a prévia mostra. A tabela fica como reserva para o
  // caso de o artefato não carregar, e um teste exige que as duas concordem.
  const declarado = ladderEvidence?.profiles?.[activeProfileKey()]?.declared;
  const equity = declarado ? Number(declarado.maximum_equity_weight) * 100 : Number(policy.equity);
  const issuer = declarado ? Number(declarado.maximum_asset_weight) * 100 : Number(policy.issuer);
  return {
    ...policy,
    equity: Math.max(0, Math.min(100, equity || 0)),
    issuer: Math.max(1, Math.min(100, issuer || 1)),
  };
}

function activeProfileRows() {
  return researchData?.annual || [];
}

function dossierStrategy() {
  return currentDossierStrategy === "b2"
    ? { key: "b2", name: "Benevente 2", short: "B2", returnKey: "benevente2_return", operation: "Controle de risco durante o ano" }
    : { key: "b1", name: "Benevente 1", short: "B1", returnKey: "net_return", operation: "Pesos mantidos até a revisão anual" };
}

function syncDossierStrategyButtons() {
  document.querySelectorAll("[data-dossier-strategy]").forEach(button => {
    const active = button.dataset.dossierStrategy === currentDossierStrategy;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
}

function renderProfileHistory() {
  if (!document.querySelector("#decision-year")) return;
  const container = document.querySelector("#profile-history");
  if (!container || !researchData) return;
  const rows = activeProfileRows();
  if (!rows.length) { container.innerHTML = ""; return; }
  const strategy = dossierStrategy();
  container.innerHTML = `<div class="profile-history-head"><div><span class="control-label">ANO A ANO</span><b>${strategy.name}</b><small>${strategy.operation}. Clique em um ano para abrir a decisão.</small></div><span>${rows.length} anos completos</span></div><div class="profile-year-grid">${rows.map(row => `<button type="button" class="profile-year ${String(selectedAnnualDecision()?.decision_year) === String(row.decision_year) ? "active" : ""}" data-year="${row.decision_year}" aria-label="${strategy.name} em ${row.decision_year}: ${pct(Number(row[strategy.returnKey]))}"><small>${row.decision_year}</small><b>${pct(Number(row[strategy.returnKey]))}</b><span>${strategy.short} · CDI ${pct(row.cdi_net_return)}</span></button>`).join("")}</div>`;
  container.querySelectorAll(".profile-year").forEach(button => button.addEventListener("click", () => {
    document.querySelector("#decision-year").value = button.dataset.year;
    renderAssetWorkbench(); renderProfileHistory();
  }));
}

function configurationLabel(value) {
  const match = String(value || "").match(/^eq(\d+)_n(\d+)_(.+)$/);
  if (!match) return "configuração anual documentada";
  const factors = {
    triple_factor: "valor, qualidade e comportamento de preços",
    value_quality: "valor e qualidade",
    low_volatility: "baixa volatilidade",
    momentum_12m: "comportamento de preços em 12 meses",
  };
  return `${match[1]}% em ações · mínimo de ${match[2]} emissores · ${factors[match[3]] || "fatores quantitativos"}`;
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
  if (!document.querySelector("#asset-grid")) return;
  if (!researchData) return;
  const decision = selectedAnnualDecision();
  if (!decision) return;
  const holdingsSource = researchData.holdings;
  const transitionsSource = researchData.transitions;
  const holdings = holdingsSource.filter(item => item.decision_year === decision.decision_year);
  const transitions = transitionsSource.filter(item => item.decision_year === decision.decision_year);
  const equities = holdings.filter(item => item.ticker !== "TITULO_CDI");
  const equityWeight = equities.reduce((sum, item) => sum + item.weight, 0);
  const transitionByTicker = Object.fromEntries(transitions.map(item => [item.ticker, item]));
  const strategy = dossierStrategy();
  const selected = configurationLabel(decision.selected_configuration);
  document.querySelector("#dossier-policy").textContent = strategy.key === "b2"
    ? `${selected}. A cesta nasce em janeiro como no Benevente 1. Durante o ano, alertas de mercado podem reduzir proporcionalmente as ações e aumentar o CDI.`
    : `${selected}. A cesta e os pesos de janeiro são mantidos até a próxima revisão anual.`;
  const coverage = researchData.meta.coverage;
  const source = researchData.meta.source_tier === "public_reproducible_research" ? "fonte pública de pesquisa" : "fonte qualificada";
  const series = coverage.price_tickers ? `${coverage.price_tickers.toLocaleString("pt-BR")} séries ajustadas` : "séries ajustadas";
  document.querySelector("#research-status").innerHTML = `<b>Pesquisa reproduzível, ainda não validada para uso institucional.</b><span>O painel usa ${escapeHtml(series)}, CDI do BCB e ${coverage.fundamental_snapshots?.toLocaleString("pt-BR") || "—"} registros fundamentais da CVM disponíveis em cada decisão. A tentativa de reconciliação com a página atual da B3 foi executada e bloqueou o selo institucional; uma base histórica primária ou licenciada ainda é necessária.</span>`;
  const b2Return = Number(decision.benevente2_return);
  const selectedReturn = Number(decision[strategy.returnKey]);
  const b2Config = researchData.meta?.benevente2?.training_only_selection?.configuration || {};
  const alertEquity = Math.min(equityWeight, Number(b2Config.alert_equity_cap) || .50);
  const severeEquity = Math.min(equityWeight, Number(b2Config.severe_equity_cap) || .35);
  const exposureSummary = strategy.key === "b2"
    ? `Janeiro ${plainPct(equityWeight)} · alerta ${plainPct(alertEquity)} · estresse ${plainPct(severeEquity)}`
    : `${plainPct(equityWeight)} em ações durante o ciclo anual`;
  document.querySelector("#asset-summary").innerHTML = `<div><small>CARTEIRA SELECIONADA</small><strong>${strategy.name}</strong><span>${strategy.operation}.</span></div><div><small>RESULTADO DO ANO</small><strong>${Number.isFinite(selectedReturn) ? pct(selectedReturn) : "—"}</strong><span>${formatDateBr(decision.decision_date)} a ${formatDateBr(decision.holding_end_exclusive)}.</span></div><div><small>EXPOSIÇÃO EM AÇÕES</small><strong>${plainPct(equityWeight)}</strong><span>${exposureSummary}.</span></div><div><small>REFERÊNCIAS</small><strong>CDI ${pct(decision.cdi_net_return)}</strong><span>MVO ${pct(decision.mvo_eligible_net_return)} · Ibovespa ${pct(decision.benchmark_IBOVESPA)}</span></div>`;
  document.querySelector("#asset-grid").innerHTML = holdings.map(item => {
    const transition = transitionByTicker[item.ticker];
    const isCdi = item.ticker === "TITULO_CDI";
    const status = isCdi ? "Parcela CDI" : (item.decision_action_pt || "Mantido");
    const signal = item.trailing_12m_return_at_decision == null ? "Não aplicável" : plainPct(item.trailing_12m_return_at_decision);
    const volatility = item.trailing_12m_volatility_at_decision == null ? "Não aplicável" : plainPct(item.trailing_12m_volatility_at_decision);
    const currentReason = transition?.reason_pt || "Mantido segundo a política e a revisão anual.";
    const actionClass = ({ Entrada: "entered", Aumento: "increased", Redução: "reduced", Saída: "exited" })[status] || (isCdi ? "defensive" : "maintained");
    const alertWeight = isCdi ? 1 - alertEquity : item.weight * alertEquity / Math.max(equityWeight, .0001);
    const severeWeight = isCdi ? 1 - severeEquity : item.weight * severeEquity / Math.max(equityWeight, .0001);
    const allocationDetail = strategy.key === "b2"
      ? `<div class="asset-allocation-path"><span>Janeiro <b>${plainPct(item.weight)}</b></span><span>Alerta <b>${plainPct(alertWeight)}</b></span><span>Estresse <b>${plainPct(severeWeight)}</b></span></div>`
      : `<div class="asset-allocation-path single"><span>Peso mantido no ano <b>${plainPct(item.weight)}</b></span></div>`;
    return `<article class="asset-card ${isCdi ? "defensive" : ""}"><div class="asset-card-top"><div><small>${isCdi ? "PARCELA CDI" : "ATIVO ELEGÍVEL"}</small><h3>${isCdi ? "CDI" : item.ticker.replace(".SA", "")}</h3></div><span class="asset-status ${actionClass}">${status}</span></div>${allocationDetail}<div class="asset-metrics"><div><small>12M ANTERIOR</small><b>${signal}</b></div><div><small>VOL. 12M</small><b>${volatility}</b></div></div><p><b>Critério:</b> ${item.decision_rationale_pt || item.decision_rationale}</p><p><b>Revisão:</b> ${currentReason}</p><div class="asset-return"><b>Resultado observado depois da decisão</b>${pct(item.realised_next_year_return)} no período anual. Mostrado para avaliar a regra, não para justificar a entrada.</div><div class="asset-weight"><span>Score na decisão: ${item.value_quality_score == null ? "não calculado" : item.value_quality_score.toLocaleString("pt-BR", {minimumFractionDigits:2,maximumFractionDigits:2})}</span><strong>${item.decision_action_pt || ""}</strong></div></article>`;
  }).join("");
  const panel = document.querySelector("#asset-action-panel");
  panel.classList.add("active");
  const difference = Number.isFinite(b2Return) ? b2Return - Number(decision.net_return) : null;
  panel.innerHTML = strategy.key === "b2"
    ? `<div><span class="action-label">SELEÇÃO DE JANEIRO</span><b>Mesmos ativos e pesos-base do Benevente 1.</b><p>Valor, qualidade e comportamento de preços definem os nomes antes do início do período.</p></div><div><span class="action-label">CONTROLE DURANTE O ANO</span><b>${difference == null ? "Exposição variável" : `${pct(difference)} frente ao Benevente 1`}</b><p>Com dados conhecidos até o fechamento anterior, alertas reduzem todas as ações proporcionalmente. O valor liberado passa para CDI.</p></div><div><span class="action-label">REVISÃO DOS ATIVOS</span><b>${formatDateBr(decision.holding_end_exclusive)}</b><p>A lista de ativos só muda na revisão anual. Notícias classificadas pelo radar geram alerta humano, sem ordem automática.</p></div>`
    : `<div><span class="action-label">SELEÇÃO DE JANEIRO</span><b>Valor, qualidade e comportamento de preços.</b><p>A regra escolhe a cesta somente com dados disponíveis antes da decisão.</p></div><div><span class="action-label">DURANTE O ANO</span><b>Pesos fixos até a revisão.</b><p>Oscilações e notícias não alteram a exposição. Cada ativo permanece com o peso definido em janeiro.</p></div><div><span class="action-label">PRÓXIMA DECISÃO</span><b>${formatDateBr(decision.holding_end_exclusive)}</b><p>Na revisão anual, os dados são atualizados e a regra decide quais posições manter, reduzir, retirar ou incluir.</p></div>`;
}

function refreshDecisionStudio() {
  if (!researchData) return;
  syncDecisionYears();
  renderAssetWorkbench();
  renderProfileHistory();
  renderComparison(currentPeriod);
}

function pctPlain(value) { return Number.isFinite(value) ? `${(value * 100).toLocaleString("pt-BR", {maximumFractionDigits: 1})}%` : "não calculado"; }
function signedScenario(value) { return Number.isFinite(value) ? `${value >= 0 ? "+" : ""}${pctPlain(value)}` : "não calculado"; }

function renderForecast() {
  if (!document.querySelector("#scenario-chart")) return;
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
  document.querySelector("#scenario-limitations").innerHTML = forecastData.limitations.map(note => `<span>${escapeHtml(note)}</span>`).join("");
}

function renderCurrentDecision() {
  if (!document.querySelector("#current-decision-assets")) return;
  if (!currentDecisionData) return;
  const { universe, holdings, monitoring, decision_date: date } = currentDecisionData;
  const policy = activePolicy();
  const hasMinimumDiversification = holdings.length >= 5;
  const requestedEquity = Math.min(policy.equity / 100, 1);
  const feasibleEquity = Math.min(requestedEquity, holdings.length * policy.issuer / 100);
  const visibleHoldings = hasMinimumDiversification ? holdings.map(asset => ({ ...asset, weight: feasibleEquity / holdings.length })).filter(asset => asset.weight > .0001) : [];
  const cdiWeight = Math.max(0, 1 - visibleHoldings.reduce((sum, asset) => sum + asset.weight, 0));
  const capital = Number(document.querySelector("#wealth")?.value) || 0;
  const monitoringProfile = monitoring?.profiles?.[activeProfileKey()];
  const partialReturn = monitoringProfile?.portfolio_partial_return;
  const profileName = ({ conservador: "Conservadora", moderado: "Equilibrada", arrojado: "Arrojada" })[currentProfile] || "Equilibrada";
  const requestedLabel = ({ conservador: "Conservador", moderado: "Equilibrado", arrojado: "Arrojado" })[currentProfile] || "Equilibrado";
  document.querySelector("#current-decision-heading").innerHTML = `Prévia de janeiro<br /><em>de 2026.</em>`;
  document.querySelector("#current-decision-intro").textContent = hasMinimumDiversification ? `A prévia usa a mesma triagem histórica do Benevente Wealth System, antes do período acompanhado.` : `A política exige ao menos cinco ações. A triagem de ${formatDateBr(date)} encontrou apenas ${holdings.length} com cobertura completa, por isso nenhuma carteira é sugerida.`;
  document.querySelector("#current-decision-label").textContent = hasMinimumDiversification ? `PRÉVIA · ${requestedLabel.toUpperCase()}` : "PRÉVIA BLOQUEADA";
  document.querySelector("#current-decision-summary").innerHTML = [
    ["DECISÃO", formatDateBr(date)],
    ["AÇÕES", hasMinimumDiversification ? pctPlain(1 - cdiWeight) : "Mínimo não atingido"],
    ["RESULTADO PARCIAL", hasMinimumDiversification && Number.isFinite(partialReturn) ? signedScenario(partialReturn) : "Não calculado"],
  ].map(([label, value]) => `<div><small>${label}</small><b>${value}</b></div>`).join("");
  document.querySelector("#current-decision-assets").innerHTML = hasMinimumDiversification ? [...visibleHoldings.map(asset => `<article class="suggestion-asset"><div class="suggestion-row"><div><small>ATIVO SELECIONADO</small><b>${escapeHtml(asset.ticker)}</b></div><div><small>PESO · ${money.format(capital * asset.weight)}</small><strong>${pctPlain(asset.weight)}</strong></div></div><p>${escapeHtml(asset.why)}</p></article>`), cdiWeight > .0001 ? `<article class="suggestion-asset"><div class="suggestion-row"><div><small>RESERVA DEFENSIVA</small><b>CDI</b></div><div><small>PESO · ${money.format(capital * cdiWeight)}</small><strong>${pctPlain(cdiWeight)}</strong></div></div><p>Reserva resultante do teto de renda variável da política selecionada.</p></article>` : ""].join("") : `<article class="suggestion-asset"><div class="suggestion-row"><div><small>CONTROLE DE DIVERSIFICAÇÃO</small><b>Carteira não formada</b></div><div><small>EXIGIDO</small><strong>5 ações</strong></div></div><p>Foram encontradas ${holdings.length} ações com dados completos. O Benevente não completa a carteira com nomes sem a mesma cobertura apenas para exibir uma sugestão.</p></article>`;
  const feasibility = feasibleEquity < requestedEquity ? ` Com os ${holdings.length} ativos processados nesta prévia, a exposição atingida é ${pctPlain(feasibleEquity)}; o restante fica em CDI.` : "";
  const monitoringText = hasMinimumDiversification && Number.isFinite(partialReturn)
    ? ` Até ${formatDateBr(monitoring?.through || date)}: ações ${signedScenario(monitoringProfile.equity_price_return)}, CDI ${signedScenario(monitoringProfile.cdi_return)} e carteira ${signedScenario(partialReturn)}. ${monitoring?.label || ""}`
    : " Aguardando preços e CDI suficientes para calcular a carteira deste perfil.";
  document.querySelector("#current-decision-caption").textContent = hasMinimumDiversification ? `Prévia de pesquisa. Perfil ${requestedLabel}: teto de ${policy.equity}% em renda variável e ${policy.issuer}% por emissor.${feasibility}${monitoringText}` : `Prévia bloqueada: são necessárias cinco ações com dados comparáveis. O monitoramento parcial não é exibido como desempenho de uma carteira que não foi formada.`;
}

function moneyCompact(value) { return new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL",notation:"compact",maximumFractionDigits:1}).format(value || 0); }
function renderUniverse() {
  if (!document.querySelector("#universe-table")) return;
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
wealthOut.value = money.format(wealth.value);
wealth.addEventListener("input", () => {
  wealthOut.value = money.format(wealth.value);
  // Os cards seguem o cursor. Esperar o envio fazia o controle parecer inerte,
  // que foi exatamente a reclamação que motivou esta seção.
  renderWealthCards(currentPeriod);
});
document.querySelectorAll(".choice").forEach(button => button.addEventListener("click", () => {
  document.querySelectorAll(".choice").forEach(item => item.classList.remove("active"));
  button.classList.add("active"); currentProfile = button.dataset.profile;
  selectedCurves = new Set(); chartZoom = 1; chartFocus = null;
  refreshDecisionStudio();
}));


// Quanto o patrimônio escolhido teria virado em cada alternativa, na janela
// aberta. Repetir a política em reais nao respondia nada: 55% de qualquer
// quantia continua sendo 55%. A pergunta util e comparativa, e por isso as tres
// series aparecem lado a lado com o multiplo, nao so com o valor final.
function renderWealthCards(period) {
  const host = document.querySelector("#wealth-cards");
  const data = profileDataset(period);
  if (!host || !data) return;
  const capital = Math.max(0, Number(document.querySelector("#wealth")?.value) || 0);
  // Um cartão por série plotada: os três perfis declarados e as referências.
  // O cartão de estratégia única morreu junto com a estratégia única.
  const note = { "Conservador": "35% em ações · 12 emissores", "Equilibrado": "55% em ações · 8 emissores",
                 "Arrojado": "75% em ações · 5 emissores", "Tesouro Selic": "Custo de oportunidade do caixa", "Ibovespa": "Mercado brasileiro" };
  const kind = name => note[name]?.includes("emissores") ? "primary" : "benchmark";
  const cards = Object.entries(data.series).map(([name, values], index) => {
    const first = values.find(Number.isFinite), last = values.at(-1);
    if (!Number.isFinite(first) || !Number.isFinite(last)) return "";
    const factor = last / first, final = capital * factor, gain = final - capital;
    const finalStr = money.format(final);
    const sizeClass = finalStr.length > 14 ? " num-xl" : finalStr.length > 11 ? " num-lg" : "";
    return `<article class="wealth-card ${kind(name)}" style="--series-color:${seriesColor(name, index)}"><header><b>${escapeHtml(name)}</b><small>${escapeHtml(note[name] || "Série do gráfico")}</small></header><strong class="wealth-value${sizeClass}">${finalStr}</strong><div class="wealth-card-foot"><span>${factor.toLocaleString("pt-BR", {minimumFractionDigits: 1, maximumFractionDigits: 1})}x o valor aplicado</span><span class="${gain >= 0 ? "up" : "down"}">${gain >= 0 ? "+" : "−"}${money.format(Math.abs(gain))}</span></div></article>`;
  }).join("");
  const start = data.dates[0], finish = data.dates.at(-1);
  host.innerHTML = `<p class="wealth-cards-lede">O mesmo capital, aplicado em ${formatDateBr(start)} e mantido até ${formatDateBr(finish)}, sem aportes, em cada política declarada.</p><div class="wealth-cards-grid">${cards}</div>`;
}

function renderCurveToggles(period) {
  const series = seriesFor(period), names = Object.keys(series);
  // The after-tax pair stays available but off by default: seven lines at once
  // is unreadable, and the gross series are the ones the benchmarks match.
  if (!selectedCurves.size || [...selectedCurves].some(name => !names.includes(name))) {
    selectedCurves = new Set(names);
  }
  document.querySelector("#curve-toggles").innerHTML = names.map((name, index) => `<button type="button" class="curve-toggle ${selectedCurves.has(name) ? "active" : ""}" data-kind="${escapeHtml(name)}" style="--series-color:${seriesColor(name, index)}"><i></i>${escapeHtml(name)}</button>`).join("");
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
  const width=900, height=410, left=82, right=28, top=18, bottom=40, plotW=width-left-right, plotH=height-top-bottom;
  const x = index => left + index * plotW / Math.max(dates.length - 1, 1);
  const y = value => top + (max - transformed(value)) * plotH / Math.max(max-min, .0001);
  const grid = Array.from({length:5}, (_, index) => min + index * (max-min) / 4).map(value => {
    const rawValue = chartScale === "log" ? Math.exp(value) : value;
    const yPosition = top + (max - value) * plotH / Math.max(max-min, .0001);
    return `<line class="line-grid" x1="${left}" x2="${width-right}" y1="${yPosition}" y2="${yPosition}"/><text class="line-grid-label" text-anchor="end" x="${left - 10}" y="${yPosition + 3}">${(rawValue - 100).toLocaleString("pt-BR", {maximumFractionDigits:0})}%</text>`;
  }).join("");
  // One tick per year when the window is long, otherwise per observation. A
  // three-label axis made it impossible to tell which year a move belonged to.
  const tickIndexes = [];
  let lastLabelYear = null;
  dates.forEach((date, index) => {
    const year = String(date).slice(0, 4);
    if (year !== lastLabelYear) { tickIndexes.push(index); lastLabelYear = year; }
  });
  if (!tickIndexes.includes(dates.length - 1)) tickIndexes.push(dates.length - 1);
  const dense = tickIndexes.length > 9;
  const dateLabels = tickIndexes.filter((_, position) => !dense || position % 2 === 0 || position === tickIndexes.length - 1)
    .map(index => {
      const anchor = index === 0 ? "start" : index === dates.length - 1 ? "end" : "middle";
      const label = dates.length > 24 ? String(dates[index]).slice(0, 4) : formatDateBr(dates[index]);
      return `<line class="line-grid" x1="${x(index)}" x2="${x(index)}" y1="${top}" y2="${height - bottom}" opacity=".45"/>`
        + `<text class="line-grid-label" text-anchor="${anchor}" x="${x(index)}" y="${height-24}">${label}</text>`;
    }).join("");
  const strategyName = selected.find(name => name.startsWith("Benevente"));
  lineLayer.innerHTML = selected.map((name, seriesIndex) => {
    const runs = [];
    let current = [];
    visibleSeries[name].forEach((value, index) => {
      if (!Number.isFinite(value)) { if (current.length) runs.push(current); current = []; return; }
      current.push({ x: x(index), y: y(value) });
    });
    if (current.length) runs.push(current);
    const boundary = data.phases ? data.phases.findIndex(phase => phase === "evaluated") : -1;
    const path = runs.map(smoothPath).join(" ");
    const reference = name === "MVO anual" || name === "MVO de referência";
    const area = name === strategyName && runs.length === 1 && runs[0].length > 1
      ? `<path class="line-area" fill="${seriesColor(name, seriesIndex)}" d="${smoothPath(runs[0])} L${runs[0].at(-1).x.toFixed(2)},${height - bottom} L${runs[0][0].x.toFixed(2)},${height - bottom} Z"/>`
      : "";
    // The selection stretch is redrawn on top, faded and dashed. It is the same
    // curve; what changes is the claim attached to it.
    let selection = "";
    if (boundary > 0) {
      const points = visibleSeries[name].slice(0, boundary + 1)
        .map((value, index) => Number.isFinite(value) ? { x: x(index), y: y(value) } : null).filter(Boolean);
      if (points.length > 1) {
        selection = `<path class="line-path line-selection" data-series="${escapeHtml(name)}" stroke="${seriesColor(name, seriesIndex)}" d="${smoothPath(points)}"/>`;
      }
    }
    return `${area}<path class="line-path ${reference ? "mvo-reference" : ""}" data-series="${escapeHtml(name)}" stroke="${seriesColor(name, seriesIndex)}" d="${path}"/>${selection}`;
  }).join("");
  // The legend and return chips carry the labels. End labels overlap when
  // funds, benchmarks and user-selected assets converge at the same point.
  directLabelLayer.innerHTML = "";
    const boundaryIndex = data.phases ? data.phases.slice(startIndex, endIndex).findIndex(phase => phase === "evaluated") : -1;
  const boundaryMark = boundaryIndex > 0
    ? `<line class="line-boundary" x1="${x(boundaryIndex)}" x2="${x(boundaryIndex)}" y1="${top}" y2="${height - bottom}"/>`
      + `<text class="line-boundary-label" x="${x(boundaryIndex) + 6}" y="${top + 12}">início da avaliação</text>`
    : "";
  gridLayer.innerHTML = grid + boundaryMark; labelLayer.innerHTML = `${dateLabels}<text class="line-axis-title" text-anchor="middle" x="18" y="${top + plotH / 2}" transform="rotate(-90 18 ${top + plotH / 2})">Retorno acumulado (%)</text><text class="line-axis-title" text-anchor="middle" x="${left + plotW / 2}" y="${height - 5}">Data de observação</text>`;
  document.querySelector("#chart-return-summary").innerHTML = selected.map((name, index) => {
    const series = allSeries[name].slice(startIndex, endIndex);
    const first = series.find(value => Number.isFinite(value));
    const last = [...series].reverse().find(value => Number.isFinite(value));
    const returnPct = (last / first - 1) * 100;
    return `<span style="--series-color:${seriesColor(name, index)}"><i></i><b>${escapeHtml(name)}</b><strong>${returnPct >= 0 ? "+" : ""}${returnPct.toLocaleString("pt-BR", {maximumFractionDigits:1})}%</strong></span>`;
  }).join("");
  const start = dates[0], end = dates.at(-1);
  document.querySelector("#chart-zoom-status").textContent = chartZoom === 1 ? "Visão completa" : `${dates.length} pontos visíveis`;
  const granularity = data.granularity === "monthly"
    ? `${dates.length} pontos mensais (valor exato da carteira no fim de cada mês)`
    : `${dates.length} pontos anuais`;
  // A legenda dizia apenas a extensão do desenho, que começa antes da avaliação
  // porque inclui a janela de seleção. Lida ao lado de "11 anos" no cabeçalho,
  // parecia contradição. Agora as duas datas são nomeadas pelo que são.
  const evaluationStart = boundaryIndex > 0 ? dates[boundaryIndex] : null;
  const window = evaluationStart
    ? `avaliação de ${formatDateBr(evaluationStart)} a ${formatDateBr(end)}, com o contexto desde ${formatDateBr(start)}`
    : `${formatDateBr(start)} a ${formatDateBr(end)}`;
  const phaseNote = data.note && boundaryIndex > 0 ? ` ${data.note}` : "";
  document.querySelector("#line-chart-caption").textContent = `${selected.length} série(s) · ${granularity} · ${window} · retorno acumulado em %. Escala ${chartScale === "log" ? "logarítmica" : "linear"}. Roda do mouse amplia, arraste desloca.${phaseNote}`;
  const inspect = event => {
    const rect = event.currentTarget.getBoundingClientRect();
    const viewX = (event.clientX - rect.left) * width / rect.width;
    const index = Math.max(0, Math.min(dates.length - 1, Math.round((viewX - left) / plotW * (dates.length - 1))));
    const cursor = document.querySelector("#line-chart-cursor"); cursor.classList.remove("hidden"); cursor.setAttribute("x1", x(index)); cursor.setAttribute("x2", x(index)); cursor.setAttribute("y1", top); cursor.setAttribute("y2", height-bottom);
    const readings = selected.map((name, order) => {
      const value = visibleSeries[name][index];
      const base = visibleSeries[name].find(Number.isFinite);
      const text = Number.isFinite(value) ? pct(value / base - 1) : "—";
      return { name, text, value: Number.isFinite(value) ? value / base : -Infinity, color: seriesColor(name, order) };
    }).sort((first, second) => second.value - first.value);
    document.querySelector("#chart-inspector").innerHTML =
      `<b>${formatDateBr(dates[index])}</b>` + readings.map(item =>
        `<span class="inspector-item" style="--series-color:${item.color}"><i></i>${escapeHtml(item.name)} <strong>${item.text}</strong></span>`).join("");
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
  const statsFor = column => rows.every(item => Number.isFinite(Number(item[column])))
    ? wealthStats(rows.map(item => Number(item[column]))) : null;
  const winsAgainst = (column, strategyColumn = "net_return") =>
    rows.filter(item => Number(item[strategyColumn]) > Number(item[column])).length;
  const benevente = statsFor("net_return");
  const benevente2 = statsFor("benevente2_return");
  const mvo = statsFor("mvo_eligible_net_return");
  const cdi = statsFor("cdi_net_return");
  const afterTax = statsFor("net_return_after_tax");
  const cdiAfterTax = statsFor("cdi_net_return_after_tax");
  const ibovespa = statsFor("benchmark_IBOVESPA");
  const winCdi = winsAgainst("cdi_net_return");
  const winMvo = winsAgainst("mvo_eligible_net_return");
  const winMarket = ibovespa ? winsAgainst("benchmark_IBOVESPA") : null;
  const start = rows[0].decision_date, end = rows.at(-1).holding_end_exclusive;
  const versusCdi = benevente.cumulative - cdi.cumulative, versusMvo = benevente.cumulative - mvo.cumulative;
  document.querySelector("#period-description").textContent = `Janela avaliada: ${formatDateBr(start)} a ${formatDateBr(end)}, ${rows.length} ano(s), com custos modelados. O imposto incremental do Benevente 2 aparece na simulação em reais.`;
  const marketPhrase = winMarket === null ? "" : ` Contra o Ibovespa, venceu ${winMarket} de ${rows.length}.`;
  // A percentage is easy to nod at and hard to feel. The same number said in
  // reais is what a reader actually compares against the fund they already own,
  // so it travels beside every series instead of only in the headline.
  // The summary and the table below the chart used to be built from the retired
  // annual series while the chart itself plotted something else, so the two
  // could describe different strategies on the same screen. They are now
  // derived from the series actually plotted, whatever those are.
  const plotted = profileDataset(period);
  const plottedNames = plotted ? Object.keys(plotted.series) : [];
  const noteFor = {
    "Conservador": "Com proteção · 35% em ações, 12 emissores",
    "Equilibrado": "Com proteção · 55% em ações, 8 emissores",
    "Arrojado": "Com proteção · 75% em ações, 5 emissores",
    "Tesouro Selic": "Caixa: Tesouro Selic, líquido de custódia",
    "Ibovespa": "Índice de retorno total da B3",
  };
  const baseRows = plottedNames.map(name => {
    const stats = metricsForSeries(plotted.series[name], plotted.dates);
    return stats ? [name, stats, noteFor[name] || "Série do gráfico"] : null;
  }).filter(Boolean);
  // O discriminador é o nome do perfil, não a cópia ao lado dele. Já quebrou
  // uma vez: um ajuste de texto ("Política declarada" → "Com proteção") esvaziou
  // este filtro e a home passou a descrever a política aposentada.
  const ranked = baseRows.filter(([name]) => PROFILE_SERIES.includes(name));
  const cashName = cashSeriesName(baseRows.map(([name]) => name));
  const cash = baseRows.find(([name]) => name === cashName);
  document.querySelector("#comparison-summary").textContent = ranked.length && cash
    ? `Na janela escolhida: ${ranked.map(([name, stats]) => `${name} ${plainPct(stats.cumulative)}`).join("; ")}. ${cashName} ${plainPct(cash[1].cumulative)}. Retorno e queda sobem juntos, a escada é a escolha, não o número isolado.`
    : "Selecione uma janela para comparar os perfis declarados.";
  const extras = Object.entries(extraSeries[period] || {}).map(([name, values]) => {
    const metrics = metricsForSeries(values, profileDataset(period).dates);
    const firstAvailable = values.findIndex(value => Number.isFinite(Number(value)));
    const note = firstAvailable >= 0 ? `Disponível desde ${formatDateBr(profileDataset(period).dates[firstAvailable])}` : "Série adicionada";
    return metrics ? [name, { cumulative: values.at(-1) / values.find(Number.isFinite) - 1, cagr: metrics.cagr }, note] : null;
  }).filter(Boolean);
  document.querySelector("#comparison-table").innerHTML = [...baseRows, ...extras].map(([name, stats, note]) => `<tr><td>${escapeHtml(name)}</td><td><b>${plainPct(stats.cumulative)}</b><small>${plainPct(stats.cagr)}<br />a.a.</small></td><td>${escapeHtml(note)}</td></tr>`).join("");
  const reference = baseRows.find(([name]) => name === "Ibovespa");
  const spread = ranked.length && reference
    ? ` Contra o Ibovespa, de ${pct(ranked[0][1].cumulative - reference[1].cumulative)} a ${pct(ranked.at(-1)[1].cumulative - reference[1].cumulative)} conforme o perfil.`
    : "";
  document.querySelector("#research-note").textContent = ranked.length
    ? `As três curvas são políticas declaradas e congeladas antes do período, com a camada de risco intranual aplicada.${spread} A janela também desenvolveu as próprias regras, então descreve a amostra; a avaliação prospectiva começa na decisão de janeiro de 2027, e a carteira de 2026 segue a política anterior.`
    : "As curvas exibidas são políticas declaradas e congeladas antes do período; a janela descreve a amostra de desenvolvimento.";
  renderCurveToggles(period); renderLineChart(period); renderWealthCards(period);
}

// The panel used to compare one Benevente 1 against one Benevente 2, which is a
// comparison the declared ladder no longer has: there are three policies, and
// the overlay is a layer inside each of them. It now states what that layer
// costs and returns in the profile the reader is most likely to be offered.
function renderBenevente2Panel() {
  const panel = document.querySelector("#benevente2-panel");
  const profile = ladderEvidence?.profiles?.equilibrado;
  if (!panel || !profile) return;
  const withLayer = profile.benevente2, without = profile.benevente1;
  if (!withLayer || !without) return;
  panel.querySelector("[data-b2='cagr']").textContent = plainPct(withLayer.cagr);
  panel.querySelector("[data-b2='drawdown']").textContent = plainPct(withLayer.max_drawdown);
  panel.querySelector("[data-b2='volatility']").textContent = plainPct(withLayer.annual_volatility);
  panel.querySelector("[data-b2='covid']").textContent = plainPct(withLayer.cagr - without.cagr);
  panel.querySelector("[data-b1='cagr']").textContent = plainPct(without.cagr);
  panel.querySelector("[data-b1='drawdown']").textContent = plainPct(without.max_drawdown);
  panel.classList.remove("hidden");
}
let currentPeriod = "11";
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
document.querySelector("#decision-year")?.addEventListener("change", () => { renderAssetWorkbench(); renderProfileHistory(); });
document.querySelectorAll("[data-dossier-strategy]").forEach(button => button.addEventListener("click", () => {
  currentDossierStrategy = button.dataset.dossierStrategy === "b2" ? "b2" : "b1";
  syncDossierStrategyButtons();
  renderAssetWorkbench();
  renderProfileHistory();
}));

// O formulário de demonstração só existe onde há convite comercial. Enquanto
// o projeto está em pesquisa, a home não o carrega, e sem esta guarda o
// addEventListener em null derrubaria todo o script registrado adiante.
const demoForm = document.querySelector("#demo-request-form");
if (demoForm) demoForm.addEventListener("submit", async event => {
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

function renderModel(step) { const detail=document.querySelector("#model-detail"); if(!detail) return; const item=modelSteps[step]; detail.innerHTML=`<span class="detail-number">${item.number}</span><h3>${item.title}</h3><p>${item.text}</p><div class="detail-grid"><div><small>USA</small><b>${item.uses}</b></div><div><small>BLOQUEIA</small><b>${item.blocks}</b></div><div><small>PRODUZ</small><b>${item.produces}</b></div><div><small>RESPONSÁVEL</small><b>Instituição e revisor humano</b></div></div><p class="detail-rule">${item.rule}</p>`; }
document.querySelectorAll(".model-step").forEach(button=>button.addEventListener("click",()=>{document.querySelectorAll(".model-step").forEach(item=>item.classList.remove("active"));button.classList.add("active");renderModel(button.dataset.step)}));

renderModel("optimizer");
Promise.all([fetch("./annual_research_home.json"), fetch("./fund_presets.json"), fetch("./data_contract.json").catch(() => null), fetch("./ladder_v2.json").catch(() => null)]).then(async ([research, fundPresets, contractResponse, ladderResponse]) => {
  if (!research.ok || !fundPresets.ok) throw new Error("research unavailable");
  researchData = await research.json(); fundPresetsData = await fundPresets.json();
  // The chart used to plot the retired single-strategy series because there
  // was one published rule. There are three declared policies now, so the
  // curve comes from the frozen ladder. annual_research.json stays as the
  // record of the rule that was replaced, and is still what feeds the parts
  // of the page that describe that history.
  if (ladderResponse?.ok) {
    try {
      const ladder = await ladderResponse.json();
      ladderEvidence = ladder;
      if (ladder?.monthly_curve?.dates?.length) researchData.monthly_curve = ladder.monthly_curve;
    } catch (_) { /* keeps the previous curve rather than blanking the chart */ }
  }
  if (contractResponse?.ok) {
    try {
      const contract = await contractResponse.json();
      const values = {
        "annual-decisions": contract.research_window.annual_decisions,
        "historical-issuers": contract.historical_panel.evaluated_distinct_issuers,
        "price-series": contract.historical_panel.price_series,
        "fundamentals": new Intl.NumberFormat("pt-BR").format(contract.historical_panel.fundamental_records),
        "current-instruments": new Intl.NumberFormat("pt-BR").format(contract.current_b3_catalog.instruments),
      };
      document.querySelectorAll("[data-contract]").forEach(element => {
        const value = values[element.dataset.contract];
        if (value !== undefined) element.textContent = value;
      });
    } catch (_) {
      // Os números estáticos no HTML são o fallback editorial validado em teste.
    }
  }
  extraSeries[1] = {}; extraSeries[2] = {}; extraSeries[3] = {}; extraSeries[5] = {}; extraSeries[11] = {};
  refreshDecisionStudio(); renderBenevente2Panel();
}).catch(() => {
  document.querySelector("#line-chart-caption").textContent = "A tabela fixa preserva os números do artigo. O gráfico interativo exige o arquivo anual desta publicação.";
  document.querySelector("#research-status").innerHTML = "<b>Resumo estático ativo.</b><span>Os números principais permanecem visíveis; para o dossiê completo, abra a versão publicada ou reproduza o repositório.</span>";
});
