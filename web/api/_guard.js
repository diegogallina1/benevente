// Shared request guard for the two public endpoints.
//
// Both are unauthenticated by design — the site has no accounts — so the abuse
// surface is not "someone reads another user's data" but "someone uses our
// quota". The lead endpoint spends a paid email allowance and the site's sender
// reputation; the price endpoint spends bandwidth and an upstream rate limit.
// Neither had a ceiling.
//
// The limiter is in-process and therefore per instance: serverless scales out,
// so the true ceiling is this budget times the number of warm instances. That
// is enough to stop a single client hammering an endpoint and is not enough to
// stop a distributed flood. For that, put the platform's own rate limiting or a
// WAF in front. This is a floor, not a wall, and it is documented as such.

const BUCKETS = new Map();

function clientKey(request) {
  const forwarded = String(request.headers["x-forwarded-for"] || "");
  return forwarded.split(",")[0].trim() || request.socket?.remoteAddress || "unknown";
}

/** Fixed-window counter. Returns true when the caller is over budget. */
export function isRateLimited(request, { limit, windowMs, name }) {
  const key = `${name}:${clientKey(request)}`;
  const now = Date.now();
  const bucket = BUCKETS.get(key);
  if (!bucket || now - bucket.start >= windowMs) {
    BUCKETS.set(key, { start: now, count: 1 });
    // Opportunistic sweep so an instance that stays warm for days does not
    // accumulate a key per visitor.
    if (BUCKETS.size > 5000) {
      for (const [existing, value] of BUCKETS) {
        if (now - value.start >= windowMs) BUCKETS.delete(existing);
      }
    }
    return false;
  }
  bucket.count += 1;
  return bucket.count > limit;
}

/**
 * Reject browser calls that did not originate from our own pages.
 *
 * Without this, any site can post to the lead endpoint from a visitor's
 * browser. It is not a defence against a script calling the API directly —
 * headers are trivially forged outside a browser — but it removes the
 * cross-site abuse path, which is the one that scales.
 */
export function hasAllowedOrigin(request) {
  const origin = request.headers.origin;
  if (!origin) return true; // same-origin GETs and server-side calls send none
  const allowed = new Set(
    (process.env.BENEVENTE_ALLOWED_ORIGINS || "https://benevente-wealth-system.vercel.app")
      .split(",").map(item => item.trim()).filter(Boolean),
  );
  if (process.env.VERCEL_URL) allowed.add(`https://${process.env.VERCEL_URL}`);
  if (process.env.NODE_ENV !== "production") {
    allowed.add("http://localhost:3000");
    allowed.add("http://127.0.0.1:8899");
  }
  return allowed.has(origin);
}

/** Headers every API response should carry, regardless of status. */
export function applyBaseHeaders(response) {
  response.setHeader("X-Content-Type-Options", "nosniff");
  response.setHeader("Referrer-Policy", "no-referrer");
  // These endpoints return data derived from a request; a shared cache keyed
  // only on the URL is fine for prices and wrong for anything else.
  response.setHeader("Vary", "Origin");
}
