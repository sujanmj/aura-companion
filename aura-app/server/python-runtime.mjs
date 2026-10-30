// One interpreter choice for the server, build helpers and integration tests.
export function pythonCommand(env = process.env, platform = process.platform) {
  return env.AURA_PYTHON || (platform === "win32" ? "python" : "python3");
}
export function pythonEnvironment(env = process.env) {
  // IPC contains user text; do not depend on the Windows console code page.
  return { ...env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" };
}
