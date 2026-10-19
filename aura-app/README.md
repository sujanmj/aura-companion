# AURA Companion application — 0.2.0 preview

A new React/Three.js face for the **existing AURA companion**, with its Python personality, relevance filtering, SQLite memory, feedback learning, and Claude provider intact. This is an additive application directory; existing console, sensor, safety, and monitoring commands remain available.

## Run on an Apple Silicon Mac

Requires Node.js **22.12+** (24 recommended), Python **3.11+**, and Chrome/Edge for browser speech recognition. No camera, Windows TTS, or OpenCV dependency is needed for this application.

From the repository:

```sh
cd aura-app
npm ci --ignore-scripts
npm run build
npm start
```

Open **http://127.0.0.1:8790**, then enter the session code printed in the terminal. The port intentionally differs from the existing sensor API at 8787. Stop the server with Control-C. On macOS, `Launch-AURA.command` performs dependency installation/build if needed and launches the server. The downloadable preview is a source/runtime bundle with a prebuilt web interface, **not a signed, notarized, self-contained .app or DMG**. Node and Python remain prerequisites. No system installation, global package changes, or administrator permission is required.

## Preserve your existing companion

By default this uses `data/aura_memory.db` in this repository, exactly like the original console. GitHub does not contain your personal database. If your real memory lives on your Windows computer or in another checkout, securely copy it while the old runtime is stopped, or point `AURA_DB_PATH` at that existing database:

```sh
AURA_DB_PATH='/absolute/path/to/aura_memory.db' npm start
```

Every startup makes a consistent SQLite backup under the database's adjacent `backups/` directory before applying the original schema. No reset or destructive migration runs. Facts, observations, conversation logs, routines, feedback, people, devices and safety records stay in their original tables. Backups contain private memory; manage their retention yourself. The default identity matches the original console (`Sujan M J`); `AURA_USER_ID` selects an existing user ID if needed. Do not run two chat frontends against the same user's memory simultaneously: request ordering is serialized within this application, not across older processes.

## Claude Sonnet and other brains

The **original** `brain/llm_provider.py` remains responsible for companion replies. Configure the existing ignored `config/keys.env`:

```dotenv
AURA_BRAIN_PROVIDER=claude
ANTHROPIC_API_KEY=your-local-key
ANTHROPIC_MODEL=your-enabled-sonnet-model-id
```

Use the Sonnet model ID already working in your account. No provider key is sent to the browser or built into JavaScript. The original local fallback remains available; the UI labels fallback responses. Greetings intentionally use the original local reaction engine. Without credentials, this is a rule-based companion, not an offline language model.

## Voice and appearance

- Click **Enable microphone**, then say **Hey AURA**, followed by your message. You can also pause after the wake phrase and speak within 15 seconds.
- Speech becomes an **editable draft**. Click Send to store it and get a response. Ambient speech does not submit actions.
- Toggle **Speak replies** for browser TTS; **Stop speaking** interrupts output. Turning off the microphone releases media tracks.
- Browser speech recognition may send audio to the browser vendor. It is not promised offline. Mic use is opt-in and should be turned off when no longer needed.
- Optional cloud voice: export `ELEVENLABS_API_KEY` and `AURA_VOICE_ID` into the server environment before launching. STT uses Scribe; TTS uses Eleven multilingual v2. API keys stay server-side. With cloud STT enabled, detected speech segments go to ElevenLabs while the mic is on, including segments before a wake phrase. The local VAD is adapted from Jarvis.
- Choose **Calm glow** or **Holographic**. Theme choice alone is saved in browser storage. No Iron Man artwork, movie dialogue, original demo audio, or wake-word media is bundled.
- Browser recognition can be throttled in background tabs; the app retries ended sessions. If it stops responding, toggle the microphone or type. Physical microphone, speakers, and cloud voice still need device acceptance testing.

## Optional automation — disabled by default

