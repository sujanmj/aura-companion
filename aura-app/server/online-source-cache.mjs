import { randomBytes } from "node:crypto";

const LOOKUP_ID = /^[A-Za-z0-9_-]{32}$/;

export class TemporaryOnlineSourceCache {
  constructor({ now = Date.now, ttlMs = 10 * 60 * 1000, maxEntries = 12, createId } = {}) {
    if (typeof now !== "function" || !Number.isFinite(ttlMs) || ttlMs <= 0 ||
        !Number.isSafeInteger(maxEntries) || maxEntries < 1) {
      throw new TypeError("Invalid temporary source cache settings");
    }
    this.now = now;
    this.ttlMs = ttlMs;
    this.maxEntries = maxEntries;
    this.createId = createId || (() => randomBytes(24).toString("base64url"));
    this.entries = new Map();
  }

  put(sources) {
    if (!Array.isArray(sources) || sources.length < 1 || sources.length > 3) {
      throw new TypeError("Expected one to three reviewed sources");
    }
    this.prune();
    let id;
    for (let attempt = 0; attempt < 3; attempt++) {
      id = this.createId();
      if (typeof id === "string" && LOOKUP_ID.test(id) && !this.entries.has(id)) break;
      id = undefined;
    }
    if (!id) throw new Error("Could not create a unique source handle");
    this.entries.set(id, { sources: structuredClone(sources), expiresAt: this.now() + this.ttlMs });
    this.prune();
    return id;
  }

  get(id) {
    if (typeof id !== "string" || !LOOKUP_ID.test(id)) return null;
    const entry = this.entries.get(id);
    if (!entry) return null;
    if (entry.expiresAt <= this.now()) {
      this.entries.delete(id);
      return null;
    }
    return structuredClone(entry.sources);
  }

  clear(id) {
    if (typeof id !== "string" || !LOOKUP_ID.test(id)) return false;
    return this.entries.delete(id);
  }

  prune() {
    const now = this.now();
    for (const [id, entry] of this.entries) {
      if (entry.expiresAt <= now) this.entries.delete(id);
    }
    while (this.entries.size > this.maxEntries) {
      this.entries.delete(this.entries.keys().next().value);
    }
  }
}
