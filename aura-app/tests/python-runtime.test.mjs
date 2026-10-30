import test from "node:test";
import assert from "node:assert/strict";
import { MemoryClient } from "../server/memory-client.mjs";
import { pythonCommand, pythonEnvironment } from "../server/python-runtime.mjs";
import { once } from "node:events";

test("Python selection preserves an explicit executable and uses platform defaults", () => {
  assert.equal(pythonCommand({}, "win32"), "python");
  assert.equal(pythonCommand({}, "darwin"), "python3");
  assert.equal(pythonCommand({ AURA_PYTHON: "C:\\Program Files\\Python\\python.exe" }, "win32"), "C:\\Program Files\\Python\\python.exe");
});

test("memory IPC round-trips Unicode independently of the inherited code page", async () => {
  const client = new MemoryClient({
    command: pythonCommand(),
    env: pythonEnvironment({ ...process.env, PYTHONIOENCODING: "ascii" }),
    args: ["-c", "import sys,json\nfor line in sys.stdin:\n r=json.loads(line); print(json.dumps({'id':r['id'],'result':r['text']},ensure_ascii=False),flush=True)"],
  });
  const exited = once(client.worker, "exit");
  try {
    const text = "नमस्ते — café 🌱";
    assert.equal(await client.request("echo", { text }), text);
  } finally {
    client.close();
    await exited;
  }
});
