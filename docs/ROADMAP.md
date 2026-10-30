# AURA delivery roadmap

AURA is currently a development preview, not a finished always-present companion.
The confirmed repository is https://github.com/sujanmj/aura-companion.

## Long-term companion target

The intended product is a present, personal companion: it can notice useful
context throughout the day, remember user-approved people, events and routines,
and speak naturally without requiring a wake phrase for every exchange. It may
help find recently seen objects, offer timely routine and medication reminders,
and contribute to a shared conversation when invited. This is an aspiration;
these capabilities are not implemented as a complete system today. Software milestones now proceed across Phases 2–12; Phase 2 hardware
acceptance remains open and is not a prerequisite for independent software work.

Always-present sensing must be distinguishable from recording. Audio and video
are processed only while the user has enabled the relevant sensor, with visible
status and an immediate pause control. Raw media is not retained by default;
local, user-reviewable summaries are the memory. Face/name memory is limited to
people the user enrolls with appropriate consent. A person AURA cannot identify
may trigger a configured visitor notice, but AURA must not invent their name or
identity. Activity and object observations carry uncertainty and can be corrected
or forgotten. Proactive speech respects quiet hours, interruption preferences,
and confidence thresholds. Online factual grounding is opt-in, must distinguish
verified information from uncertainty, and must not turn ambient conversation
into unrestricted external tool actions. Health signals and medication schedules
are separately opt-in; reminders are not proof that a dose was taken or a
substitute for professional care.

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

Status: software reliability milestones implemented; hardware acceptance remains open.

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
- Implemented: during an explicitly started Mac ambient session, Apple Vision
  scene labels and a human-presence signal can be saved as derived summaries in
  the existing SQLite observation memory. The authenticated loopback endpoint
  accepts bounded labels only, stores no image/audio, and limits writes to one
  changed summary per minute. The Memory view already supports review/deletion.
  Unit and authenticated API tests pass, and the native helper builds. Hardware
  acceptance of this new persistence path remains outstanding.
- Implemented: the paired Mac helper checks the existing local check-in endpoint
  every five minutes while the AURA app is running, including when ambient
  camera and microphone capture are paused. Explicit reminder enables and
  check-in preferences remain the gates; quiet hours and daily delivery limits
  are enforced by local SQLite. Replies use local speech and do not invoke
  Claude or MCP actions. Local app-build, native-test, API, and Python checks
  pass; macOS and Ubuntu push/PR CI passed in runs 39613730506 and 39613739454.
  Live speaker acceptance remains outstanding.
- Implemented with CI: companion replies can use up to three relevant on-device
  scene summaries only when they are no more than ten minutes old. Visual
  estimates are labeled uncertain and cannot confirm identity, activity, or an
  exact object location. Automated memory/prompt tests and cross-platform CI
  pass; end-to-end camera acceptance remains outstanding.
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
- Implemented for Mac preview: an off-by-default setting can prevent idle
  system and display sleep while ambient mode is live. Pause, stop, and quit
  release the sleep assertion; password and automatic-lock settings are not
  changed. The local app build and native lifecycle tests pass, and push CI
  passed on macOS and Ubuntu in run 39617638169. Pull-request CI, energy-use,
  and sleep/wake acceptance remain outstanding.
