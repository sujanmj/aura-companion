import { randomUUID } from "node:crypto";
export class ApprovalGate {
  constructor({ enabled = false, allowed = [], timeout = 60000 } = {}) {
    this.enabled = enabled;
    this.allowed = new Set(allowed);
    this.timeout = timeout;
    this.pending = new Map();
  }
  async request(name, input) {
    if (!this.enabled || !this.allowed.has(name) || !name.startsWith("mcp__"))
      return false;
    const id = randomUUID();
    return new Promise((resolve) => {
      const timer = setTimeout(() => this.resolve(id, false), this.timeout);
      this.pending.set(id, {
        id,
        name,
        input,
        expires: Date.now() + this.timeout,
        finish: (ok) => {
          clearTimeout(timer);
          resolve(ok);
        },
      });
    });
  }
  list() {
    return [...this.pending.values()].map(({ id, name, input, expires }) => ({
      id,
      name,
      input,
      expires,
    }));
  }
  resolve(id, approved) {
    const item = this.pending.get(id);
    if (!item) return false;
    this.pending.delete(id);
    item.finish(approved === true);
    return true;
  }
  close() {
    for (const id of this.pending.keys()) this.resolve(id, false);
  }
}
export function permittedOrigin(origin, port, dev = false) {
  return [
    `http://127.0.0.1:${port}`,
    ...(dev ? ["http://127.0.0.1:5173"] : []),
  ].includes(origin);
}
