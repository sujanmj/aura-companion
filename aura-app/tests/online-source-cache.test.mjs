import test from "node:test";
import assert from "node:assert/strict";
import { TemporaryOnlineSourceCache } from "../server/online-source-cache.mjs";

const source = id => ({ id, title: `Source ${id}`, excerpt: "Reviewed text." });
const testId = index => index.toString(16).padStart(32, "0");

test("source handles expire at the exact TTL boundary and are then unusable", () => {
  let now = 1000;
  const cache = new TemporaryOnlineSourceCache({ now: () => now, ttlMs: 500,
    createId: () => testId(1) });
  const id = cache.put([source(1)]);
  now = 1499;
  assert.deepEqual(cache.get(id), [source(1)]);
  now = 1500;
  assert.equal(cache.get(id), null);
  assert.equal(cache.get(id), null);
});

test("cache capacity evicts the oldest source handles", () => {
  let next = 1;
  const cache = new TemporaryOnlineSourceCache({ maxEntries: 2,
    createId: () => testId(next++) });
  const first = cache.put([source(1)]);
  const second = cache.put([source(2)]);
  const third = cache.put([source(3)]);
  assert.equal(cache.get(first), null);
  assert.deepEqual(cache.get(second), [source(2)]);
  assert.deepEqual(cache.get(third), [source(3)]);
  assert.equal(cache.entries.size, 2);
});

test("clear removes source data and handles are independent copies", () => {
  const cache = new TemporaryOnlineSourceCache({ createId: () => testId(4) });
  const input = [source(4)];
  const id = cache.put(input);
  input[0].excerpt = "mutated after insertion";
  const output = cache.get(id);
  assert.equal(output[0].excerpt, "Reviewed text.");
  output[0].excerpt = "mutated after read";
  assert.equal(cache.get(id)[0].excerpt, "Reviewed text.");
  assert.equal(cache.clear(id), true);
  assert.equal(cache.get(id), null);
  assert.equal(cache.clear(id), false);
});

test("only one to three reviewed sources and valid temporary cache settings are accepted", () => {
  for (const settings of [{ ttlMs: 0 }, { ttlMs: Infinity }, { maxEntries: 0 }, { maxEntries: 1.5 }]) {
    assert.throws(() => new TemporaryOnlineSourceCache(settings), /Invalid temporary source cache settings/);
  }
  const cache = new TemporaryOnlineSourceCache({ createId: () => testId(5) });
  for (const sources of [[], [source(1), source(2), source(3), source(4)]]) {
    assert.throws(() => cache.put(sources), /one to three reviewed sources/);
  }
  assert.equal(cache.get("invalid"), null);
  assert.equal(cache.clear("invalid"), false);
});
