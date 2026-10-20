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
    const defaultPreferences = await (
      await fetch(base + "/api/preferences", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(defaultPreferences.checkins_enabled, false);
    assert.equal(defaultPreferences.quiet_start, "22:00");
    assert.equal(
      (
        await post(
          "preferences",
          { checkins_enabled: true, quiet_start: "22:00", quiet_end: "08:00", checkin_interval_hours: 24 },
          cookie,
        )
      ).status,
      200,
    );
    const checkin = await post("checkin", {}, cookie);
    assert.equal(checkin.status, 200);
    assert.equal((await checkin.json()).due, false);
    assert.equal((await post("checkin", {}, "invalid-session")).status, 401);
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
    const exportResponse = await fetch(base + "/api/memory/export", {
      headers: { Cookie: cookie },
    });
    assert.equal(exportResponse.status, 200);
    assert.match(exportResponse.headers.get("content-type"), /application\/json/);
    assert.match(
      exportResponse.headers.get("content-disposition"),
      /aura-memory-export\.json/,
    );
    const memoryExport = await exportResponse.json();
    assert.equal(memoryExport.format, "aura-memory-export");
    assert.equal(memoryExport.version, 1);
    assert.equal(memoryExport.records.conversation_logs.length, 2);
    assert.ok(
      memoryExport.records.memory_facts.some(
        (fact) => fact.fact_key === "recent_anxiety",
      ),
    );
    assert.equal(
      (await fetch(base + "/api/memory/export")).status,
      401,
      "memory export requires the local AURA session",
    );
    const anxietyFact = status.facts.find(
      (f) => f.fact_key === "recent_anxiety",
    );
    assert.ok(Number.isInteger(anxietyFact.id));
    assert.equal(
      (
        await post(
          "fact/update",
          {
            fact_id: anxietyFact.id,
            value: "I prefer calm encouragement before interviews.",
          },
          cookie,
        )
      ).status,
      200,
    );
    const corrected = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(
      corrected.facts.find((f) => f.id === anxietyFact.id).fact_value,
      "I prefer calm encouragement before interviews.",
    );
    assert.equal(
      corrected.facts.find((f) => f.id === anxietyFact.id).source,
      "user_correction",
    );
    assert.equal(
      (
        await post(
          "fact/update",
          { fact_id: anxietyFact.id, value: "  " },
          cookie,
        )
      ).status,
      400,
    );
    assert.equal(
      (await post("fact/delete", { fact_id: anxietyFact.id }, cookie)).status,
      200,
    );
    assert.equal(
      (await post("fact/delete", { fact_id: anxietyFact.id }, cookie)).status,
      404,
    );
    assert.equal(
      (await post("fact/delete", { fact_id: 0 }, cookie)).status,
      400,
    );
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
    assert.ok(Array.isArray(withContext.routines));
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
