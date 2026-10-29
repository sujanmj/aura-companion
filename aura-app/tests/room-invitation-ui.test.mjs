import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";

const token = "test-dashboard-admin-token-that-is-long-enough";
const sessionId = "5d62dff8-07bb-4a96-b19c-0f7046133798";
const node = {
  node_id: "bedroom",
  display_name: "Bedroom Pi",
  room: "bedroom",
  disabled: 0,
  token: "must-not-render",
};
const kitchenNode = {
  node_id: "kitchen",
  display_name: "Kitchen Pi",
  room: "kitchen",
  disabled: 0,
};

class Element {
  constructor() {
    this.handlers = {};
    this.options = [];
    this.value = "";
    this.textContent = "";
    this.disabled = false;
  }
  addEventListener(name, callback) { this.handlers[name] = callback; }
  appendChild(option) {
    this.options.push(option);
    if (this.options.length === 1) this.value = option.value;
  }
  replaceChildren() { this.options = []; this.value = ""; }
  click() { this.handlers.click?.(); }
  change() { this.handlers.change?.(); }
}

async function dashboardHarness(initialToken = token) {
  const html = await readFile(new URL("../../web/room_invitation.js", import.meta.url), "utf8");
  const ids = [
    "room-invitation-status", "room-invitation-details", "room-invite-node",
    "room-transfer-node", "room-invite-btn", "room-transfer-btn",
    "room-refresh-btn", "room-stop-btn",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new Element()]));
  const requests = [];
  let promptAnswers = [];
  let activeSession = null;
  let loseNextMutationResponse = false;
  let storedToken = initialToken;
  const fetch = async (url, init) => {
    requests.push({ url, init });
    let body;
    if (url === "/nodes/status") {
      body = { ok: true, nodes: [node, kitchenNode] };
    } else if (url === "/rooms/status") {
      body = { ok: true, session: activeSession };
    } else if (url === "/rooms/start") {
      activeSession = {
        session_id: sessionId,
        generation: 1,
        node_id: "bedroom",
        expires_at: 1_900_000_000,
      };
      body = { ok: true, session: activeSession };
    } else if (url === "/rooms/transfer") {
      activeSession = { ...activeSession, node_id: "kitchen", generation: 2 };
      body = { ok: true, session: activeSession };
    } else if (url === "/rooms/stop") {
      activeSession = null;
      body = { ok: true, session: null };
    } else {
      throw new Error(`Unexpected request ${url}`);
    }
    if (init.method === "POST" && url !== "/rooms/status" && loseNextMutationResponse) {
      loseNextMutationResponse = false;
      throw new TypeError("Failed to fetch");
    }
    return { ok: true, status: 200, json: async () => body };
  };
  const windowEvents = {};
  const window = {
    prompt: () => promptAnswers.shift() ?? null,
    addEventListener: (name, callback) => { windowEvents[name] = callback; },
    dispatchEvent: (event) => { windowEvents[event.type]?.(event); },
  };
  const localStorage = { getItem: (key) => key === "AURA_SENSOR_API_TOKEN" ? storedToken : null };
  vm.runInNewContext(html, {
    document: {
      getElementById: (id) => elements[id],
      createElement: () => new Element(),
    },
    window,
    localStorage,
    fetch,
    Date,
    Number,
    Array,
    Promise,
  });
  const settle = async () => {
    await new Promise((resolve) => setImmediate(resolve));
    await new Promise((resolve) => setImmediate(resolve));
  };
  await settle();
  return {
    elements,
    requests,
    setAnswers: (answers) => { promptAnswers = answers; },
    loseNextMutationResponse: () => { loseNextMutationResponse = true; },
    setToken: (value) => { storedToken = value; },
    tokenChanged: () => window.dispatchEvent({ type: "aura-token-changed" }),
    settle,
  };
}

