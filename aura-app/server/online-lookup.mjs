// One explicitly reviewed lookup. No memory, model, MCP, or arbitrary URL access.
const ORIGIN = "https://en.wikipedia.org";
const MAX_BYTES = 128 * 1024;
const USER_AGENT = "AURACompanion/0.3.0 (https://github.com/sujanmj/aura-companion)";

function cleanText(value, limit) {
  if (typeof value !== "string") return "";
  // Source display text deliberately strips terminal/control characters.
  // eslint-disable-next-line no-control-regex
  return value.replace(/[\u0000-\u0008\u000b-\u001f\u007f]/g, "").trim().slice(0, limit);
}

async function boundedJSON(url, fetcher, signal) {
  const response = await fetcher(url, {
    method: "GET",
    redirect: "error",
    credentials: "omit",
    headers: { Accept: "application/json", "User-Agent": USER_AGENT },
    signal,
  });
  if (!response.ok || !response.headers.get("content-type")?.includes("application/json") || !response.body) {
    await response.body?.cancel().catch(() => {});
    throw new Error("Source unavailable");
  }
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BYTES) throw new Error("Source response too large");
      chunks.push(Buffer.from(value));
    }
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export async function lookupWikipedia(query, approved, { fetcher = fetch, signal, timeoutMs = 8000 } = {}) {
  if (approved !== true || typeof query !== "string" || !query.trim() || query.length > 300)
    throw Object.assign(new Error("Review and approve a query of 1–300 characters."), { status: 400 });
  const timeout = AbortSignal.timeout(timeoutMs);
  const boundedSignal = signal ? AbortSignal.any([signal, timeout]) : timeout;
  boundedSignal.throwIfAborted();
  const search = new URL("/w/api.php", ORIGIN);
  search.search = new URLSearchParams({ action: "query", list: "search", srsearch: query.trim(),
    srnamespace: "0", srlimit: "3", srprop: "timestamp", format: "json", formatversion: "2" }).toString();
  const data = await boundedJSON(search, fetcher, boundedSignal);
  if (data.error || !Array.isArray(data.query?.search)) throw new Error("Invalid source response");
  const sources = [];
  let unavailable = 0;
  const seen = new Set();
  for (const item of data.query.search.slice(0, 3)) {
    if (!Number.isSafeInteger(item.pageid) || item.pageid <= 0 || seen.has(item.pageid) ||
        typeof item.title !== "string" || !item.title.trim() || item.title.length > 300) {
      unavailable++;
      continue;
    }
    seen.add(item.pageid);
    // Encode the title as one path component. Never follow a URL from source content.
    const url = new URL("/api/rest_v1/page/summary/" + encodeURIComponent(item.title), ORIGIN);
    try {
      if (!url.pathname.startsWith("/api/rest_v1/page/summary/") || [".", ".."].includes(item.title))
        throw new Error("Invalid source title");
      const page = await boundedJSON(url, fetcher, boundedSignal);
      if (page.pageid !== item.pageid || !["standard", "disambiguation"].includes(page.type))
        throw new Error("Mismatched source");
      const excerpt = cleanText(page.extract, 1600);
      if (!excerpt) throw new Error("Empty source");
      sources.push({
        id: item.pageid,
        title: cleanText(item.title, 300),
        url: `${ORIGIN}/?curid=${item.pageid}`,
        excerpt,
        truncated: page.extract.length > 1600,
        ambiguous: page.type === "disambiguation",
      });
    } catch {
      boundedSignal.throwIfAborted();
      unavailable++;
    }
  }
  boundedSignal.throwIfAborted();
  return { query: query.trim(), provider: "Wikipedia", retrieved_at: new Date().toISOString(),
    sources, unavailable, saved: false, independently_verified: false };
}
