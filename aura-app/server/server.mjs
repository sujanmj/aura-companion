import http from "node:http";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { readFileSync, existsSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { pythonCommand, pythonEnvironment } from "./python-runtime.mjs";
import { MemoryClient } from "./memory-client.mjs";
import { ApprovalGate, permittedOrigin } from "./policy.mjs";
import { lookupWikipedia } from "./online-lookup.mjs";
let onlineBusy = false;
let nextOnlineLookup = 0;

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const port = Number(process.env.AURA_PORT || 8790);
const host = `127.0.0.1:${port}`;
const token =
  process.env.AURA_SESSION_TOKEN || randomBytes(24).toString("base64url");
if (token.length < 24)
  throw new Error("AURA_SESSION_TOKEN must be at least 24 characters");
const session = randomBytes(32).toString("base64url");
let busy = false;
let task = null;
const memoryClient = new MemoryClient({
  command: pythonCommand(),
  env: pythonEnvironment(),
  args: [path.join(ROOT, "server/memory_worker.py")],
});
const memory = (op, data = {}) => memoryClient.request(op, data);
const configPath = path.join(ROOT, "mcp.local.json");
const config = existsSync(configPath)
  ? JSON.parse(readFileSync(configPath, "utf8"))
  : { servers: {}, allowedTools: [] };
const actionsEnabled = process.env.AURA_ENABLE_ACTIONS === "1";
let gate = new ApprovalGate({
  enabled: actionsEnabled,
  allowed: config.allowedTools || [],
});
let controller = null;
function safeEqual(a, b) {
  const x = Buffer.from(a || ""),
    y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
}
async function body(req, max = 32768) {
  const chunks = [];
  let n = 0;
  for await (const chunk of req) {
    n += chunk.length;
    if (n > max)
      throw Object.assign(new Error("Request too large"), { status: 413 });
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}
function json(res, status, data) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(data));
}
async function voice(req, res, route) {
  const key = process.env.ELEVENLABS_API_KEY;
  if (!key)
    return json(res, 503, {
      error: "ElevenLabs is not configured; use browser voice.",
    });
  let url, options;
  if (route === "stt") {
    const bytes = await body(req, 8 * 1024 * 1024);
    const form = new FormData();
    form.append(
      "file",
      new Blob([bytes], { type: req.headers["content-type"] || "audio/webm" }),
      "speech.webm",
    );
    form.append("model_id", "scribe_v1");
    url = "https://api.elevenlabs.io/v1/speech-to-text";
    options = { body: form };
  } else {
    const data = JSON.parse((await body(req)).toString());
    if (typeof data.text !== "string" || data.text.length > 8000)
      return json(res, 400, { error: "Invalid speech text" });
    const voiceId = process.env.AURA_VOICE_ID;
    if (!voiceId || !/^[a-zA-Z0-9]+$/.test(voiceId))
      return json(res, 503, { error: "Set AURA_VOICE_ID for cloud speech." });
    url = `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`;
    options = {
      body: JSON.stringify({
        text: data.text,
        model_id: "eleven_multilingual_v2",
      }),
      headers: { "content-type": "application/json" },
    };
  }
  const response = await fetch(url, {
    ...options,
    method: "POST",
    headers: { ...options.headers, "xi-api-key": key },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok)
    return json(res, 502, { error: "Voice provider unavailable" });
  const bytes = Buffer.from(await response.arrayBuffer());
  res.writeHead(200, {
    "Content-Type": route === "stt" ? "application/json" : "audio/mpeg",
  });
  res.end(bytes);
}
const server = http.createServer(async (req, res) => {
  res.setHeader("Cache-Control", "no-store");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("Referrer-Policy", "no-referrer");
  res.setHeader(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
  );
  try {
    if (req.headers.host !== host)
      return json(res, 403, { error: "Invalid host" });
    const url = new URL(req.url, `http://${host}`);
    if (url.pathname.startsWith("/api/")) {
      if (
        req.method !== "GET" &&
        !permittedOrigin(req.headers.origin, port, process.env.AURA_DEV === "1")
      )
        return json(res, 403, { error: "Invalid origin" });
      if (
        req.headers.origin &&
        !permittedOrigin(req.headers.origin, port, process.env.AURA_DEV === "1")
      )
        return json(res, 403, { error: "Invalid origin" });
      if (req.method === "POST" && url.pathname === "/api/login") {
        const data = JSON.parse((await body(req)).toString());
        if (!safeEqual(data.token, token))
          return json(res, 401, { error: "Incorrect session code" });
        res.setHeader(
          "Set-Cookie",
          `aura_session=${session}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200`,
        );
        return json(res, 200, { ok: true });
      }
      const cookie = (req.headers.cookie || "")
        .split(";")
        .map((s) => s.trim())
        .find((s) => s.startsWith("aura_session="))
        ?.slice(13);
      if (!safeEqual(cookie, session))
        return json(res, 401, {
          error: "Enter the session code shown in your terminal.",
        });
      if (req.method === "GET" && url.pathname === "/api/readiness") {
        let readiness;
        try {
          readiness = await memory("readiness");
        } catch {
          return json(res, 503, {
            error:
              "Memory service unavailable. Restart AURA after checking Python and database access.",
          });
        }
        return json(res, 200, {
          ...readiness,
          voice: {
            stt: process.env.ELEVENLABS_API_KEY
              ? "configured_unverified"
              : "browser",
            tts:
              process.env.ELEVENLABS_API_KEY &&
              /^[a-zA-Z0-9]+$/.test(process.env.AURA_VOICE_ID || "")
                ? "configured_unverified"
                : "browser",
          },
          actions: {
            state: !actionsEnabled
              ? "disabled"
              : Object.keys(config.servers || {}).length &&
                  (config.allowedTools || []).length
                ? "configured_unverified"
                : "missing_configuration",
          },
          hardware: "not_tested",
        });
      }
      if (req.method === "POST" && url.pathname === "/api/readiness/provider-test") {
        try {
          await body(req, 1024);
          return json(res, 200, await memory("provider_test"));
        } catch (error) {
          if (error.status) return json(res, error.status, { error: "Request too large" });
          return json(res, 503, {
            error: "Provider test could not run. Check the local memory service and provider configuration.",
          });
        }
      }
      if (req.method === "GET" && url.pathname === "/api/memory/export") {
        try {
          const exported = await memory("export");
          res.writeHead(200, {
            "Content-Type": "application/json; charset=utf-8",
            "Content-Disposition":
              'attachment; filename="aura-memory-export.json"',
          });
          return res.end(`${JSON.stringify(exported, null, 2)}\n`);
        } catch {
          return json(res, 503, {
            error:
              "Memory export is unavailable. Check the local memory service.",
          });
        }
      }
      if (
        req.method === "POST" &&
        url.pathname === "/api/conversations/clear"
      ) {
        try {
          return json(res, 200, await memory("clear_conversations"));
        } catch {
          return json(res, 503, {
            error: "Conversation history could not be cleared.",
          });
        }
      }
      if (req.method === "POST" && url.pathname === "/api/observations/clear") {
        try {
          return json(res, 200, await memory("clear_observations"));
        } catch {
          return json(res, 503, {
            error: "Saved observations could not be cleared.",
          });
        }
      }
      if (req.method === "GET" && url.pathname === "/api/preferences") {
        try {
          return json(res, 200, await memory("preferences"));
        } catch {
          return json(res, 503, { error: "Preferences are unavailable." });
        }
      }
      if (req.method === "GET" && url.pathname === "/api/status")
        return json(res, 200, {
          ...(await memory("status")),
          actions: gate.enabled,
          stt: !!process.env.ELEVENLABS_API_KEY,
          tts: !!(process.env.ELEVENLABS_API_KEY && process.env.AURA_VOICE_ID),
        });
      if (req.method === "GET" && url.pathname === "/api/task")
        return json(res, 200, { task, approvals: gate.list() });
      if (req.method !== "POST") return json(res, 404, { error: "Not found" });
      if (["/api/stt", "/api/tts"].includes(url.pathname))
        return await voice(req, res, url.pathname.slice(5));
      const data = JSON.parse((await body(req)).toString());
      if (["/api/observations/retention", "/api/observations/retention-preview"].includes(url.pathname)) {
        if (!Number.isInteger(data.days) || ![0, 1, 7, 30, 90, 365].includes(data.days))
          return json(res, 400, { error: "Invalid observation retention." });
        const saving = url.pathname === "/api/observations/retention";
        if (saving && data.confirmed !== true)
          return json(res, 400, { error: "Confirm the retention change first." });
        try {
          return json(res, 200, await memory(saving ? "set_observation_retention" : "preview_observation_expiry", { days: data.days }));
        } catch {
          return json(res, 503, { error: "Observation retention is unavailable." });
        }
      }
      if (url.pathname === "/api/online/lookup") {
        if (data.approved !== true || typeof data.query !== "string" || !data.query.trim() || data.query.length > 300)
          return json(res, 400, { error: "Review and approve a query of 1–300 characters." });
        if (onlineBusy || Date.now() < nextOnlineLookup)
          return json(res, 429, { error: "Wait a moment before another lookup." });
        onlineBusy = true;
        const controller = new AbortController();
        const disconnect = () => { if (!res.writableEnded) controller.abort(); };
        res.on("close", disconnect);
        try {
          const result = await lookupWikipedia(data.query, true, { signal: controller.signal });
          if (!res.destroyed) return json(res, 200, result);
        } catch {
          if (!res.destroyed) return json(res, 502, { error: "Wikipedia could not be checked. No answer has been verified; try again later." });
        } finally {
          res.off("close", disconnect);
          onlineBusy = false;
          nextOnlineLookup = Date.now() + 2000;
        }
        return;
      }
      if (url.pathname === "/api/ambient/observation") {
        if (
          !Array.isArray(data.labels) ||
          data.labels.length > 4 ||
          data.labels.some(
            (label) =>
              typeof label !== "string" ||
              label.trim().length < 1 ||
              label.trim().length > 64 ||
              !/^[A-Za-z0-9 _-]+$/.test(label.trim()),
          ) ||
          typeof data.human_present !== "boolean" ||
          typeof data.confidence !== "number" ||
          !Number.isFinite(data.confidence) ||
          data.confidence < 0 ||
          data.confidence > 1
        )
          return json(res, 400, { error: "Scene summary is invalid." });
        try {
          return json(
            res,
            200,
            await memory("ambient_scene", {
              labels: data.labels,
              human_present: data.human_present,
              confidence: data.confidence,
            }),
          );
        } catch {
          return json(res, 503, {
            error: "AURA could not save the local scene summary.",
          });
        }
      }
      if (url.pathname === "/api/preferences") {
        if (
          typeof data.checkins_enabled !== "boolean" ||
          typeof data.quiet_start !== "string" ||
          typeof data.quiet_end !== "string" ||
          !Number.isSafeInteger(data.checkin_interval_hours) ||
          data.checkin_interval_hours < 4 ||
          data.checkin_interval_hours > 168
        )
          return json(res, 400, { error: "Check-in preferences are invalid." });
        try {
          const saved = await memory("update_preferences", data);
          return json(res, 200, saved);
        } catch {
          return json(res, 400, { error: "Check-in preferences are invalid." });
        }
      }
      if (url.pathname === "/api/checkin") {
        try {
          return json(res, 200, await memory("checkin"));
        } catch {
          return json(res, 503, {
            error: "AURA could not check in right now.",
          });
        }
      }
      if (url.pathname === "/api/approve")
        return json(res, gate.resolve(data.id, data.approved) ? 200 : 404, {
          ok: true,
        });
      if (url.pathname === "/api/cancel") {
        controller?.abort();
        gate.close();
        return json(res, 200, { ok: true });
      }
      if (url.pathname === "/api/reminder/create") {
        if (
          typeof data.label !== "string" ||
          !data.label.trim() ||
          data.label.trim().length > 120 ||
          typeof data.local_time !== "string" ||
          !/^([01]\d|2[0-3]):[0-5]\d$/.test(data.local_time) ||
          !Array.isArray(data.days_of_week) ||
          data.days_of_week.length < 1 ||
          data.days_of_week.length > 7 ||
          data.days_of_week.some((day) => !Number.isInteger(day) || day < 1 || day > 7) ||
          new Set(data.days_of_week).size !== data.days_of_week.length
        )
          return json(res, 400, { error: "Enter a reminder and a valid local time." });
        if (data.enabled !== true)
          return json(res, 400, { error: "Confirm that you want this reminder enabled." });
        try {
          return json(
            res,
            201,
            await memory("create_reminder", {
              label: data.label,
              local_time: data.local_time,
              days_of_week: data.days_of_week,
            }),
          );
        } catch {
          return json(res, 400, { error: "AURA could not save this reminder." });
        }
      }
      if (
        url.pathname === "/api/reminder/delete" ||
        url.pathname === "/api/reminder/dismiss" ||
        url.pathname === "/api/reminder/enabled"
      ) {
        if (!Number.isSafeInteger(data.reminder_id) || data.reminder_id <= 0)
          return json(res, 400, { error: "Choose a valid reminder." });
        if (url.pathname === "/api/reminder/enabled" && typeof data.enabled !== "boolean")
          return json(res, 400, { error: "Choose whether this reminder should be active." });
        try {
          const op = url.pathname.endsWith("/delete")
            ? "delete_reminder"
            : url.pathname.endsWith("/enabled")
              ? "set_reminder_enabled"
              : "dismiss_reminder";
          const result = await memory(op, data);
          if (result.reason === "not_found")
            return json(res, 404, { error: "That reminder could not be found." });
          if (result.reason === "limit")
            return json(res, 409, { error: "Pause another reminder before enabling this one." });
          return json(res, 200, result);
        } catch {
          return json(res, 404, { error: "That reminder could not be found." });
        }
      }
      if (url.pathname === "/api/person/create") {
        if (
          typeof data.display_name !== "string" ||
          !data.display_name.trim() ||
          data.display_name.trim().length > 100 ||
          (data.relation !== undefined &&
            data.relation !== null &&
            (typeof data.relation !== "string" || data.relation.length > 100))
        )
          return json(res, 400, { error: "Enter a name and an optional short relationship." });
        if (data.consent_to_remember !== true)
          return json(res, 400, { error: "Confirm that this person agreed to be remembered." });
        try {
          const result = await memory("create_person", {
            display_name: data.display_name,
            relation: data.relation,
            consent_to_remember: true,
          });
          if (!result.created)
            return json(res, 409, { error: "That person is already in AURA memory." });
          return json(res, 201, result);
        } catch {
          return json(res, 503, { error: "AURA could not save this person right now." });
        }
      }
      if (
        url.pathname === "/api/fact/update" ||
        url.pathname === "/api/fact/delete" ||
        url.pathname === "/api/routine/update" ||
        url.pathname === "/api/routine/delete" ||
        url.pathname === "/api/observation/correct" ||
        url.pathname === "/api/observation/delete" ||
        url.pathname === "/api/person/delete"
      ) {
        const isRoutine = url.pathname.startsWith("/api/routine/");
        const isObservation = url.pathname.startsWith("/api/observation/");
        const isObservationCorrection = url.pathname === "/api/observation/correct";
        const isPerson = url.pathname === "/api/person/delete";
        const idKey = isRoutine
          ? "routine_id"
          : isObservation
            ? "observation_id"
            : isPerson
              ? "person_id"
              : "fact_id";
        const label = isRoutine
          ? "memory routine"
          : isObservation
            ? "observation"
            : isPerson
              ? "known person"
              : "memory fact";
        if (!Number.isSafeInteger(data[idKey]) || data[idKey] <= 0)
          return json(res, 400, { error: `Choose a valid ${label}.` });
        if (
          (url.pathname.endsWith("/update") || isObservationCorrection) &&
          (typeof data.value !== "string" ||
            !data.value.trim() ||
            data.value.length > (isObservationCorrection ? 500 : 2000))
        )
          return json(res, 400, {
            error: isObservationCorrection
              ? "An observation correction must contain 1–500 characters."
              : "A correction must contain 1–2000 characters.",
          });
        try {
          const result = await memory(
            isObservationCorrection
              ? "correct_observation"
              : url.pathname === "/api/observation/delete"
              ? "delete_observation"
              : isPerson
                ? "forget_person"
                : `${url.pathname.endsWith("/update") ? "update" : "delete"}_${isRoutine ? "routine" : "fact"}`,
            data,
          );
          return json(res, 200, result);
        } catch {
          return json(res, 404, {
            error: `That ${label} could not be found.`,
          });
        }
      }
      if (url.pathname === "/api/feedback")
        return json(
          res,
          200,
          await memory("feedback", {
            response_id: data.response_id,
            rating: data.rating,
            note: data.note,
          }),
        );
      if (!["/api/chat", "/api/ambient", "/api/shared", "/api/private", "/api/task"].includes(url.pathname))
        return json(res, 404, { error: "Not found" });
      if (
        typeof data.message !== "string" ||
        !data.message.trim() ||
        data.message.length > 8000
      )
        return json(res, 400, {
          error: "Message must contain 1–8000 characters",
        });
      if (busy)
        return json(res, 409, { error: "AURA is finishing another request." });
      if (url.pathname === "/api/private") {
        if (data.consent !== true)
          return json(res, 400, { error: "Review the message and confirm this private turn." });
        busy = true;
        try {
          return json(res, 200, await memory("private_chat", { message: data.message }));
        } finally { busy = false; }
      }
      if (url.pathname === "/api/shared") {
        if (data.consent !== true || data.message.trim().length > 4000 ||
            (data.history !== undefined && (!Array.isArray(data.history) || data.history.length > 6)))
          return json(res, 400, { error: "Review the shared question and confirm participants agree." });
        busy = true;
        try {
          return json(res, 200, await memory("shared_chat", { message: data.message, history: data.history || [], consent: true }));
        } finally { busy = false; }
      }
      if (["/api/chat", "/api/ambient"].includes(url.pathname)) {
        busy = true;
        try {
          return json(
            res,
            200,
            await memory("chat", {
              message: data.message,
              observation:
                url.pathname === "/api/ambient" &&
                typeof data.observation === "string"
                  ? data.observation.slice(0, 500)
                  : "",
            }),
          );
        } finally {
          busy = false;
        }
      }
      if (!gate.enabled)
        return json(res, 403, {
          error:
            "Actions are disabled. Configure an explicit MCP tool list and enable actions on the server.",
        });
      busy = true;
      gate = new ApprovalGate({
        enabled: actionsEnabled,
        allowed: config.allowedTools || [],
      });
      controller = new AbortController();
      task = { state: "running", response: "" };
      const timer = setTimeout(() => {
        controller.abort();
        gate.close();
      }, 120000);
      import("./agent.mjs")
        .then(({ runAgent }) =>
          runAgent(
            data.message,
            config,
            gate,
            path.join(ROOT, ".agent-work"),
            controller.signal,
          ),
        )
        .then((response) => {
          task = { state: "done", response };
        })
        .catch(() => {
          task = {
            state: "failed",
            response:
              "Task failed or was cancelled. Check Claude Code login and MCP configuration.",
          };
        })
        .finally(() => {
          clearTimeout(timer);
          busy = false;
          gate.close();
        });
      return json(res, 202, { ok: true });
    }
    if (req.method !== "GET")
      return json(res, 405, { error: "Method not allowed" });
    const relative =
      url.pathname === "/"
        ? "index.html"
        : decodeURIComponent(url.pathname).slice(1);
    const base = path.join(ROOT, "dist");
    const file = path.resolve(base, relative);
    if (!file.startsWith(base + path.sep))
      return json(res, 404, { error: "Not found" });
    const bytes = await readFile(file).catch(() => null);
    if (!bytes)
      return json(res, 404, {
        error: "Build the app first with npm run build.",
      });
    const mime =
      {
        ".html": "text/html",
        ".js": "text/javascript",
        ".css": "text/css",
        ".svg": "image/svg+xml",
      }[path.extname(file)] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": mime });
    res.end(bytes);
  } catch (error) {
    json(res, error.status || 400, {
      error: "Request failed. Check input and local service configuration.",
    });
  }
});
server.requestTimeout = 45000;
server.headersTimeout = 10000;
server.listen(port, "127.0.0.1", () => {
  console.log(
    `AURA Companion · http://${host}\nSession code: ${token}\nActions: ${gate.enabled ? "explicit tools, each requires approval" : "disabled"}`,
  );
});
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  controller?.abort();
  gate.close();
  const workerClosed = memoryClient.close();
  const serverClosed = new Promise((resolve) => server.close(resolve));
  await Promise.all([workerClosed, serverClosed]);
  process.exit(0);
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
