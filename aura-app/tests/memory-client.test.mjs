import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { MemoryClient } from "../server/memory-client.mjs";

test("worker exit rejects pending and future requests", async () => {
  const client = new MemoryClient({
    command: process.execPath,
    args: ["-e", "process.exit(1)"],
  });
  const exited = once(client.worker, "exit");
  await assert.rejects(client.request("status"), /unavailable/);
  await exited;
  await assert.rejects(
    client.request("chat", { message: "hello" }),
    /unavailable/,
  );
});
test("missing Python executable is handled without an unhandled stream error", async () => {
  const client = new MemoryClient({
    command: "/nonexistent/aura-python",
    args: [],
  });
  await assert.rejects(client.request("status"), /unavailable/);
  await assert.rejects(client.request("status"), /unavailable/);
});
test("stalled worker fails within a bound and is not retried", async () => {
  const client = new MemoryClient({
    command: process.execPath,
    args: ["-e", "setInterval(() => {}, 1000)"],
    timeout: 50,
  });
  const exited = once(client.worker, "exit");
  await assert.rejects(
    client.request("chat", { message: "hello" }),
    /unavailable/,
  );
  await assert.rejects(client.request("status"), /unavailable/);
  await exited;
  assert.equal(client.pending.size, 0);
});
