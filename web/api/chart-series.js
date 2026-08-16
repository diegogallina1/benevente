import { applyBaseHeaders, hasAllowedOrigin, isRateLimited } from "./_guard.js";

// Letters and digits only. The previous class also allowed a dot and a caret,
// which are not part of a B3 ticker and only widened what could be appended to
// an upstream path. The ".SA" suffix is added here, by us, not accepted from
// the caller.
const SYMBOL = /^[A-Z0-9]{4,8}$/;

export default async function handler(request, response) {
  applyBaseHeaders(response);
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ error: "Método não permitido." });
  }
  if (!hasAllowedOrigin(request)) {
    return response.status(403).json({ error: "Origem não autorizada." });
  }
  // This route is an unauthenticated proxy onto somebody else's rate limit.
  // Without a ceiling it is a free relay for anyone who finds the URL.
  if (isRateLimited(request, { limit: 60, windowMs: 10 * 60 * 1000, name: "chart" })) {
    response.setHeader("Retry-After", "600");
    return response.status(429).json({ error: "Muitas consultas. Aguarde alguns minutos." });
  }
  const raw = String(request.query.symbol || "").trim().toUpperCase();
  const symbol = raw.endsWith(".SA") ? raw.slice(0, -3) : raw;
  const start = new Date(String(request.query.start || ""));
  const end = new Date(String(request.query.end || ""));
  if (!SYMBOL.test(symbol) || Number.isNaN(start.valueOf()) || Number.isNaN(end.valueOf()) || end <= start) {
    return response.status(400).json({ error: "Informe ticker B3 válido e intervalo de datas válido." });
  }
  const yahooSymbol = `${symbol}.SA`;
  const endpoint = new URL(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yahooSymbol)}`);
  endpoint.searchParams.set("period1", String(Math.floor(start.valueOf() / 1000)));
  endpoint.searchParams.set("period2", String(Math.floor(end.valueOf() / 1000) + 86_400));
  endpoint.searchParams.set("interval", "1d");
  endpoint.searchParams.set("events", "history");
  const upstream = await fetch(endpoint, { headers: { "User-Agent": "Benevente research chart/1.0" } });
  if (!upstream.ok) return response.status(502).json({ error: "A fonte de preços não respondeu para este ticker." });
  const payload = await upstream.json();
  const result = payload?.chart?.result?.[0];
  if (!result?.timestamp?.length || !result?.indicators?.adjclose?.[0]?.adjclose?.length) {
    return response.status(404).json({ error: "Não há série ajustada suficiente para o ticker informado." });
  }
  const points = result.timestamp.map((timestamp, index) => ({ date: new Date(timestamp * 1000).toISOString().slice(0, 10), value: result.indicators.adjclose[0].adjclose[index] }))
    .filter(point => Number.isFinite(point.value) && point.value > 0);
  if (points.length < 2) return response.status(404).json({ error: "A fonte não retornou observações suficientes." });
  response.setHeader("Cache-Control", "s-maxage=3600, stale-while-revalidate=86400");
  return response.status(200).json({ symbol: yahooSymbol, source: "Yahoo Finance — preço ajustado", points });
}
