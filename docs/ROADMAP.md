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
- Implemented: denied macOS Speech Recognition, microphone, and camera
  permissions offer a direct Privacy Settings button for recovery.
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
- Fixed: AURA's spoken reply temporarily suppresses microphone transcription and
  cancels any in-flight recognition, then resumes after a quiet grace period.
  Stale speech-completion callbacks cannot reopen the microphone after a newer
  utterance or Pause; native tests cover those generations. Acoustic feedback
  still needs confirmation on the unlocked Mac.
- Fixed: closing the AURA companion window or quitting the app pauses ambient
  microphone and camera capture. Reopening AURA from the Dock restores the
  window without restarting capture; the user must opt in again.
- Fixed: pairing reports success only after the session cookie is saved to
  macOS Keychain. Credential rotation updates an existing item before creating
  one, so a save failure does not delete a previously stored credential.
  Native tests cover update, add, access-denied, and add-failure results without
  touching the real Keychain.
- Fixed: startup validation of a stored pairing cannot clear a newer explicit
  pairing, and duplicate pairing attempts are serialized.
- Fixed: only an explicit 401 clears a stored pairing; temporary network or
  service errors keep the Keychain cookie and offer a retry action.
- Clarified: the macOS Speech Recognition permission prompt distinguishes raw
  audio (not saved) from triggered transcripts that may enter local SQLite
  memory.
- Fixed: if macOS cannot open the requested Privacy Settings pane, AURA leaves
  manual System Settings directions for the denied permission.
- Fixed: camera interruption and runtime-error notifications now pause the
  complete ambient session and report recovery guidance instead of leaving a
  stale active indicator while microphone capture continues.
- Fixed: an AVAudioEngine input/output configuration change now pauses the
  complete ambient session. The notification is handled asynchronously, and
  generation checks discard events from previous sessions.
- Mac hardware acceptance (2026-10-20): paired the rebuilt app to an isolated,
  temporary SQLite database; confirmed local camera classification, on-device
  recognition through the Mac microphone, an ambient reply, and Pause clearing
  the live mic/camera indicators. The app invoked its speech output path; this
  check did not measure acoustic playback. Temporary pairing and test database
  were cleared.
- Latest unlocked-Mac check (2026-10-20): paired the rebuilt helper to a new
  disposable SQLite database. macOS already showed AURA microphone and camera
  permissions enabled. Starting ambient mode caused the native window to become
  unavailable to UI inspection, so active capture, indicators, shutdown/restart,
  permission-denial recovery, sleep/wake and acoustic feedback could not be
  verified in this pass. The helper and temporary server were stopped and the
  test database was removed. This is a failed/incomplete acceptance attempt,
  not a pass.
- Remaining: repeat and record camera startup/shutdown/restart, permission
  recovery, sleep/wake, startup failure recovery and acoustic feedback on Mac.

Exit: automated failure-path tests and CI pass, with real-device acceptance recorded
separately. Missing hardware access must remain an explicit unresolved gate.

## Phase 3 — Usable companion on one device

Status: partial components exist; acceptance not complete.

- Implemented: diagnose configuration and service readiness without exposing secrets.
- Implemented: Setup includes a guided first-device acceptance checklist for
  conversation/provider, reviewed voice input, spoken output/Stop, memory
  continuity, Mac ambient mode and optional MCP approvals. Checklist marks are
  manual notes stored in that browser only; they do not run tests or claim that
  a provider, microphone, speaker, camera or tool worked. Browser end-to-end
  coverage checks persistence and clearing of those notes.
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
- Implemented: users can confirm deletion of their conversation messages and
  replies while retaining their saved facts, routines, and observations.
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
- Fixed: simple explicit negation such as “I am not anxious” no longer creates
  or reuses anxiety and low-mood labels from the current turn.
- Implemented: consent-based local check-ins default off, wait for a saved idle
  interval, honor quiet hours, and only appear while the web companion is open.
- Remaining: broader native controls and lifecycle acceptance.
- Handle interruptions, uncertainty and emotional cues without claiming mind-reading.

Exit: behavior and privacy tests pass; preferences and consent persist correctly.

## Phase 5 — Raspberry Pi and multi-room presence

Status: security hardening is progressing; kiosk UI, event API and simulators exist; real node integration remains.

- Pi node runtime and local speech options with resource limits.
- Implemented: sensor and dashboard data routes fail closed unless a shared
  token of at least 32 characters is configured. Token checks use constant-time
  comparison, unauthenticated requests cannot update the service heartbeat, and
  the Pi simulator refuses to send without a valid configured token or print it.
  Automated API tests cover missing, weak, incorrect and valid tokens and ensure
  unauthenticated event data is not stored.
- Implemented: sensor events accept a client UUID, and the database enforces
  uniqueness by user, source and UUID. The Pi simulator retries transient network
  and server errors using the same UUID; duplicate requests return the original
  event without repeating observations or safety processing. Device-specific
  enrollment now issues separate random node credentials stored as hashes;
  nodes can send scoped events and heartbeats, be revoked independently, and
  appear online for 90 seconds after their last contact. Credential enrollment
  and revocation, room/source binding, and status are API-tested. A production Pi
  background service and room-to-room conversation handoff remain.
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