The SDK bridge follows the Jarvis architecture but intentionally does **not** load `~/.claude.json`, project settings, filesystem tools, shell tools, or the old broad tool-name heuristics. Native SDK tools are disabled (`tools: []`). Use Claude Code installed and authenticated locally for this optional mode; this authentication is separate from the companion's API key.

Create ignored `aura-app/mcp.local.json` using MCP servers you trust:

```json
{
  "servers": {
    "my_service": {"command": "/absolute/path/to/audited-server", "args": []}
  },
  "allowedTools": ["mcp__my_service__exact_tool_name"]
}
```

Then launch with `AURA_ENABLE_ACTIONS=1 npm start`. This explicitly allows the configured server programs to start when a task runs. MCP server startup itself executes local code; install and inspect those programs yourself. The app does not install MCP servers or auto-discover them.

Use the **Actions** tab to submit a task. Every allowed tool call displays its exact name and arguments and requires a fresh approve/deny click. Unknown tools and all built-in filesystem/shell tools remain denied. Approval expires after 60 seconds, cannot be replayed, and never applies to a different invocation. Tasks expire after two minutes and can be cancelled; cancellation cannot undo a tool action that already completed. Read operations also require approval: tool names are not reliable evidence of safety. External MCP servers remain responsible for their own side effects; this is not an OS sandbox. Action tasks use an AURA system prompt but **do not receive personal SQLite memories** or write task output into companion history in this preview.

## Security boundary

The Node server binds only `127.0.0.1`. Exact Host validation blocks DNS rebinding; state-changing API requests require the matching Origin, and any supplied foreign Origin is rejected. A random per-launch code exchanges for an HttpOnly, SameSite=Strict cookie. Provider secrets and the login code are never stored in localStorage. The cookie is intentionally local HTTP, suitable only for the loopback bind; do not expose this server through a reverse proxy or change it to a network bind. There is no arbitrary file/media proxy or model-generated HTML. React escapes messages; CSP blocks frames and remote scripts. The Python worker has no HTTP port and accepts only private stdin/stdout messages. Authentication protects memory reads as well as writes. This local app trusts software already running as your OS user.

## Development and verification

```sh
npm run build       # TypeScript plus production bundle
npm run lint
npm test            # real loopback server + temp SQLite, auth, origin/host, persistence, approvals
python3 -m unittest discover -s tests -p 'test_*.py'
npm run bundle      # tracked source + production UI, no keys or memory
```

For live UI development, run `AURA_DEV=1 npm start` and `npm run dev` in separate terminals, then open `http://127.0.0.1:5173`. Development admits exactly that extra origin; production does not. Run the build first for the server integration test. GitHub Actions repeats build, lint, tests, and artifact creation on macOS and Linux.

Tests use disposable databases and mocked Claude responses; they do not charge your API account. Live Claude, ElevenLabs, and user-specific MCP tools require your actual credentials and configuration and are not proven by these tests. The earlier Windows/sensor scripts are untouched and not launched by the new app. Camera UI, emergency dispatch, iPhone control, task history and a native menu-bar app are outside this preview.

## Source and attribution

Upstream: [adewaskar/jarvis](https://github.com/adewaskar/jarvis), inspected at commit `1c4016afdf86f7043efc6882ceffef84ad0d8783`.

Reused/adapted MIT code: `src/scene/Core.tsx`, `src/scene/Particles.tsx`, `src/lib/audio.ts`, `src/lib/vad.ts`, and the Agent SDK bridge pattern. See [LICENSE-JARVIS](LICENSE-JARVIS) for the original copyright and permission notice. New AURA glue and UI are MIT-licensed under [LICENSE](LICENSE). The existing repository's original code remains under its original terms. No upstream `public/audio` or other demo media was copied.

Architecture: browser → authenticated loopback Node bridge → private Python worker → existing AURA engine / SQLite / server-side Claude API. Optional actions use a separate, bounded Claude Agent SDK session with explicit MCP configuration and approval hooks.
