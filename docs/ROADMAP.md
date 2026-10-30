Warning: truncated output (original token count: 25461)
Total output lines: 1541

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
  request with a minor wording error; the local AURA fallback produced a reply,
  native speech output completed, and the helper returned to Listening locally.
  Pause turned off both sensors; pairing, service, database and generated audio
  were cleared. This verifies the local request-to-reply and synthesizer path,
  not acoustic loudness/quality or live Claude behavior.
- Restart-cycle check (2026-10-20): ran five successive live Mac capture
  cycles. Every cycle reached LIVE with microphone and camera on, then returned
  to PAUSED with both off. The temporary pairing, service, and database were
  cleared. This complements the 1,000-cycle hardware-free lifecycle test; it is
  not a long-run or sleep/wake test.
- Permission-prompt stall check (2026-10-20): after resetting only AURA's
  Speech Recognition permission, the rebuilt app remained at "Checking Speech
  Recognition permission…" without showing a macOS prompt or adding AURA to
  that System Settings list. The 60-second watchdog safely returned it to
  PAUSED with microphone and camera off. Pairing and isolated test data were
  cleared. A follow-up improves the timeout message and adds a link to the
  Speech Recognition privacy pane; automated tests and a local app build pass,
  but the permission prompt path still needs investigation and successful
  clean-install recovery is not verified.
- Restored-access follow-up (2026-10-20): opened the linked Speech Recognition
  pane, confirmed AURA Companion was enabled, then relaunched the helper. It
  passed Speech Recognition, microphone, and camera checks and reached LIVE;
  Pause turned both sensors off. The temporary pairing, service, and database
  were cleared. This verifies settings-based permission restoration and a
  successful restart, but not an automatic fresh-install Allow dialog.
- Acoustic feedback spot check (2026-10-20): with an isolated database, actions
  disabled, and local-only brain provider, played a synthetic direct request
  through the Mac's built-in speakers while the helper was listening. AURA
  recognized it, returned a local reply, finished native speech output, and
  resumed listening; no echo-triggered reply was observed during this check.
  Pause turned both sensors off and the temporary pairing, service, database,
  and audio file were cleared. This does not measure calibrated loudness or
  prove feedback behavior across rooms and volumes.
- Idle soak spot check (2026-10-20): left the rebuilt helper in LIVE ambient
  mode for five minutes with the isolated local-only service. It remained LIVE
  with microphone and camera on, without a restart or startup timeout. Pause
  turned both sensors off and the temporary pairing, service, and database
  were cleared. This is a short soak only; the long-run stability gate remains.
- Extended idle soak (2026-10-20): ran the helper LIVE for 30 minutes with an
  isolated local-only service and external actions disabled. The UI remained
  LIVE with microphone and camera on; local scene classifications continued
  updating, and Listening locally remained the status without a restart or
  startup timeout. Pause turned both sensors off. The temporary pairing,
  service, and database were cleared. Multi-hour stability is still unverified.
- One-hour Mac soak (2026-10-20): with a fresh isolated local-only service and
  external actions disabled, the helper remained LIVE for one hour with
  microphone and camera on. The UI continued to report Listening locally and
  local scene classifications updated throughout sampled checks. No restart,
  timeout, or sensor drop was observed; Pause turned both sensors off. The
  temporary pairing, service, and database were cleared. This is an hour-long
  stability check, not multi-hour or sleep/wake acceptance.
- Interrupted Mac soak (2026-10-20): an attempted longer run reached about
  34 minutes before macOS reported an audio configuration change. AURA safely
  paused and turned off both sensors. The first restart stalled during local
  microphone startup; its Cancel control was activated through macOS
  accessibility, and the old helper produced an EXC_BAD_ACCESS report in
  SwiftUI's accessibility button dispatch. This was preserved as failure
  evidence and prompted moving AVAudioEngine work off the main actor.
