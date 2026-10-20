# AURA Companion application — 0.3.0 ambient preview

A new React/Three.js face for the **existing AURA companion**, with its Python personality, relevance filtering, SQLite memory, feedback learning, and Claude provider intact. This is an additive application directory; existing console, sensor, safety, and monitoring commands remain available.

## Run on an Apple Silicon Mac

Requires Node.js **22.12+** (24 recommended), Python **3.11+**, and Chrome/Edge for browser speech recognition. No Windows TTS or OpenCV dependency is needed. The native ambient mode uses Apple Speech and Vision frameworks on macOS 13 or newer; Safari/Chrome is only needed for the web interface.

From the repository:

```sh
cd aura-app
npm ci --ignore-scripts
npm run build
npm start
```

Open **http://127.0.0.1:8790**, then enter the session code printed in the terminal. The port intentionally differs from the existing sensor API at 8787. Stop the server with Control-C. On macOS, `Launch-AURA.command` performs dependency installation/build if needed and launches the server. The downloadable preview is a source/runtime bundle with a prebuilt web interface, **not notarized**. The ZIP includes a locally signed, native menu bar app when built on macOS. Node and Python remain prerequisites. No system installation, global package changes, or administrator permission is required.

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

## Optional 24/7 ambient mode on Mac

The native menu bar helper can stay running while your Mac is awake, even when you close the web browser. Build it on Apple Silicon with `npm run macos:app`; it appears in the ZIP as `release/AURA Companion.app`. Start the AURA web server first with `npm start`, then open the menu bar app and pair once per server session using the session code printed in Terminal. The helper stores only its session cookie in the macOS Keychain.

Click **Start local ambient mode** when you are ready. macOS asks for microphone, camera, and Speech Recognition permission. The menu bar shows a live AURA status, macOS shows microphone/camera privacy indicators, and the app always has a visible Pause button. Recognition refuses to start unless Apple reports on-device English recognition support; it sets `requiresOnDeviceRecognition`, and never uploads raw audio. The Vision framework classifies one camera frame per second locally; no image or audio recording is written. AURA sends only a recognized phrase that says “AURA”, asks a direct question, or explicitly says “I need help/support”, “I feel overwhelmed/panicked”, “I feel unsafe”, or similar listed support phrases. It does not infer distress from voice tone or facial expressions. Passive speech and camera labels remain in short-lived memory; only a triggered transcript and its brief camera context are saved through the existing companion store. AURA replies with the locally configured companion brain and speaks through macOS voices. If Sonnet is not configured on this Mac, the existing local reaction fallback responds.

Pause cancels startup and pending replies, stops the microphone, queues camera shutdown, and stops recognition and speech. Late callbacks from a previous session cannot reactivate capture or speak a reply. Native UI state is isolated to the main actor, and camera setup/start/stop share a serial capture queue. Closing the browser leaves the helper listening; quitting the helper stops it. Sleep pauses capture; AURA resumes after wake while the app stays open. Keep the terminal launcher running for the local companion service. To monitor after reboot, add the server launcher and AURA Companion to your Mac Login Items; this preview does not install a privileged background daemon. A signed and notarized distribution is a later step.

For the quickest local start, keep `npm start` running in Terminal. Open the native app from `aura-app/release/AURA Companion.app`, paste the current session code, then start ambient mode. Use your existing personal database with `AURA_DB_PATH` before starting the server if it is stored elsewhere.

## Raspberry Pi target

The web companion now has a full-screen face mode at `http://127.0.0.1:8790/?kiosk=1`, with visible microphone and spoken-reply controls after login. Recognized speech is an editable draft by default, including in kiosk mode. The kiosk’s “Send recognized speech automatically” checkbox explicitly opts into immediate storage and configured-provider processing; it resets on reload. The current ambient camera/microphone helper is macOS-only, so this is not yet a Pi camera-and-sensors release. See [`../docs/raspberry_pi.md`](../docs/raspberry_pi.md) for the target hardware and the remaining Pi integration work. Do not treat the current browser microphone as private on-device recognition: browser speech recognition may use a network service.

The companion brain can also use OpenAI's Responses API by setting `AURA_BRAIN_PROVIDER=openai`, `OPENAI_API_KEY`, and optionally `OPENAI_MODEL` in the server environment. The key stays in the Python server process and is never sent to the browser. This does not yet move memory to a cloud database; the existing companion store remains SQLite.

## Optional automation — disabled by default

The SDK bridge follows the Jarvis architecture but intentionally does **not** load `~/.claude.json`, project settings, filesystem tools, shell tools, or the old broad tool-name heuristics. Native SDK tools are disabled (`tools: []`). Use Claude Code installed and authenticated locally for this optional mode; this authentication is separate from the companion's API key.

Create ignored `aura-app/mcp.local.json` using MCP servers you trust:

```json
{
  "servers": {
    "my_service": { "command": "/absolute/path/to/audited-server", "args": [] }
  },
  "allowedTools": ["mcp__my_service__exact_tool_name"]
}
```

Then launch with `AURA_ENABLE_ACTIONS=1 npm start`. This explicitly allows the configured server programs to start when a task runs. MCP server startup itself executes local code; install and inspect those programs yourself. The app does not install MCP servers or auto-discover them.

