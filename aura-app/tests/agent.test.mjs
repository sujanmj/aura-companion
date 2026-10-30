import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { ApprovalGate } from "../server/policy.mjs";
import { runAgent } from "../server/agent.mjs";

const invocation = {
  tool_name: "mcp__demo__write",
  tool_input: { path: "notes/today.txt", text: "approved once" },
};

function deferred() {
  let resolve;
  const promise = new Promise((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

async function temporaryWorkingDirectory() {
  return mkdtemp(path.join(os.tmpdir(), "aura-agent-bridge-"));
}

test("Claude SDK bridge allows only the exact MCP invocation approved by the user", async () => {
  const gate = new ApprovalGate({
    enabled: true,
    allowed: ["mcp__demo__write"],
  });
  const controller = new AbortController();
  const pendingApproval = deferred();
  const decisions = [];
  const cwd = await temporaryWorkingDirectory();
  const queryRunner = async function* ({ options }) {
    assert.deepEqual(options.mcpServers, { demo: { command: "demo-mcp" } });
    assert.deepEqual(options.tools, []);
    assert.deepEqual(options.allowedTools, []);
    assert.equal(options.permissionMode, "default");
    assert.equal(options.persistSession, false);
    const hook = options.hooks.PreToolUse[0].hooks[0];
    const decisionPromise = hook(invocation);
    pendingApproval.resolve(gate.list()[0]);
    const decision = await decisionPromise;
    decisions.push(decision.hookSpecificOutput);
    yield { type: "result", is_error: false, result: "The approved note was saved." };
  };

  try {
    const task = runAgent(
      "Save this note",
      { servers: { demo: { command: "demo-mcp" } } },
      gate,
      cwd,
      controller.signal,
      queryRunner,
    );
    const pending = await pendingApproval.promise;
    assert.equal(pending.name, invocation.tool_name);
    assert.deepEqual(pending.input, invocation.tool_input);
    assert.equal(gate.resolve(pending.id, true), true);
    assert.equal(await task, "The approved note was saved.");
    assert.deepEqual(decisions, [
      {
        hookEventName: "PreToolUse",
        permissionDecision: "allow",
        permissionDecisionReason: "User approved this exact invocation.",
      },
    ]);
    assert.deepEqual(gate.list(), []);
  } finally {
    gate.close();
    await rm(cwd, { recursive: true, force: true });
  }
});

test("cancelling the Claude task denies a pending MCP call and discards its response", async () => {
  const gate = new ApprovalGate({
    enabled: true,
    allowed: ["mcp__demo__write"],
  });
  const controller = new AbortController();
  const pendingApproval = deferred();
  const decisions = [];
  const cwd = await temporaryWorkingDirectory();
  const queryRunner = async function* ({ options }) {
    const hook = options.hooks.PreToolUse[0].hooks[0];
    const decisionPromise = hook(invocation);
    pendingApproval.resolve(gate.list()[0]);
    const decision = await decisionPromise;
    decisions.push(decision.hookSpecificOutput);
    yield { type: "result", is_error: false, result: "A stale response" };
  };

  try {
    const task = runAgent(
      "Save this note",
      { servers: { demo: { command: "demo-mcp" } } },
      gate,
      cwd,
      controller.signal,
      queryRunner,
    );
    const pending = await pendingApproval.promise;
    controller.abort();
    await assert.rejects(task, { name: "AbortError" });
    assert.equal(gate.resolve(pending.id, true), false);
    assert.deepEqual(decisions, [
      {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: "AURA blocks unapproved actions.",
      },
    ]);
    assert.deepEqual(gate.list(), []);
  } finally {
    gate.close();
    await rm(cwd, { recursive: true, force: true });
  }
});