- Two-hour Mac soak (2026-10-20, pre audio-queue fix): after restarting the
  helper, it remained LIVE for 2 hours 4 seconds with microphone and camera on.
  Read-only UI samples showed Listening locally and changing local scene labels;
  two-minute process/service/database samples stayed healthy. External actions
  and cloud sync were disabled, and the isolated SQLite database recorded no
  conversation, observation, or safety rows. Pause turned both sensors off,
  pairing and service were cleared, and test database files were deleted. This
  validates the pre-fix build only; the rebuilt audio-queue version still needs
  its own multi-hour soak.
- Rebuilt permission recovery check (2026-10-20): the first ambient start
  reached the 60-second Speech Recognition watchdog, which returned the helper
  to PAUSED with sensors off. System Settings showed AURA Companion already
  enabled for Speech Recognition. A subsequent retry reached LIVE; two
  additional Pause/start cycles also returned to LIVE. Final Pause turned both
  sensors off, and the temporary pairing, service, and database were cleared.
  This does not verify a fresh-install Allow prompt or sleep/wake.
- Fresh-install permission check (2026-10-20): after an explicitly approved
  Speech Recognition permission reset, the macOS settings pane no longer
  listed AURA and no Allow prompt appeared. AURA's requestAuthorization callback
  remained pending until the 60-second watchdog safely returned it to PAUSED;
  no microphone or camera capture began. This clean-install prompt blocker
  remains unresolved. Existing permission recovery succeeded before the reset,
  but the grant could not be restored through the missing prompt in this run.
- Speech privacy update (2026-10-20): when built with the macOS 27 / Swift 6.4
  SDK and run on macOS 27 or later, ambient transcription uses Apple's
  `SpeechAnalyzer` and `SpeechTranscriber` with supported on-device English
  assets. Older build SDKs and older systems retain the explicitly on-device-
  only Speech framework path. The modern build compiled and reached
  LIVE with local camera classifications, but a synthetic spoken request
  produced no visible speech-recognition status or conversation row. A later
  fresh launch timed out while checking microphone permission even though
  System Settings listed AURA as allowed, and no Allow prompt appeared. The new
  on-device speech-to-reply path and stable signed permission identity remain
  unverified; the earlier live voice-loop result applies to the older path.
- On-device analyzer smoke test (2026-10-20): a locally generated speech clip
  fed through Apple's SpeechAnalyzer, SpeechTranscriber, and AURA's audio
  converter produced finalized English transcription segments before the input
  stream closed. Temporary clip and harness were removed. This verifies the
  on-device model and analyzer path, not AVAudioEngine delivery or an AURA reply.
- macOS CI compatibility fix (2026-10-20): run 39465895378 exposed that the
  macOS 26 SDK does not include Apple's `AnalyzerInputConverter`. The modern
  SpeechAnalyzer implementation is now compile-gated to Swift 6.4+ and macOS 27
  runtime; older SDKs compile the on-device-only fallback. The local macOS 27
  build and app tests pass; macOS 26 and Ubuntu CI passed in run 39466315415.
- Microphone permission check (2026-10-20): AURA now uses Apple's
  `AVAudioApplication` recording-permission API on macOS 14+ and keeps the
  capture-device permission path for older macOS and camera access. On this
  Mac, the microphone switch is on in Privacy Settings, but the app reports
  permission as undetermined; its permission request produced no prompt and
  did not return before the 60-second startup watchdog. No capture began. The