Use the **Actions** tab to submit a task. Every allowed tool call displays its exact name and arguments and requires a fresh approve/deny click. Unknown tools and all built-in filesystem/shell tools remain denied. Approval expires after 60 seconds, cannot be replayed, and never applies to a different invocation. Tasks expire after two minutes and can be cancelled; cancellation permanently closes that task’s approval gate, including requests arriving late. Each new task gets a new gate; cancellation cannot undo a tool action that already completed. Read operations also require approval: tool names are not reliable evidence of safety. External MCP servers remain responsible for their own side effects; this is not an OS sandbox. Action tasks use an AURA system prompt but **do not receive personal SQLite memories** or write task output into companion history in this preview.

## Security boundary

The Node server binds only `127.0.0.1`. Exact Host validation blocks DNS rebinding; state-changing API requests require the matching Origin, and any supplied foreign Origin is rejected. A random per-launch code exchanges for an HttpOnly, SameSite=Strict cookie. Provider secrets and the login code are never stored in localStorage. The cookie is intentionally local HTTP, suitable only for the loopback bind; do not expose this server through a reverse proxy or change it to a network bind. There is no arbitrary file/media proxy or model-generated HTML. React escapes messages; CSP blocks frames and remote scripts. The Python worker has no HTTP port and accepts only private stdin/stdout messages. Authentication protects memory reads as well as writes. This local app trusts software already running as your OS user.

## Development and verification

```sh
npm run build       # TypeScript plus production bundle
npm run lint
npm test            # real loopback server + temp SQLite, auth, origin/host, persistence, approvals
npx playwright install chromium
npm run test:e2e    # browser conversation, feedback, memory and kiosk consent
npm run test:native # macOS: capture lifecycle cancellation/restart checks without hardware
python3 -m unittest discover -s tests -p 'test_*.py'
npm run bundle      # tracked source + production UI, no keys or memory
```

For live UI development, run `AURA_DEV=1 npm start` and `npm run dev` in separate terminals, then open `http://127.0.0.1:5173`. Development admits exactly that extra origin; production does not. Run the build first for the server integration test. GitHub Actions repeats build, lint, tests, and artifact creation on macOS and Linux.

Tests use disposable databases and mocked Claude responses; they do not charge your API account. Live Claude, ElevenLabs, and user-specific MCP tools require your actual credentials and configuration and are not proven by these tests. The earlier Windows/sensor scripts are untouched and not launched by the new app. Emergency dispatch, iPhone control and task history remain outside this preview.

## Source and attribution

Upstream: [adewaskar/jarvis](https://github.com/adewaskar/jarvis), inspected at commit `1c4016afdf86f7043efc6882ceffef84ad0d8783`.

Reused/adapted MIT code: `src/scene/Core.tsx`, `src/scene/Particles.tsx`, `src/lib/audio.ts`, `src/lib/vad.ts`, and the Agent SDK bridge pattern. See [LICENSE-JARVIS](LICENSE-JARVIS) for the original copyright and permission notice. New AURA glue and UI are MIT-licensed under [LICENSE](LICENSE). The existing repository's original code remains under its original terms. No upstream `public/audio` or other demo media was copied.

Architecture: browser → authenticated loopback Node bridge → private Python worker → existing AURA engine / SQLite / server-side Claude API. Optional actions use a separate, bounded Claude Agent SDK session with explicit MCP configuration and approval hooks.

Memory worker failures fail closed: exit, missing Python, and a 45-second response deadline reject requests. Restart the app after checking configuration; failed writes are never automatically retried because SQLite may already have committed them.

## Readiness and live acceptance

Open **Setup** after pairing. Its checks read configuration and confirm the memory
worker responds; they never call a provider, start an MCP server, or turn on a
microphone/camera. “Configured” is not a successful live test. Missing settings
list only variable names, never key values. Restart after changing configuration.
The selected model now matches the selected brain, including OpenAI and Ollama.

Before declaring the single-device companion ready, record these live results:

1. Configure the intended brain privately and send a non-greeting message. Check
   that the response is labeled with the intended provider, not local fallback.
2. Opt into voice; check recognition, draft review, spoken output and Stop.
3. Pair the native helper and explicitly start ambient mode. Check permission
   denial, use **Open Privacy Settings** to review denied Speech Recognition,
   microphone or camera access, Cancel startup, Pause during a pending reply,
   restart and sleep/wake.
4. Confirm camera/microphone indicators stop after Pause, and no old reply speaks.
5. If actions are needed, configure a trusted MCP server and a harmless test tool.
   Verify Deny, approval expiry, Cancel and a separately approved successful call.

Physical capture, model credentials and MCP authentication cannot be proven by
mock tests. Keep results scoped to the actual device and configuration tested.
See the [project roadmap](../docs/ROADMAP.md) for remaining phase gates.

### Memory controls

In **Memory**, correct a saved fact or forget it with a confirmation. A correction
is marked as user-provided. Forgetting an inferred fact also prevents AURA from
automatically saving that same fact key again. Your original chat messages stay in
history and may still inform recent replies; this feature removes a saved summary,
not the source messages. **Download all my AURA data** exports your profile,
conversations, facts, observations and other records stored for your account as a
JSON file. The export is generated locally, requires the current session, and is
not sent to a cloud service. The Memory view also shows saved routines and recent
observations, including any room labels attached to ambient requests.

Check-ins are separate from voice listening. They are off unless you opt in under
**Setup**, wait for the selected idle interval, respect quiet hours in the AURA
device's local time, and appear only while the web companion is open. They use a
short local message and do not start Claude, MCP tools, camera, or microphone.
