import test from "node:test";
import http from "node:http";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { execFileSync } from "node:child_process";
import { mkdtemp, rm, readdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { once } from "node:events";
const token = "test-only-session-code-123456789";
const port = 18790,
  base = `http://127.0.0.1:${port}`;
let proc;
async function start(db, extraEnv = {}) {
  proc = spawn(process.execPath, ["server/server.mjs"], {
    env: {
      ...process.env,
      AURA_DB_PATH: db,
      AURA_PORT: String(port),
      AURA_SESSION_TOKEN: token,
      AURA_BRAIN_PROVIDER: "local",
      AURA_ENABLE_ACTIONS: "0",
      ...extraEnv,
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
    assert.equal((await post("person/delete", { person_id: 1 })).status, 401);
    assert.equal(
      (await post("reminder/create", { label: "Take medication", local_time: "20:00", enabled: true })).status,
      401,
    );
    assert.equal(
      (await post("reminder/enabled", { reminder_id: 1, enabled: false })).status,
      401,
    );
    assert.equal((await post("observations/clear", {})).status, 401);
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
    assert.equal((await post("shared", { message: "hello", consent: true })).status, 401);
    assert.equal((await post("shared", { message: "hello", consent: true }, cookie, "https://evil.test")).status, 403);
    assert.equal((await post("shared", { message: "hello" }, cookie)).status, 400);
    const beforeShared = await (await fetch(base + "/api/memory/export", { headers: { Cookie: cookie } })).json();
    const shared = await post("shared", { message: "Our private shared question", consent: true }, cookie);
    assert.equal(shared.status, 200);
    assert.equal((await shared.json()).saved, false);
    const afterShared = await (await fetch(base + "/api/memory/export", { headers: { Cookie: cookie } })).json();
    assert.deepEqual(afterShared.records, beforeShared.records, "Shared contributions must not read into or mutate personal memory");
    assert.equal((await post("observations/retention", { days: 30, confirmed: true })).status, 401);
    assert.equal((await post("observations/retention", { days: 30, confirmed: true }, cookie, "https://evil.test")).status, 403);
    assert.equal((await post("observations/retention", { days: 30 }, cookie)).status, 400);
    assert.equal((await post("observations/retention", { days: true, confirmed: true }, cookie)).status, 400);
    const retentionPreview = await post("observations/retention-preview", { days: 30 }, cookie);
    assert.equal(retentionPreview.status, 200);
    assert.equal((await retentionPreview.json()).days, 30);
    assert.equal((await post("observations/retention", { days: 30, confirmed: true }, cookie)).status, 200);
    assert.equal((await post("observations/retention", { days: 0, confirmed: true }, cookie)).status, 200);
    assert.equal(
      (await post("ambient/observation", { labels: ["room"], human_present: true, confidence: 0.8 })).status,
      401,
    );
    assert.equal(
      (
        await post(
          "ambient/observation",
          { labels: ["room"], human_present: true, confidence: 0.8 },
          cookie,
          "https://evil.test",
        )
      ).status,
      403,
    );
    assert.equal(
      (
        await post(
          "ambient/observation",
          { labels: ["<script>"], human_present: true, confidence: 0.8 },
          cookie,
        )
      ).status,
      400,
    );
    const sceneObservation = await post(
      "ambient/observation",
      {
        labels: ["living room", "sofa"],
        human_present: true,
        confidence: 0.91,
      },
      cookie,
    );
    assert.equal(sceneObservation.status, 200);
    assert.equal((await sceneObservation.json()).saved, true);
    const unchangedScene = await post(
      "ambient/observation",
      {
        labels: ["living room", "sofa"],
        human_present: true,
        confidence: 0.93,
      },
      cookie,
    );
    assert.deepEqual(await unchangedScene.json(), {
      saved: false,
      reason: "unchanged",
    });
    const rapidSceneChange = await post(
      "ambient/observation",
      { labels: ["kitchen"], human_present: false, confidence: 0.8 },
      cookie,
    );
    assert.deepEqual(await rapidSceneChange.json(), {
      saved: false,
      reason: "rate_limited",
    });
    const observationBeforeCorrection = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    const visualMemory = observationBeforeCorrection.observations.find(
      (item) => item.source === "mac_local_vision",
    );
    assert.ok(visualMemory);
    assert.equal(
      (
        await post(
          "observation/correct",
          { observation_id: visualMemory.id, value: "My keys are on the blue sofa." },
          cookie,
        )
      ).status,
      200,
    );
    const correctedMemory = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    const correctedObservation = correctedMemory.observations.find(
      (item) => item.id === visualMemory.id,
    );
    assert.equal(correctedObservation.source, "user_correction");
    assert.match(correctedObservation.event_summary, /blue sofa/);
    assert.equal(
      (
        await post(
          "observation/correct",
          { observation_id: visualMemory.id, value: "x".repeat(501) },
          cookie,
        )
      ).status,
      400,
    );
    const readiness = await (
      await fetch(base + "/api/readiness", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(readiness.brain.state, "local_only");
    assert.equal(readiness.memory, "available");
    assert.equal(readiness.actions.state, "disabled");
    assert.equal(readiness.hardware, "not_tested");
    assert.equal("conversations" in readiness, false);
    assert.equal("facts" in readiness, false);
    assert.equal((await post("readiness/provider-test", {})).status, 401);
    assert.equal(
      (await post("readiness/provider-test", {}, cookie, "https://evil.test"))
        .status,
      403,
    );
    const providerTest = await post("readiness/provider-test", {}, cookie);
    assert.equal(providerTest.status, 200);
    assert.deepEqual(await providerTest.json(), {
      provider: "local",
      state: "local_only",
      verified: false,
    });
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
          {
            checkins_enabled: true,
            quiet_start: "22:00",
            quiet_end: "08:00",
            checkin_interval_hours: 24,
          },
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
    assert.deepEqual(status.people, []);
    assert.ok(status.facts.some((f) => f.fact_key === "recent_anxiety"));
    const exportResponse = await fetch(base + "/api/memory/export", {
      headers: { Cookie: cookie },
    });
    assert.equal(exportResponse.status, 200);
    assert.match(
      exportResponse.headers.get("content-type"),
      /application\/json/,
    );
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
    assert.equal(
      (await post("person/delete", { person_id: 0 }, cookie)).status,
      400,
    );
    assert.equal(
      (await post("person/delete", { person_id: 999999 }, cookie)).status,
      404,
    );
    assert.equal(
      (
        await post(
          "routine/update",
          { routine_id: 0, value: "Routine" },
          cookie,
        )
      ).status,
      400,
    );
    assert.equal(
      (await post("routine/update", { routine_id: 1, value: "  " }, cookie))
        .status,
      400,
    );
    assert.equal(
      (
        await post(
          "routine/update",
          { routine_id: 1, value: "x".repeat(2001) },
          cookie,
        )
      ).status,
      400,
    );
    assert.equal(
      (await post("chat", { message: "I like gym workouts" }, cookie)).status,
      200,
    );
    const routineStatus = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    const fitnessRoutine = routineStatus.routines.find(
      (routine) => routine.routine_key === "fitness_interest",
    );
    assert.ok(fitnessRoutine);
    assert.equal(
      (
        await post(
          "routine/update",
          { routine_id: fitnessRoutine.id, value: "I prefer swimming." },
          cookie,
        )
      ).status,
      200,
    );
    assert.equal(
      (await post("routine/delete", { routine_id: fitnessRoutine.id }, cookie))
        .status,
      200,
    );
    assert.equal(
      (await post("routine/delete", { routine_id: fitnessRoutine.id }, cookie))
        .status,
      404,
    );
    assert.equal(
      (await post("chat", { message: "I like gym workouts" }, cookie)).status,
      200,
    );
    const afterRoutineForget = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(afterRoutineForget.routines.length, 0);
    const afterRoutineForgetExport = await (
      await fetch(base + "/api/memory/export", { headers: { Cookie: cookie } })
    ).json();
    assert.ok(
      afterRoutineForgetExport.records.forgotten_memory_routines.some(
        (entry) => entry.routine_key === "fitness_interest",
      ),
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
    const ambientObservation = withContext.observations.find(
      (o) => o.event_type === "ambient_context",
    );
    assert.ok(Number.isSafeInteger(ambientObservation.id));
    assert.equal(
      (await post("observation/delete", { observation_id: 0 }, cookie)).status,
      400,
    );
    assert.equal(
      (
        await post(
          "observation/delete",
          { observation_id: ambientObservation.id },
          cookie,
        )
      ).status,
      200,
    );
    assert.equal(
      (
        await post(
          "observation/delete",
          { observation_id: ambientObservation.id },
          cookie,
        )
      ).status,
      404,
    );
    const afterObservationDelete = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(
      afterObservationDelete.observations.some(
        (o) => o.id === ambientObservation.id,
      ),
      false,
    );
    assert.equal(
      (await post("observations/clear", {}, cookie, "https://evil.test")).status,
      403,
    );
    assert.ok(afterObservationDelete.observations.length > 0);
    const clearObservations = await post("observations/clear", {}, cookie);
    assert.equal(clearObservations.status, 200);
    assert.equal(
      (await clearObservations.json()).deleted,
      afterObservationDelete.observations.length,
    );
    const clearedObservationStatus = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.deepEqual(clearedObservationStatus.observations, []);
    assert.ok(clearedObservationStatus.facts.length > 0);
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
    assert.equal(restored.conversations.length, 8);
    assert.equal(restored.routines.length, 0);
    assert.equal((await post("conversations/clear", {})).status, 401);
    assert.equal(
      (
        await fetch(base + "/api/conversations/clear", {
          headers: { Cookie: cookie },
        })
      ).status,
      404,
    );
    const clearResponse = await post("conversations/clear", {}, cookie);
    assert.equal(clearResponse.status, 200);
    assert.equal((await clearResponse.json()).deleted, 8);
    const cleared = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(cleared.conversations.length, 0);
    assert.ok(cleared.facts.length > 0);
    assert.ok(
      (await readdir(path.join(dir, "backups"))).some((f) => f.endsWith(".db")),
    );
  } finally {
    await stop();
    await rm(dir, { recursive: true, force: true });
  }
});

test("people memory is private and forget removes its associated timeline", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "aura-people-test-"));
  const db = path.join(dir, "memory.db");
  const personId = Number(
    execFileSync(
      "python3",
      [
        "-c",
        [
          "import sys",
          "from pathlib import Path",
          `sys.path.insert(0, ${JSON.stringify(path.resolve(".."))})`,
          "from memory.sqlite_store import AuraMemoryStore",
          "store = AuraMemoryStore(Path(sys.argv[1]))",
          "store.apply_schema()",
          "user = store.get_or_create_user('Sujan M J', 'Sujan')",
          "person = store.add_known_person(user, 'Alex', relation='friend', notes='private note', consent_to_remember=True)",
          "store.add_person_event(user, person, 'person_introduced', 'Alex was introduced.')",
          "print(person)",
          "store.close()",
        ].join("\n"),
        db,
      ],
      { encoding: "utf8" },
    ).trim(),
  );
  try {
    await start(db);
    const cookie = await login();
    const before = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.deepEqual(before.people.map((person) => person.display_name), ["Alex"]);
    assert.equal(before.people[0].consent_to_remember, 1);
    assert.equal("notes" in before.people[0], false);
    assert.equal(
      (await post("person/create", { display_name: "Taylor" }, cookie)).status,
      400,
    );
    assert.equal(
      (
        await post(
          "person/create",
          { display_name: "Alex", consent_to_remember: true },
          cookie,
        )
      ).status,
      409,
    );
    assert.equal(
      (await post("person/delete", { person_id: personId }, cookie)).status,
      200,
    );
    const after = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.deepEqual(after.people, []);
    const created = await post(
      "person/create",
      {
        display_name: "Taylor",
        relation: "friend",
        consent_to_remember: true,
      },
      cookie,
    );
    assert.equal(created.status, 201);
    const createdPerson = await created.json();
    assert.equal(createdPerson.display_name, "Taylor");
    const afterCreate = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.deepEqual(afterCreate.people.map((person) => person.display_name), ["Taylor"]);
    assert.equal(afterCreate.people[0].face_profile_status, "not_enrolled");
    assert.equal(
      (
        await post(
          "reminder/create",
          { label: "Take medication", local_time: "20:00" },
          cookie,
        )
      ).status,
      400,
    );
    assert.equal(
      (
        await post(
          "reminder/create",
          { label: "Take medication", local_time: "25:00", enabled: true },
          cookie,
        )
      ).status,
      400,
    );
    const reminderResponse = await post(
      "reminder/create",
      { label: "Take medication", local_time: "20:00", enabled: true },
      cookie,
    );
    assert.equal(reminderResponse.status, 201);
    const reminder = await reminderResponse.json();
    assert.equal(
      (await post("reminder/enabled", { reminder_id: reminder.reminder_id, enabled: "false" }, cookie)).status,
      400,
    );
    assert.equal(
      (await post("reminder/enabled", { reminder_id: reminder.reminder_id, enabled: false }, cookie, "https://evil.test")).status,
      403,
    );
    assert.equal(
      (await post("reminder/enabled", { reminder_id: reminder.reminder_id, enabled: false }, cookie)).status,
      200,
    );
    const reminderStatus = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.equal(reminderStatus.reminders[0].label, "Take medication");
    assert.equal(reminderStatus.reminders[0].enabled, false);
    assert.equal(
      (await post("reminder/enabled", { reminder_id: reminder.reminder_id, enabled: true }, cookie)).status,
      200,
    );
    assert.equal(
      (await post("reminder/dismiss", { reminder_id: reminder.reminder_id }, cookie)).status,
      200,
    );
    const dismissedStatus = await (
      await fetch(base + "/api/status", { headers: { Cookie: cookie } })
    ).json();
    assert.ok(dismissedStatus.reminders[0].dismissed_on);
    assert.equal(
      (await post("reminder/delete", { reminder_id: reminder.reminder_id }, cookie)).status,
      200,
    );
    const counts = execFileSync(
      "python3",
      [
        "-c",
        [
          "import sqlite3, sys",
          "conn = sqlite3.connect('file:' + sys.argv[1] + '?mode=ro', uri=True)",
          "print(*conn.execute('select (select count(*) from known_people), (select count(*) from person_events)').fetchone())",
        ].join("\n"),
        db,
      ],
      { encoding: "utf8" },
    ).trim();
    assert.equal(counts, "1 1");
  } finally {
    await stop();
    await rm(dir, { recursive: true, force: true });
  }
});


test("online route needs approval, isolates memory and bounds repeated requests", async () => {
  const dir = await mkdtemp(path.join(os.tmpdir(), "aura-online-test-"));
  const fixture = path.join(dir, "online-fixture.mjs");
  await writeFile(fixture, `globalThis.fetch = async (url, options) => {
    if (url.origin !== "https://en.wikipedia.org" || options.redirect !== "error") throw new Error("Unexpected destination");
    const body = url.pathname === "/w/api.php"
      ? {query:{search:[{pageid:42,title:"Test article"}]}}
      : {pageid:42,type:"standard",extract:"A test source excerpt."};
    return new Response(JSON.stringify(body), {headers:{"content-type":"application/json"}});
  };`);
  try {
    await start(path.join(dir, "memory.db"), { NODE_OPTIONS: `--import=${JSON.stringify(fixture)}` });
    assert.equal((await post("online/lookup", { query: "test", approved: true })).status, 401);
    const cookie = await login();
    assert.equal((await post("online/lookup", { query: "test", approved: true }, cookie, "https://evil.test")).status, 403);
    assert.equal((await post("online/lookup", { query: "test" }, cookie)).status, 400);
    const before = await (await fetch(base + "/api/memory/export", { headers: { Cookie: cookie } })).json();
    const response = await post("online/lookup", { query: "test", approved: true }, cookie);
    assert.equal(response.status, 200);
    assert.equal((await response.json()).sources[0].url, "https://en.wikipedia.org/?curid=42");
    assert.equal((await post("online/lookup", { query: "again", approved: true }, cookie)).status, 429);
    const after = await (await fetch(base + "/api/memory/export", { headers: { Cookie: cookie } })).json();
    assert.deepEqual(after.records, before.records);
  } finally { await stop(); await rm(dir, { recursive: true, force: true }); }
});
