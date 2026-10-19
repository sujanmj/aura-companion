import test from "node:test";
import assert from "node:assert/strict";
import { ApprovalGate, permittedOrigin } from "../server/policy.mjs";
test("unknown tools and all builtins stay blocked even with actions enabled", async () => {
  const off = new ApprovalGate({ allowed: ["mcp__demo__read"] });
  assert.equal(await off.request("mcp__demo__read", {}), false);
  const gate = new ApprovalGate({
    enabled: true,
    allowed: ["mcp__demo__read", "Bash"],
  });
  assert.equal(await gate.request("mcp__other__read", {}), false);
  assert.equal(await gate.request("Bash", { command: "echo x" }), false);
});
test("approval is bound to one exact invocation, expires, and cannot be replayed", async () => {
  const gate = new ApprovalGate({
    enabled: true,
    allowed: ["mcp__demo__write"],
    timeout: 25,
  });
  const first = gate.request("mcp__demo__write", { path: "one" });
  const id = gate.list()[0].id;
  assert.deepEqual(gate.list()[0].input, { path: "one" });
  assert.equal(gate.resolve(id, true), true);
  assert.equal(await first, true);
  assert.equal(gate.resolve(id, true), false);
  assert.equal(await gate.request("mcp__demo__write", { path: "two" }), false);
  const third = gate.request("mcp__demo__write", {});
  gate.close();
  assert.equal(await third, false);
});
test("origins are exact, never wildcard or arbitrary loopback ports", () => {
  assert.equal(permittedOrigin("http://127.0.0.1:8790", 8790), true);
  for (const origin of [
    undefined,
    "null",
    "https://evil.test",
    "http://127.0.0.1:8790.evil.test",
    "http://localhost:8790",
    "http://127.0.0.1:5173",
  ])
    assert.equal(permittedOrigin(origin, 8790), false);
  assert.equal(permittedOrigin("http://127.0.0.1:5173", 8790, true), true);
});
