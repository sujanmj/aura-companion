# AURA delivery roadmap

AURA is currently a development preview, not a finished always-present companion.
The confirmed repository is https://github.com/sujanmj/aura-companion.

For every milestone: implement, run relevant automated tests, fix failures, commit,
push, and verify CI before continuing. CI success proves only the checks it ran.
Live provider, hardware, and multi-device behavior require separate acceptance
results. Never describe mocked speech/provider tests as live verification.

## Phase 1 — Preserve AURA and integrate its interface

Status: complete for the development preview.

- Preserve the existing SQLite schema, personality, feedback and Claude provider.
- Add the AURA interface and opt-in voice using appropriately attributed MIT code.
- Keep external actions disabled by default and approve individual MCP invocations.
- Verify authenticated conversation, persistence, backup, feedback and UI flows.

Evidence: integration branch through b2d1aa4; 18 local automated tests and Linux /
macOS CI run 39288627959 passed. Preview artifacts exist. This is not a stable
hardware release, and the branch has not yet been merged into main.

## Phase 2 — Reliable single-device runtime

Status: in progress; this is the current phase.

- Completed: closed approval gates after cancellation; enforce approval deadlines;
  explicit kiosk auto-send consent; fail closed when the memory worker dies/stalls.
- Completed with CI: native startup, Pause, camera cleanup and delayed
  responses obey a single capture-session lifecycle; prevent speaking after Pause.
  Camera setup always closes its configuration transaction, even on failure.
  Evidence: 89a3894, Linux/macOS run 39290007322; native lifecycle tests include
  1,000 cancel/restart cycles. This is automated evidence, not a hardware test.
- Implemented: authenticated Setup/readiness diagnostics distinguish missing
  configuration, local fallback and configured-but-unverified providers.
- Fixed: copy audio tap buffers before asynchronous recognition and isolate
  delayed errors with per-utterance generations, so a stale callback cannot
  reset a newer phrase. Native tests cover stale callbacks.
- Fixed: Pause distinguishes camera shutdown from camera-off state, waits for
  the serialized session stop callback, and blocks restart until teardown ends.
  Stop completion is generation-guarded so it cannot overwrite a newer session.
- Fixed: sleep/wake resume now handles both notification orders; it waits for
  camera teardown if wake arrives first and never restarts while still asleep.
  Manual Pause cancels a pending automatic resume. Hardware sleep/wake remains
  unverified.
- Mac hardware acceptance (2026-10-20): paired the rebuilt app to an isolated,
  temporary SQLite database; confirmed local camera classification, on-device
  recognition through the Mac microphone, an ambient reply, and Pause clearing
  the live mic/camera indicators. The app invoked its speech output path; this
  check did not measure acoustic playback. Temporary pairing and test database
  were cleared. Sleep/wake and startup-failure recovery still need acceptance.
- Remaining: verify camera shutdown/restart, permission-denial recovery and
  sleep/wake behavior on hardware. The newly rebuilt stop acknowledgement has
  automated coverage but awaits a repeat Mac check because the Mac is locked.

Exit: automated failure-path tests and CI pass, with real-device acceptance recorded
separately. Missing hardware access must remain an explicit unresolved gate.

## Phase 3 — Usable companion on one device

Status: partial components exist; acceptance not complete.

- Implemented: diagnose configuration and service readiness without exposing secrets.
- Verify real voice conversations, interruption, memory continuity and opt-in tools.
- Exercise real Claude/MCP and optional voice-provider paths when configured.
- Provide a repeatable onboarding and acceptance procedure.

Exit: a configured device completes the documented live acceptance flow. Do not
invent credentials, silently enable tools, or substitute mock results for it.

## Phase 4 — Companion behavior and user control

Status: foundations exist in the original reaction/memory engines.

- Review, correct, export and forget remembered information deliberately.
- Implemented: authenticated JSON export contains the selected user's profile and
  records across conversations, saved and forgotten facts, feedback, observations,
  routines, device/safety records and related timelines. Cross-user scoping is
  tested; the download stays on the local AURA service.
- Implemented: Memory view now reviews saved routines and the latest 20
  observations alongside correctable/forgettable facts.
- Implemented: routines can be corrected or explicitly forgotten; a forgotten
  routine is suppressed from automatic conversation extraction until the user
  explicitly asks AURA to remember it again.
- Implemented: ambient observations can be deleted individually from the
  authenticated Memory view; deletion is scoped to the current user's SQLite
  records and removes that observation from future exports.
- Fixed: emotional cues are inferred from the current user turn instead of
  accumulating across unrelated older messages. Quiet or still camera context
  no longer counts as evidence that someone is sad or lonely.
- Implemented: consent-based local check-ins default off, wait for a saved idle
  interval, honor quiet hours, and only appear while the web companion is open.
- Remaining: broader native controls and lifecycle acceptance.
- Handle interruptions, uncertainty and emotional cues without claiming mind-reading.

Exit: behavior and privacy tests pass; preferences and consent persist correctly.

## Phase 5 — Raspberry Pi and multi-room presence

Status: kiosk UI, event API and simulators exist; real node integration remains.

- Pi node runtime and local speech options with resource limits.
- Authenticated device enrollment, reconnect/offline behavior and node health.
- Conversation handoff without duplicate replies or accidental cross-user memory.
- Real camera/microphone and GPIO sensor acceptance on target hardware.

Exit: a real multi-node deployment passes handoff, reconnection and privacy tests.

## Phase 6 — Safety validation and release packaging

Status: simulated safety workflows exist; production validation remains.

- Validate sensor errors, false alarms, confirmation timeouts and recovery.
- External alerts remain explicitly authorized; no unverified emergency guarantees.
- Package supported platforms, verify clean installation and upgrades, preserve
  memory, and sign/notarize distributions when signing credentials are available.
- Publish only builds whose stated scope has passed its release gates.

Exit: release checklist and evidence identify tested platforms, known limitations,
hardware coverage and rollback instructions. A preview is never labeled production
ready solely because it compiles or passes CI.
