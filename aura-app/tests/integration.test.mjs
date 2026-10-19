import test from "node:test";
import http from "node:http";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, rm, readdir } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { once } from "node:events";
const token = "test-only-session-code-123456789";
const port = 18790,
  base = `http://127.0.0.1:${port}`;
let proc;
async function start(db) {
  proc = spawn(process.execPath, ["server/server.mjs"], {
    env: {
      ...process.env,
      AURA_DB_PATH: db,
      AURA_PORT: String(port),
      AURA_SESSION_TOKEN: token,
      AURA_BRAIN_PROVIDER: "local",
      AURA_ENABLE_ACTIONS: "0",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let output = "";
  proc.stderr.on("data", (b) => (output += b));
  for (let i = 0; i < 100; i++) {
    try {
      await fetch(base);
      return;
    } catch {
      await new Promise((r) => setTimeout(r, 50));
    }
    if (proc.exitCode !== null) throw new Error(output);
  }
  throw new Error("Server did not start");
}
async function stop() {
  if (proc && proc.exitCode === null) {
    proc.kill("SIGTERM");
    await once(proc, "exit");
  }
}
async function post(route, data, cookie = "", origin = base) {
  return fetch(base + "/api/" + route, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Origin: origin,
      Cookie: cookie,
    },
    body: JSON.stringify(data),
  });
}
async function login() {
  const res = await post("login", { token });
  assert.equal(res.status, 200);
  const cookie = res.headers.get("set-cookie");
  assert.match(cookie, /HttpOnly/);
  assert.match(cookie, /SameSite=Strict/);
  return cookie.split(";")[0];
}
test("loopback app: authentication, CSRF, conversation, feedback, persistence, backups, default-denied tools", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "aura-test-"));
  const db = path.join(dir, "memory.db");
  try {
    await start(db);
    assert.equal((await fetch(base + "/api/status")).status, 401);
    assert.equal((await fetch(base + "/api/readiness")).status, 401);
    assert.equal(
      (await post("login", { token }, "", "https://evil.test")).status,
      403,
    );
    assert.equal((await post("login", { token: "wrong" })).status, 401);
    assert.equal(
      await new Promise((resolve, reject) => {
        http
          .get(base, { headers: { Host: "evil.test" } }, (res) => {
            res.resume();
            resolve(res.statusCode);
          })
          .on("error", reject);
      }),
      403,
    );
    let cookie = await login();
    const readiness = await (
      await fetch(base + "/api/readiness", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(readiness.brain.state, "local_only");
    assert.equal(readiness.memory, "available");
    assert.equal(readiness.actions.state, "disabled");
    assert.equal(readiness.hardware, "not_tested");
    assert.equal("conversations" in readiness, false);
    assert.equal("facts" in readiness, false);
    assert.equal(
      (await post("chat", { message: "hello" }, cookie, "https://evil.test"))
        .status,
      403,
    );
    assert.equal((await post("chat", { message: "" }, cookie)).status, 400);
    assert.equal(
      (await post("chat", { message: "x".repeat(8001) }, cookie)).status,
      400,
    );
    const reply = await post(
      "chat",
      { message: "I am nervous about my presentation" },
      cookie,
    );
    assert.equal(reply.status, 200);
    const data = await reply.json();
    assert.equal(typeof data.response, "string");
    assert.equal(data.provider, "local");
    assert.equal(
      (await post("feedback", { response_id: data.id, rating: "good" }, cookie))
        .status,
      200,
    );
    assert.equal(
      (await post("feedback", { response_id: 999999, rating: "good" }, cookie))
        .status,
      400,
    );
    assert.equal(
      (await post("task", { message: "delete all files" }, cookie)).status,
      403,
    );
    const status = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(status.conversations.length, 2);
    assert.ok(status.facts.some((f) => f.fact_key === "recent_anxiety"));
    assert.equal(status.actions, false);
    const ambient = await post(
      "ambient",
      {
        message: "Hey AURA, can you help me?",
        observation: "Local camera context: laptop, person present",
      },
      cookie,
    );
    assert.equal(ambient.status, 200);
    assert.equal(typeof (await ambient.json()).response, "string");
    const withContext = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.ok(
      withContext.observations.some(
        (o) => o.event_type === "ambient_context" && o.source === "mac_local",
      ),
    );
    const page = await fetch(base);
    assert.equal(page.status, 200);
    assert.match(await page.text(), /AURA Companion/);
    assert.match(
      page.headers.get("content-security-policy"),
      /frame-ancestors 'none'/,
    );
    assert.equal((await fetch(base + "/server/server.mjs")).status, 404);
    await stop();
    await start(db);
    cookie = await login();
    const restored = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(restored.conversations.length, 4);
    assert.ok(
      (await readdir(path.join(dir, "backups"))).some((f) => f.endsWith(".db")),
    );
  } finally {
    await stop();
    await rm(dir, { recursive: true, force: true });
  }
});
