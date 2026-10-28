import { spawn } from "node:child_process";
import { createInterface } from "node:readline";

// A dead or stalled worker must not leave HTTP requests waiting indefinitely.
export class MemoryClient {
  constructor({ command, args, env = process.env, timeout = 45000 }) {
    this.pending = new Map();
    this.sequence = 0;
    this.timeout = timeout;
    this.closed = false;
    this.worker = spawn(command, args, { env, stdio: ["pipe", "pipe", "pipe"] });
    this.worker.stderr.on("data", () => {}); // Never relay provider secrets.
    this.worker.on("error", () => this.close());
    this.worker.on("exit", () => this.close());
    this.worker.stdin.on("error", () => this.close());
    createInterface({ input: this.worker.stdout }).on("line", (line) => {
      let data;
      try {
        data = JSON.parse(line);
      } catch {
        return;
      }
      const pending = this.pending.get(data?.id);
      if (!pending) return;
      this.pending.delete(data.id);
      clearTimeout(pending.timer);
      if (data.error) pending.reject(new Error("Memory request failed"));
      else pending.resolve(data.result);
    });
  }
  request(op, data = {}) {
    if (this.closed)
      return Promise.reject(new Error("Memory service unavailable"));
    return new Promise((resolve, reject) => {
      const id = ++this.sequence;
      const timer = setTimeout(() => this.close(), this.timeout);
      this.pending.set(id, { resolve, reject, timer });
      this.worker.stdin.write(
        JSON.stringify({ ...data, id, op }) + "\n",
        (error) => {
          if (error) this.close();
        },
      );
    });
  }
  close() {
    if (this.closed) return;
    this.closed = true;
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(new Error("Memory service unavailable"));
    }
    this.pending.clear();
    // Do not retry writes: a failed request may already have committed to SQLite.
    this.worker.kill();
  }
}
