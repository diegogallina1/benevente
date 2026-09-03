(async function () {
  const host = document.querySelector("[data-event-radar]");
  if (!host) return;
  const escape = value => String(value ?? "").replace(/[&<>\"']/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" }[character]));
  const date = value => new Date(value).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo", dateStyle: "short", timeStyle: "short" });
  // Os itens do radar vêm de manchete de terceiro e de documento da CVM: o
  // texto é escapado, mas escapar não desarma um esquema de URL. Um link
  // "javascript:..." sobrevive ao escape e vira execução ao clique. A CSP
  // bloqueia isso hoje; esta é a segunda tranca, e ela não depende de header.
  const link = value => {
    try {
      const url = new URL(String(value ?? ""), location.origin);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : "";
    } catch (_) { return ""; }
  };
  // Valores que entram em atributo (state, status) são gerados pelo coletor e
  // não pelo terceiro, mas atributo sem escape é uma classe de bug, não um
  // caso: se algum dia um desses campos passar a vir de fora, o escape já está
  // aqui em vez de precisar ser lembrado.
  const attr = value => escape(String(value ?? "").replace(/[^a-z0-9_-]/gi, ""));
  const stateLabel = { normal: "Normal", atencao: "Atenção", alerta: "Alerta", critico: "Crítico", sem_coleta: "Sem coleta" };
  try {
    const response = await fetch("./event_radar.json", { cache: "no-store" });
    if (!response.ok) throw new Error("indisponível");
    const data = await response.json();
    const run = data.consolidations[0];
    const sourcesOk = run.source_status.filter(item => item.status === "ok").length;
    const sourcesFailed = run.source_status.length - sourcesOk;
    const items = (data.latest_items || []).slice(0, 8);
    const latestUsesGemini = items.some(item => item.classification?.classifier?.startsWith("gemini:"));
    const cards = items.length ? items.map(item => {
      const analysis = item.classification;
      const tickers = analysis.impacted_tickers?.length ? analysis.impacted_tickers.join(" · ") : "mercado geral";
      const href = link(item.url);
      const fonte = href
        ? `<a href="${escape(href)}" target="_blank" rel="noopener noreferrer">Abrir fonte</a>`
        : `<span class="radar-event-sem-link">Sem link utilizável na fonte</span>`;
      return `<article class="radar-event ${attr(item.state)}"><div class="radar-event-top"><span>${stateLabel[item.state] || attr(item.state)} · ${Number(analysis.materiality) || 0}/100</span><time>${date(item.published_at)}</time></div><h4>${escape(item.title)}</h4><p>${escape(analysis.summary)}</p><div class="radar-event-meta"><span>${escape(item.source)}</span><span>${escape(tickers)}</span><span>confiança ${(Number(analysis.confidence) * 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })}%</span></div>${fonte}</article>`;
    }).join("") : `<p class="radar-empty">Nenhum item novo na consolidação mais recente.</p>`;
    const sourceRows = run.source_status.map(item => `<li><span>${escape(item.source)}</span><b class="${attr(item.status)}">${item.status === "ok" ? `${Number(item.items) || 0} item(ns)` : "indisponível"}</b></li>`).join("");
    host.innerHTML = `<div class="radar-summary"><div><span>ESTADO DA CONSOLIDAÇÃO</span><strong class="radar-state ${attr(run.state)}">${stateLabel[run.state] || attr(run.state)}</strong><small>${Number(run.new_items) || 0} novo(s) nesta execução · ${items.length} recente(s) exibido(s)</small></div><div><span>ÚLTIMA EXECUÇÃO</span><strong>${date(run.run_at)}</strong><small>próximas: 00h10 e 12h10</small></div><div><span>CLASSIFICAÇÃO</span><strong>${latestUsesGemini ? "Gemini + validação" : "Regras de contingência"}</strong><small>${sourcesOk} fontes disponíveis · ${sourcesFailed} indisponível(is)</small></div></div><div class="radar-grid"><div class="radar-events">${cards}</div><aside class="radar-sources"><h4>Fontes consultadas</h4><ul>${sourceRows}</ul><p>O radar prioriza revisão humana. Não altera pesos nem transmite ordens.</p><code>${escape(String(data.record_sha256 ?? "").slice(0, 16))}…</code></aside></div>`;
  } catch (_) {
    host.innerHTML = `<p class="live-error">O radar de eventos não pôde ser carregado agora.</p>`;
  }
}());
