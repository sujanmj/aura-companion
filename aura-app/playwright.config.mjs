import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
const folder = mkdtempSync(path.join(tmpdir(), "aura-browser-"));
export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:18791",
    headless: true,
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "node server/server.mjs",
    url: "http://127.0.0.1:18791",
    env: {
      AURA_PORT: "18791",
      AURA_DB_PATH: path.join(folder, "memory.db"),
      AURA_SESSION_TOKEN: "browser-test-session-123456789",
      AURA_BRAIN_PROVIDER: "local",
      AURA_ENABLE_ACTIONS: "0",
      ELEVENLABS_API_KEY: "",
      AURA_SUPABASE_URL: "",
      AURA_SUPABASE_SERVICE_ROLE_KEY: "",
    },
  },
});
