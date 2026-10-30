import test from "node:test";
import assert from "node:assert/strict";
import { lookupWikipedia } from "../server/online-lookup.mjs";
const json = value => new Response(JSON.stringify(value), { headers: { "content-type": "application/json" } });
const search = [{ pageid: 42, title: "Example" }];
const summary = { pageid: 42, type: "standard", extract: "A source excerpt.", content_urls: { desktop: { page: "https://evil.test" } } };

test("online lookup requires literal approval and bounded reviewed text before network access", async () => {
  for (const [query, approval] of [["hello", false], ["hello", "true"], ["", true], ["x".repeat(301), true], [null, true]]) {
    await assert.rejects(lookupWikipedia(query, approval, { fetcher: () => assert.fail("network called") }), /Review and approve/);
  }
});
test("lookup sends only the encoded query and returns source-controlled text with fixed citation URLs", async () => {
  const calls = [];
  const result = await lookupWikipedia("science & nature", true, { fetcher: async (url, options) => {
    calls.push([url, options]);
    return calls.length === 1 ? json({ query: { search } }) : json(summary);
  } });
  assert.equal(calls.length, 2);
  assert.equal(calls[0][0].searchParams.get("srsearch"), "science & nature");
  for (const [url, options] of calls) {
    assert.equal(url.origin, "https://en.wikipedia.org");
    assert.equal(options.redirect, "error");
    assert.equal(options.credentials, "omit");
    assert.equal(options.headers.Authorization, undefined);
    assert.equal(options.body, undefined);
    assert.match(options.headers["User-Agent"], /AURACompanion/);
  }
  assert.equal(result.sources[0].url, "https://en.wikipedia.org/?curid=42");
  assert.equal(result.sources[0].excerpt, summary.extract);
  assert.equal(result.saved, false);
  assert.equal(result.independently_verified, false);
  assert.ok(Number.isFinite(Date.parse(result.retrieved_at)));
});
test("source failures, invalid identifiers and dot segments cannot become trusted citations", async () => {
  let count = 0;
  const result = await lookupWikipedia("example", true, { fetcher: async () => {
    count++;
    if (count === 1) return json({ query: { search: [{ pageid: 41, title: ".." }, { pageid: -2, title: "bad" }, search[0]] } });
    return json({ ...summary, pageid: 999 });
  } });
  assert.equal(count, 2);
  assert.equal(result.sources.length, 0);
  assert.equal(result.unavailable, 3);
});
test("only three distinct source summaries can be requested and large excerpts are marked", async () => {
  let count = 0;
  const result = await lookupWikipedia("example", true, { fetcher: async () => {
    count++;
    return count === 1 ? json({ query: { search: [...search, ...search, ...search, { pageid: 99, title: "unused" }] } })
      : json({ ...summary, type: "disambiguation", extract: "x".repeat(3000) });
  } });
  assert.equal(count, 2);
  assert.equal(result.sources.length, 1);
  assert.equal(result.sources[0].excerpt.length, 1600);
  assert.equal(result.sources[0].truncated, true);
  assert.equal(result.sources[0].ambiguous, true);
});
test("oversized, non-JSON and malformed upstream responses fail closed", async () => {
  for (const response of [new Response("x".repeat(131073), { headers: { "content-type": "application/json" } }),
    new Response("<html>private error</html>"), json({ error: { message: "private provider error" } })]) {
    await assert.rejects(lookupWikipedia("test", true, { fetcher: async () => response }));
  }
});
test("pre-cancelled requests do not reach the network", async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(lookupWikipedia("test", true, { signal: controller.signal, fetcher: () => assert.fail("network called") }));
});
test("network timeout aborts the request rather than fabricating an answer", async () => {
  // Keep the test event loop live; AbortSignal.timeout itself is unref'ed by Node.
  const keepAlive = setTimeout(() => {}, 1000);
  try {
    await assert.rejects(lookupWikipedia("test", true, { timeoutMs: 10, fetcher: async (_url, { signal }) =>
      new Promise((_resolve, reject) => signal.addEventListener("abort", () => reject(signal.reason), { once: true })) }));
  } finally { clearTimeout(keepAlive); }
});