…13461 tokens truncated… documented sensor API test client now
use a shared direct transport
that ignores machine-wide proxies and refuses redirects. Remote HTTP URLs are
rejected before administrator credentials are sent; remote hubs require HTTPS.
Focused tests verify no-proxy/redirect behavior, enrollment/status/test-client
request scope, and existing retry/claim behavior. Local verification passes:
94 app Python tests and 45 focused room, invitation, heartbeat, service,
admin-client and sensor-transport tests. The admin-client suite is included in CI.
Commit `29061f7` passed macOS, Windows and Ubuntu push CI in
[40964038358](https://github.com/sujanmj/aura-companion/actions/runs/40964038358)
and PR CI
[40964044684](https://github.com/sujanmj/aura-companion/actions/runs/40964044684);
both runs uploaded preview archives for all three platforms. This is software
transport coverage only; no Pi installation or network deployment is claimed.

The documented sensor API test client now uses the same direct transport and
refuses remote HTTP before sending its administrator token. Focused local tests
and the 94 app Python tests pass. Commit `2de8276` passed macOS, Windows and
Ubuntu push CI in
[40966173161](https://github.com/sujanmj/aura-companion/actions/runs/40966173161)
and PR CI
[40966180392](https://github.com/sujanmj/aura-companion/actions/runs/40966180392);
both runs uploaded all three preview archives. This still does not establish a
deployed hub or physical Pi behavior.

The sensor API authentication and event-status probes now use the same direct
transport as the documented client; all reject remote HTTP before sending
credentials and return a failing process status for that unsafe configuration.
Ten focused admin-client tests, the 49-test room/transport group,
and all 94 app Python tests pass locally. Commit `b7c72ff` passed macOS,
Windows and Ubuntu push CI in
[40967410539](https://github.com/sujanmj/aura-companion/actions/runs/40967410539)
and PR CI
[40967416698](https://github.com/sujanmj/aura-companion/actions/runs/40967416698);
both runs uploaded all three preview archives. This remains a client transport
check and does not validate a deployed hub or Pi device.

Follow-up commit `5120a4d` makes the three probes exit non-zero when their hub
URL violates the HTTPS/loopback policy. Push CI
[40968379151](https://github.com/sujanmj/aura-companion/actions/runs/40968379151)
and PR CI
[40968385143](https://github.com/sujanmj/aura-companion/actions/runs/40968385143)
passed on macOS, Windows and Ubuntu and uploaded all three preview archives.

The incident, confirmation, dashboard and runtime-heartbeat probes now use the
same no-proxy, no-redirect transport and reject remote HTTP before sending the
admin token. The Windows loopback integration test now explicitly bypasses
system proxies, avoiding an intermittent connection-abort while validating
unauthenticated routes. Twelve focused admin-client tests, the 51-test
room/transport group and all 94 app Python tests pass locally. Commit `79b8f40`
passed macOS, Windows and Ubuntu push CI in
[40970180323](https://github.com/sujanmj/aura-companion/actions/runs/40970180323)
and PR CI
[40970187073](https://github.com/sujanmj/aura-companion/actions/runs/40970187073);
both runs uploaded all three preview archives. This client-side check does not
validate a deployed hub or Pi device.

## 2026-10-30 continuation — lazy holographic scene loading (Phase 2)

The React shell now lazy-loads its Three.js scene behind the existing static orb
fallback, allowing the companion controls and privacy status to render without
waiting for the scene chunk. Local production output split the initial
JavaScript from 1,177.90 kB minified (326.04 kB gzip) to 266.92 kB (82.76 kB
gzip); the holographic scene is a separate 912.29 kB chunk (244.31 kB gzip).
This measures bundle layout, not wall-clock startup or hardware rendering.
Local build, lint, 28 Node tests and 18 browser tests pass. Commit `dfd56d9`
passed macOS, Windows and Ubuntu push CI in
[40972148472](https://github.com/sujanmj/aura-companion/actions/runs/40972148472)
and PR CI
[40972155147](https://github.com/sujanmj/aura-companion/actions/runs/40972155147);
both uploaded all three preview archives.

## 2026-10-30 continuation — live room-claim revalidation (Phase 5)

The room hub can now revalidate an enrolled node's exact claim against its
current heartbeat, invitation generation and stored turn reservation. A
transfer, stop, expiry or node revocation makes an old claim fail closed. The
Pi simulator includes a one-shot client check that explicitly reports only
validity at that instant; it does not play audio and cannot stop sound already
playing or remove a transfer race after validation. Local evidence passes:
10 node-client tests, 8 temporary-database/loopback handoff tests, and all 95
application Python tests. Commit `f0648ed` passed macOS, Windows and Ubuntu
push CI in [41012385491](https://github.com/sujanmj/aura-companion/actions/runs/41012385491)
and pull-request CI in [41012390947](https://github.com/sujanmj/aura-companion/actions/runs/41012390947).
All three preview artifacts were uploaded. No Pi, network deployment, acoustic
or physical handoff acceptance is claimed.

## 2026-10-30 continuation — expose room-claim revalidation CLI (Phase 5)

The Pi simulator now exposes the existing point-in-time claim check as
`--validate-session SESSION_ID --generation N --turn-id TURN_UUID`; it rejects
combining validation with a new claim. The command never starts playback. Local
evidence passes: 12 client tests, 8 loopback handoff tests and all 95 app Python
tests. Commit `912d162` passed all-platform push CI
[41016809978](https://github.com/sujanmj/aura-companion/actions/runs/41016809978)
and PR CI
[41016817404](https://github.com/sujanmj/aura-companion/actions/runs/41016817404);
both uploaded macOS, Windows and Ubuntu preview artifacts. This is a point-in-
time software check only; it does not establish live playback fencing or Pi
hardware acceptance.

## 2026-10-30 continuation — bound Pi heartbeat service resources (Phase 5)

The hardened systemd heartbeat-only service now declares 10% CPU, 128 MiB
memory and 16 task ceilings. Regression coverage checks the unit retains these
limits alongside its existing sandboxing and fail-closed credential preflight.
These are configured limits, not Pi measurements, and do not apply to a future
voice/perception runtime. Local service and Python tests pass. The limits
passed macOS, Windows and Ubuntu push CI in
[41013242908](https://github.com/sujanmj/aura-companion/actions/runs/41013242908)
and were rechecked in the all-platform PR run
[41014366925](https://github.com/sujanmj/aura-companion/actions/runs/41014366925).
No Pi installation or hardware resource measurement is claimed.

## 2026-10-30 continuation — prevent stale Memory refresh overwrite (Phases 2, 4)

A Windows browser run exposed an ordering race where a Memory refresh started
before a reminder save could finish later and overwrite the newer saved state.
The companion now applies only the newest status refresh. An end-to-end test
holds the old response until after the reminder save to verify the stale result
cannot replace it. All 18 browser tests, lint and production build pass locally.
Commit `e401909` passed macOS, Windows and Ubuntu push CI in
[41014353029](https://github.com/sujanmj/aura-companion/actions/runs/41014353029)
and PR CI in
[41014366925](https://github.com/sujanmj/aura-companion/actions/runs/41014366925),
with all three preview artifacts uploaded.

## 2026-10-30 continuation — session-only Mac speech output control (Phases 2, 9)

The native helper now lets the user keep replies visible while muting only new
ambient replies for the active session. Speech remains enabled by default,
reminders keep their separate opt-in, and pause resets this session-only choice.
Native lifecycle tests cover the paused guard and reset. Local Mac build,
native tests, 28 Node tests, lint and production build pass. Commit `abda9b0`
passed macOS, Windows and Ubuntu push CI in
[41015190985](https://github.com/sujanmj/aura-companion/actions/runs/41015190985)
and PR CI in
[41015196752](https://github.com/sujanmj/aura-companion/actions/runs/41015196752),
with all three preview archives uploaded. No acoustic mute or live-speaker
acceptance is claimed.

## 2026-10-30 continuation — confirmed sensor-node revocation CLI (Phase 5)

Added `scripts/revoke_sensor_node.py` so the owner can revoke an enrolled
sensor node from the command line using the existing authenticated hub API. It
requires an exact `REVOKE <node_id>` confirmation, validates the node ID before
prompting, rejects non-HTTPS remote hub URLs before sending credentials, uses
the project's direct no-proxy transport, and reports only success or a generic
failure. An ambiguous network result tells the owner to verify node status
before retrying. Tests cover success, cancellation, invalid IDs, unsafe remote
HTTP, and a hub response that does not confirm revocation. Focused local checks
pass: 16 sensor-admin tests, 12 room-client tests, and all 95 application
Python tests. Commit `89ee2f7` passed all three push-CI platforms in
[41017738378](https://github.com/sujanmj/aura-companion/actions/runs/41017738378),
which uploaded the macOS, Windows and Ubuntu previews; pull-request run
[41017743156](https://github.com/sujanmj/aura-companion/actions/runs/41017743156)
also passed all three platforms. The CLI does not enroll devices,
retrieve tokens, or claim physical node shutdown; revoked credentials are
rejected by the existing hub.

The Command Center now offers the same owner-controlled revocation beside its
room invitation controls. It uses the browser's already-entered admin token,
requires the exact typed phrase, refreshes enrolled-node and invitation status
after a confirmed response, and explains that credential revocation does not
power off the device. A revoked node's active invitation is cleared by the hub.
Six dashboard interaction tests and all 30 Node tests pass along with lint and
the production web build. Commits `1210c1c` and `60c169e` passed the exact-tree
macOS, Windows and Ubuntu PR matrix in
[41018596692](https://github.com/sujanmj/aura-companion/actions/runs/41018596692),
which uploaded all three preview archives. The matching push run
[41018590170](https://github.com/sujanmj/aura-companion/actions/runs/41018590170)
passed macOS and Ubuntu but failed the Windows browser suite: 16 tests passed,
and two Memory assertions timed out. The Setup E2E test had left proactive
check-ins enabled in the suite's shared temporary database. A follow-up now
turns that opt-in back off and awaits the expiry confirmation dialog. The full
18-test browser suite passes locally after the cleanup. Commit `0bfb4be` passed
all three push-CI platforms in
[41019957264](https://github.com/sujanmj/aura-companion/actions/runs/41019957264),
which uploaded all preview archives; its PR run
[41019964090](https://github.com/sujanmj/aura-companion/actions/runs/41019964090)
passed on all three platforms and uploaded all preview archives. No physical
device shutdown is claimed.

## 2026-10-30 continuation — owner-visible enrolled-node status (Phase 5)

Added `scripts/list_sensor_nodes.py` as a read-only follow-up to the revoke
command. It lists node ID, display name, room, 90-second heartbeat/event status
and last-seen time, but ignores credential fields and explicitly says online
does not verify sensor or playback operation. It uses the authenticated direct
transport, rejects remote HTTP before sending the admin credential, and refuses
malformed or terminal-control-character output. Nineteen sensor-admin tests,
all 95 app Python tests and 12 room-client tests pass locally. The three-platform
PR run
[41020624724](https://github.com/sujanmj/aura-companion/actions/runs/41020624724)
passed and uploaded all preview archives. No physical node or sensor behavior
is claimed.

## 2026-10-30 continuation — Command Center node heartbeat table (Phase 5)

The room invitation panel now displays enrolled node, room, heartbeat freshness
and last-seen time from the authenticated hub status endpoint. It states that
an observed heartbeat/event is not proof of sensor, microphone, speaker, or
room coverage. Refresh updates node and invitation state together; removing the
admin token or a failed refresh clears the displayed node data. Values are
rendered as text, malformed labels are excluded, and credentials are not shown.
The CLI rejects an online record without a valid last-seen timestamp, and the
Command Center labels the same inconsistent record unavailable. The 30 Node
interaction tests, 95 app Python tests, 19 sensor-admin tests,
lint, build and 18 browser E2E tests pass locally. Cross-platform CI for this
addition passed on macOS, Windows and Ubuntu in commit `c2da152` PR run
[41021377750](https://github.com/sujanmj/aura-companion/actions/runs/41021377750),
which uploaded all three preview archives. No target hardware is claimed.

## 2026-10-30 continuation — disable HTTP caching for sensor API JSON (Phases 5, 7)

The sensor API now adds `Cache-Control: no-store` to every JSON response, including
authorization failures, so caches are not instructed to retain event details,
node/room status, or other private API payloads. Two focused header tests verify
the success and unauthorized response paths. The 95 app Python tests and other
sensor/room client suites pass locally. The live-auth probe was skipped because
this workspace has no configured hub token. The first two exact-tree CI runs
passed macOS and Ubuntu but timed out different Windows E2E assertions at the
default five-second expectation limit, with 17/18 browser tests passing in each
run ([41022301772](https://github.com/sujanmj/aura-companion/actions/runs/41022301772),
[41022294392](https://github.com/sujanmj/aura-companion/actions/runs/41022294392)).
The Windows-only Playwright expectation timeout is now 15 seconds. The complete
18-test browser suite, 30 Node tests, lint, build and focused API header tests
pass locally. Commit `f32a159` passed all three platforms in the push run
[41023358488](https://github.com/sujanmj/aura-companion/actions/runs/41023358488)
and PR run
[41023365160](https://github.com/sujanmj/aura-companion/actions/runs/41023365160);
both uploaded macOS, Windows and Ubuntu preview archives.

## 2026-10-30 continuation — reject inconsistent and future-dated node status (Phase 5)

The CLI and Command Center mark records with `online=true` but no valid
last-seen timestamp as unavailable. Malformed and future-dated heartbeat times
display as unavailable and count as offline; room invitation, claim and
claim-validation paths reject them. Temporary-database regression tests check
both status and handoff denial.
The status-shape change passed push run
[41024614388](https://github.com/sujanmj/aura-companion/actions/runs/41024614388)
and PR run
[41024608660](https://github.com/sujanmj/aura-companion/actions/runs/41024608660)
on all three platforms, with preview artifacts uploaded. The future-time guard
passes all 97 app Python tests, 30 Node tests, 18 browser E2E tests, lint and
build locally. Push CI
[41024839694](https://github.com/sujanmj/aura-companion/actions/runs/41024839694)
passed on all three platforms and uploaded all previews. Its PR Mac and Ubuntu
jobs also passed after retrying a cancelled Windows job and one slow Mac E2E
attempt; both retries passed. Timestamp normalization passed all three
platforms in push run
[41027375513](https://github.com/sujanmj/aura-companion/actions/runs/41027375513)
and PR run
[41027384362](https://github.com/sujanmj/aura-companion/actions/runs/41027384362),
with all preview artifacts uploaded. The documentation snapshot passed its
three-platform PR workflow in
[41026034065](https://github.com/sujanmj/aura-companion/actions/runs/41026034065).
This is software-only evidence.

## 2026-10-30 continuation — reminder acknowledgment (Phase 11)

Scheduled reminders now have separate owner-scoped actions to record that the
current day's reminder was seen or to dismiss it for the day. Acknowledgment is
available only after delivery, is safe to repeat, and does not record task or
dose completion. Dismissal and acknowledgment cannot both be recorded for the
same delivery; both statuses reset when the next scheduled occurrence is
delivered. Legacy SQLite databases receive the new nullable field in place.
Verification includes the database migration, local-date rollover, account
isolation, API delivery and response, and the browser acknowledgment flow. Full
local verification passed: 98 app Python tests, 30 Node tests, 18 browser E2E
tests, lint, production build, native Mac lifecycle/voice tests, and the focused
room and sensor client suites. Push CI
[41028802195](https://github.com/sujanmj/aura-companion/actions/runs/41028802195)
and PR CI
[41028796545](https://github.com/sujanmj/aura-companion/actions/runs/41028796545)
passed on macOS, Windows and Ubuntu and uploaded all three preview artifacts.
No medication or health-device integration is claimed.

## 2026-10-30 continuation — SQLite backup restore verification (Phase 12)

The disposable loopback integration now copies a pre-clear SQLite backup to a
new database after stopping the original service, starts AURA against that
copy, and verifies the owner's saved conversation and facts are present. This
complements existing backup-creation and restart-persistence checks without
opening or changing the user's database. The 30-test Node suite and lint pass
locally. Push CI
[41029925282](https://github.com/sujanmj/aura-companion/actions/runs/41029925282)
and PR CI
[41029933353](https://github.com/sujanmj/aura-companion/actions/runs/41029933353)
passed on macOS, Windows and Ubuntu with all three preview archives uploaded.
The local Mac preview for source commit `de7dfbd` has SHA-256
`a35787b750a6ac5b4d3e93a2e0401f20844e7ffe10c8353eb1bb65a9eb58ecbd`; it is
ad-hoc signed and not notarized. This is a simulated database recovery check,
not a home upgrade, cross-device restore or hardware acceptance result.

## 2026-10-30 continuation — editable routine reminders (Phase 11)

Owners can correct an existing reminder's label, local time, and selected
weekdays in Memory without deleting and recreating it. Edits remain scoped to
the owner and preserve the current delivery, acknowledgment, dismissal, and
enabled state, so changing the schedule cannot deliver the same reminder twice
on the same local date. Invalid schedules are rejected by the authenticated
API and SQLite store. Local verification passed 99 app Python tests, 30 Node
tests, all 18 browser E2E tests, lint, and the production build. Cross-platform
CI for the change is pending. This is a reminder scheduling control, not dose
tracking or health-device integration.

## 2026-10-30 continuation — explicit local backup controls (Phases 4, 12)

Memory now shows the timestamp and size of AURA's local SQLite startup
snapshots, offers an explicit create-and-integrity-check action, and allows one
snapshot to be removed after a warning that database copies can contain every
account's private memory. Automatic pruning remains off; the active database
is never replaced or changed by these controls. Creation uses SQLite's online
backup API so committed WAL data is included, verifies the result with
`quick_check`, and creates POSIX files with owner-only permissions. Windows
uses the directory's inherited ACL. Automated tests cover restore-readable
content, integrity, owner-only POSIX mode, authentication, CSRF, traversal,
symlink refusal, and confirmation UI. Local verification passed 105 app Python
tests, 30 Node tests, 19 browser E2E tests, lint, and the production build.
Owners can also re-run a read-only SQLite integrity check on any listed snapshot.
The check follows only an exact generated filename, refuses symlinks, reveals no
filesystem path, and reports that it never restores or alters the active database.
Automated coverage includes valid, corrupt, invalid-name and symlinked snapshots,
authenticated API and browser verification. Local verification passed 108 app
Python tests, 30 Node tests, 19 browser E2E tests, lint, production build, and
native Mac lifecycle tests. Commit `b5bc888` passed push CI
[41035336999](https://github.com/sujanmj/aura-companion/actions/runs/41035336999)
and PR CI
[41035347627](https://github.com/sujanmj/aura-companion/actions/runs/41035347627)
on macOS, Windows and Ubuntu; both uploaded all three preview archives. The
local Mac development preview for this commit matches its embedded manifest
and has SHA-256
`997660d6f230a29e7a02d5dd47edacbd32070e9867c0524029966ac32b441e54`.
It is ad-hoc signed and not notarized. This is software recovery evidence;
home restore, cross-device privacy and hardware acceptance remain NOT RUN.

## 2026-10-30 continuation — packaged legacy SQLite upgrade (Phases 6, 12)

The extracted-preview smoke now launches AURA against both a clean temporary
database and a synthetic database made from AURA's pre-weekday-reminder schema.
It checks that the startup backup still contains the old fact and reminder,
that the upgraded app retains the existing fact, conversation and reminder,
and that the reminder receives the expected all-days default and empty
acknowledgment field. It runs SQLite `quick_check` on the backup and upgraded
database, and confirms the unauthenticated API cannot read either account's
memory. All data is disposable; the test never opens the configured home DB.

Local verification passed 109 Python app tests, 30 Node tests, 19 browser E2E
tests, lint, production build, native Mac lifecycle tests, archive verification,
and the extracted clean-install/legacy-upgrade smoke. `npm audit --json`
reported zero known vulnerabilities across the resolved Node tree; `pip-audit`
reported none for the Python requirements. Commit `75ab2e2` passed the
three-platform push workflow
[41040534258](https://github.com/sujanmj/aura-companion/actions/runs/41040534258)
and matching PR workflow
[41040541589](https://github.com/sujanmj/aura-companion/actions/runs/41040541589)
also passed on macOS, Windows and Ubuntu; both uploaded all three preview
archives. The local Mac archive for source commit `75ab2e2` matches its
manifest and has SHA-256
`885180b0d5d53b1f1c5625c350319f807d6b2554de097c7eb4fccc5473b88a6c`; it is
ad-hoc signed, not notarized. This is simulated migration and packaging
evidence, not an upgrade of the owner's home database or hardware acceptance.

## 2026-10-30 continuation — dependency audit CI (Phase 12)

Ubuntu CI now runs `npm audit --audit-level=high` against the locked Node tree
and `pip-audit` 2.10.1 against `requirements.txt`. The Python auditor and its
own dependencies stay in a disposable virtual environment, separate from
AURA's tests and runtime. Local checks found no known advisories in either
resolved tree. The first npm-gate run, commit `7e98bb1`, passed push CI on all
three desktop platforms and uploaded all preview archives in
[41047848066](https://github.com/sujanmj/aura-companion/actions/runs/41047848066)
and PR CI
[41047853691](https://github.com/sujanmj/aura-companion/actions/runs/41047853691).

The combined Node/Python audit run exposed a transient Windows-only SQLite file
lock during test cleanup. Cleanup now retries `EBUSY` with a bounded delay.
The 30-test Node suite passes locally. Commit `811332a` passed push CI on
macOS, Windows and Ubuntu in
[41049167203](https://github.com/sujanmj/aura-companion/actions/runs/41049167203)
and PR CI on all three platforms in
[41049176739](https://github.com/sujanmj/aura-companion/actions/runs/41049176739);
both uploaded all three preview archives. The audit is advisory coverage for
declared/resolved dependencies at run time, not a guarantee against unknown or
future vulnerabilities. No hardware, signing or notarization acceptance is
implied.

## 2026-10-30 continuation — scheduled dependency updates (Phase 12)

Added weekly Dependabot update configuration for the app's npm lockfile, root
Python requirements, and GitHub Actions. The checks have a five-open-PR limit
per ecosystem and do not auto-merge. The YAML parses locally. Since Dependabot
reads configuration from the repository's default branch, this policy will
become active after the branch is merged; it is not yet operating on the open
development branch. Preview CI verifies the tree and docs but cannot verify
Dependabot's scheduled service.

## 2026-10-30 continuation — reminder DST fallback coverage (Phase 11)

The reminder store now has a regression test for the repeated local 01:30
across a UTC-4 to UTC-5 fallback. The test confirms a reminder is delivered
only once for that local date even though the two instants are one hour apart.
It uses explicit fixed offsets to simulate the repeated wall-clock hour; it
does not validate a platform timezone database, scheduler wake-up, or spoken
reminder on a real device. All 110 Python app tests passed locally. Commit
`f2625d5` passed push CI
[41052472784](https://github.com/sujanmj/aura-companion/actions/runs/41052472784)
and PR CI
[41052482168](https://github.com/sujanmj/aura-companion/actions/runs/41052482168)
on macOS, Windows and Ubuntu, each with all three preview artifacts.

## 2026-10-30 continuation — reminder DST gap coverage (Phase 11)

Added the spring-forward counterpart: when a 02:30 reminder falls in the
simulated jump from 01:59 UTC-5 to 03:00 UTC-4, it becomes due at 03:00 on the
same local date. All 111 Python app tests pass locally, including 20
memory-controls tests. Commit `6252e1f` passed push CI
[41054980576](https://github.com/sujanmj/aura-companion/actions/runs/41054980576)
and PR CI
[41054988634](https://github.com/sujanmj/aura-companion/actions/runs/41054988634)
on all three desktop platforms with all preview archives. These fixed-offset
instants simulate a clock gap; platform timezone and live notification
acceptance remain open.

## 2026-10-30 continuation — Windows IANA tzdata for reminder DST (Phase 11)

Pinned test-only `tzdata==2026.6` in root `requirements-test.txt` so
`ZoneInfo('America/New_York')` reminder DST coverage can run on Windows CI
instead of skipping when the OS has no IANA database. Runtime
`requirements.txt` is unchanged. CI installs the test requirements before
app Python unit tests, and Ubuntu `pip-audit` covers both requirement files.
Local verification passed: focused New York DST test (1/1), all 21
memory-controls tests, all 112 Python app tests, 30 Node tests, lint,
production build, and browser E2E (19/19). `pip-audit` reported no known
vulnerabilities across both requirement files. Cross-platform CI for this
commit is pending; this macOS run does not prove Windows runner behavior.