- Implemented for Mac preview: camera room perception can be disabled in the
  native helper before starting a session. The saved preference defaults to the
  prior camera-enabled behavior for existing installs; when disabled, startup
  requests no camera permission and starts local speech alone, with no scene or
  person summaries. The control is locked during capture so changes apply only
  after Pause. Native tests verify the saved preference's default and opt-out.
  Local native build and lifecycle tests pass; commit `3127c7e` passed macOS,
  Windows and Ubuntu push CI in
  [41006853364](https://github.com/sujanmj/aura-companion/actions/runs/41006853364)
  and pull-request CI in
  [41006857996](https://github.com/sujanmj/aura-companion/actions/runs/41006857996).
  Both runs uploaded three preview archives. Physical camera permission,
  pause and room-observation acceptance remain outstanding.
- Implemented for Mac preview: a separate saved preference disables periodic
  camera-summary submissions to local Memory while retaining volatile scene
  labels for direct requests. The UI explains that distinction and directs the
  user to disable room perception to remove visual context entirely. Native
  tests cover its default and opt-out; local native build and lifecycle tests
  pass. Commit `17b981f` passed macOS, Windows and Ubuntu push CI in
  [41008831382](https://github.com/sujanmj/aura-companion/actions/runs/41008831382)
  and pull-request CI in
  [41008838161](https://github.com/sujanmj/aura-companion/actions/runs/41008838161)
  after the Windows job was rerun successfully. Both runs uploaded all three
  preview archives. Physical camera and persistent-memory acceptance remain
  outstanding.
- Implemented for Mac preview: a third saved camera preference excludes recent
  scene labels and person presence from ambient requests without stopping local
  camera analysis or changing the separate Memory-storage setting. A bounded
  reply-context helper and native tests verify opt-out and the five-label limit.
  Local native build and lifecycle tests pass; CI and physical acceptance
  remain pending.
- Implemented for Mac preview: a session-only private-reply choice routes new
  addressed phrases through AURA's existing unsaved private-turn endpoint. The
  request omits saved-memory access and camera context and does not enter saved
  chat history. Pause, sleep or closing the window clears the choice. Native
  tests verify private routing, payload exclusions and that private mode cannot
  be enabled outside an active session and resets on stop; the existing API
  suite covers unsaved private turns. Local verification passes: 28 Node tests,
  94 Python tests, lint, native lifecycle/speech tests and an ad-hoc Mac app build.
  CI passed on macOS, Windows and Ubuntu for the exact same source tree in push
  run [41010752411](https://github.com/sujanmj/aura-companion/actions/runs/41010752411)
  and pull-request run [41010757482](https://github.com/sujanmj/aura-companion/actions/runs/41010757482).
  Both runs uploaded all three preview archives. The upload correction commit
  `0cb28f8` has an identical tree to the locally tested feature commit. Provider
  retention and live provider behavior remain outside this verification.
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
- Fixed after Mac restart testing (2026-10-20): AVAudioEngine setup, start,
  tap removal, and stop now run on a dedicated serial queue. Startup awaits the
  audio result without blocking the main actor, so the UI and startup watchdog
  can still respond if CoreAudio stalls during a device change. The rebuilt Mac
  helper reached LIVE after permission recovery and completed two consecutive
  Pause/start cycles; final Pause confirmed both sensors off. A multi-hour soak
  of this rebuilt audio-queue version remains to be run.
- Fixed after a stalled pairing test (2026-10-20): Keychain reads, saves, and
  deletes return to the UI after an eight-second bound. Each request runs
  independently so a stalled system call cannot starve later UI operations.
  On this Mac, `SecItemCopyMatching` and `SecItemUpdate` have both stalled inside
  macOS for AURA's test item. Removing that item in Keychain Access restored one
  successful pairing, but the next restart and update stalled again. The
  app reports the uncertainty and offers an explicit in-memory session option;
  this option and reliable saved-pairing recovery still need acceptance. After
  the app was rebuilt with Hardened Runtime and capture entitlements (2026-10-20),
  one isolated test saved a pairing, quit and relaunched AURA, recovered the
  pairing from Keychain, cleared it successfully, and verified that the item was
  absent in Keychain Access. This is one successful cycle, not proof of repeated
  Keychain reliability; earlier stalls remain part of the evidence.
- Fixed: ambient startup now names each permission/device setup stage and has a
  60-second watchdog. If a macOS permission or capture callback stalls, AURA
  safely pauses instead of leaving the user on an indefinite startup state;
  manual Cancel remains available and late callbacks are rejected by the
  session generation. Native tests cover watchdog expiry and cancellation.
- Strengthened: native startup tests now hold a permission callback suspended,
  drive the same watchdog-expiry gate used by the Mac helper, verify the capture
  lifecycle returns to Paused, then release the late callback and verify it
  cannot reactivate capture. This validates the timeout recovery logic without
  claiming a real macOS permission prompt was stalled.
- Improved: watchdog timeouts now identify whether Speech Recognition,
  microphone, camera, or a later startup stage stalled. Permission-stage
  timeouts offer a direct link to the matching Privacy & Security pane.
- Mac hardware acceptance (2026-10-20): paired the rebuilt app to an isolated,
  temporary SQLite database; confirmed local camera classification, on-device
  recognition through the Mac microphone, an ambient reply, and Pause clearing
  the live mic/camera indicators. The app invoked its speech output path; this
  check did not measure acoustic playback. Temporary pairing and test database
  were cleared.
- Latest unlocked-Mac check (2026-10-20): paired the rebuilt helper to an
  isolated temporary SQLite database. Startup first appeared stalled, then
  completed: the helper visibly reached LIVE with microphone and camera on and
  a local Vision classification. Pause returned it to PAUSED with both sensors
  off. No ambient phrase/reply or acoustic speaker output was tested. The test
  pairing, temporary service, and database were cleared. Sleep/wake and
  acoustic feedback remain unverified.
- Permission recovery check (2026-10-20): separately disabled AURA's camera,
  microphone, and Speech Recognition permissions in System Settings. Start
  reported the matching denied permission in each case and showed the direct
  Open Privacy Settings action. Restored all permissions, relaunched, confirmed
  LIVE with microphone and camera on, then paused and verified both off. The
  temporary pairing, service, and database were cleared. This verifies denied
  permission recovery for all three macOS access types; phrase recognition and
  acoustic reply are not established by this check.
- Local voice-loop check (2026-10-20): with MCP actions disabled, the selected
  brain provider reporting local-only, cloud sync explicitly disabled, and an
  isolated SQLite database, played a synthetic test request through the Mac
  speakers while ambient mode was live. On-device recognition transcribed the
  request with a minor wording error; the local AURA fallback produced a re