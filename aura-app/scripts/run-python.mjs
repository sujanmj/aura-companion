import { spawnSync } from "node:child_process";
import { pythonCommand, pythonEnvironment } from "../server/python-runtime.mjs";
const result = spawnSync(pythonCommand(), process.argv.slice(2), {
  env: pythonEnvironment(),
  stdio: "inherit",
  shell: false,
});
if (result.error) {
  console.error("Python could not start. Install Python 3.11+ or set AURA_PYTHON to its executable path.");
}
process.exitCode = result.status ?? 1;