test("room manager requires exact typed consent before sending an invitation", async () => {
  const ui = await dashboardHarness();
  const controls = ui.elements;
  controls["room-invite-node"].value = "bedroom";
  controls["room-invite-node"].change();
  const before = ui.requests.length;

  ui.setAnswers(["invite bedroom"]);
  controls["room-invite-btn"].click();
  assert.equal(ui.requests.length, before);
  assert.match(controls["room-invitation-status"].textContent, /Canceled/);

  ui.setAnswers(["INVITE bedroom"]);
  controls["room-invite-btn"].click();
  await ui.settle();
  const mutation = ui.requests.filter((request) => request.url === "/rooms/start");
  assert.equal(mutation.length, 1);
  assert.deepEqual(JSON.parse(mutation[0].init.body), { node_id: "bedroom", approved: true });
  assert.equal(mutation[0].init.redirect, "error");
  assert.equal(mutation[0].init.headers["X-AURA-API-Token"], token);
  assert.match(controls["room-invitation-details"].textContent, new RegExp(sessionId));
  assert.doesNotMatch(controls["room-invitation-details"].textContent, /must-not-render|token/i);
  assert.equal(controls["room-invite-node"].options.some((option) => option.textContent.includes("must-not-render")), false);
  assert.match(controls["room-invitation-status"].textContent, /No sensor or audio action is active/);
});

test("saving or clearing the dashboard token reloads room status", async () => {
  const ui = await dashboardHarness("");
  const controls = ui.elements;
  assert.equal(ui.requests.length, 0);
  assert.match(controls["room-invitation-status"].textContent, /API token above/);

  ui.setToken(token);
  ui.tokenChanged();
  await ui.settle();
  assert.equal(ui.requests.filter((request) => request.url === "/rooms/status").length, 1);
  assert.equal(controls["room-invite-node"].options.length, 3);

  ui.setToken("");
  ui.tokenChanged();
  await ui.settle();
  assert.equal(controls["room-invite-node"].disabled, true);
  assert.match(controls["room-invitation-status"].textContent, /API token above/);
});

test("lost mutation response asks the owner to inspect status instead of retrying", async () => {
  const ui = await dashboardHarness();
  const controls = ui.elements;
  controls["room-invite-node"].value = "bedroom";
  controls["room-invite-node"].change();
  ui.setAnswers(["INVITE bedroom"]);
  ui.loseNextMutationResponse();
  controls["room-invite-btn"].click();
  await ui.settle();
  assert.equal(ui.requests.filter((request) => request.url === "/rooms/start").length, 1);
  assert.match(controls["room-invitation-status"].textContent, /Refresh invitation status before retrying/);
  assert.equal(controls["room-invite-btn"].disabled, true);
  controls["room-invite-btn"].click();
  await ui.settle();
  assert.equal(ui.requests.filter((request) => request.url === "/rooms/start").length, 1);

  controls["room-refresh-btn"].click();
  await ui.settle();
  assert.match(controls["room-invitation-details"].textContent, new RegExp(sessionId));
  assert.equal(ui.requests.filter((request) => request.url === "/rooms/start").length, 1);
});

test("transfer and stop confirm each exact action and send one request each", async () => {
  const ui = await dashboardHarness();
  const controls = ui.elements;
  controls["room-invite-node"].value = "bedroom";
  ui.setAnswers(["INVITE bedroom"]);
  controls["room-invite-btn"].click();
  await ui.settle();

  controls["room-transfer-node"].value = "kitchen";
  controls["room-transfer-node"].change();
  ui.setAnswers(["TRANSFER kitchen"]);
  controls["room-transfer-btn"].click();
  await ui.settle();
  const transfer = ui.requests.filter((request) => request.url === "/rooms/transfer");
  assert.equal(transfer.length, 1);
  assert.deepEqual(JSON.parse(transfer[0].init.body), {
    session_id: sessionId,
    generation: 1,
    node_id: "kitchen",
    approved: true,
  });
  assert.match(controls["room-invitation-details"].textContent, /Generation: 2/);

  ui.setAnswers([`STOP ${sessionId}`]);
  controls["room-stop-btn"].click();
  await ui.settle();
  const stop = ui.requests.filter((request) => request.url === "/rooms/stop");
  assert.equal(stop.length, 1);
  assert.deepEqual(JSON.parse(stop[0].init.body), { session_id: sessionId, generation: 2 });
  assert.match(controls["room-invitation-details"].textContent, /No active room invitation/);
});
