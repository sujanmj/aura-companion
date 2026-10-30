Warning: truncated output (original token count: 20216)
Total output lines: 1209

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
  tests verify private routing and payload exclusions; the existing API suite
  covers unsaved private turns. Local Mac build and native tests pass; CI and
  live provider behavior remain pending.
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
- Local voice-l…12716 tokens truncated…d lint and production build pass. The
follow-up CI and preview evidence is recorded in the next milestone entry. No
real provider retention, multi-person consent, or acoustic behavior is verified
by these software tests.

## 2026-10-29 continuation — bounded reply and preview acceptance (Phases 10, 12)

The shared-conversation provider reply is capped at the same 4,000-character
limit used for transcript messages, so one long response cannot invalidate the
next turn. A regression test covers the cap. On the pushed source commit
`76ce6e6`, local verification passed: 93 Python tests, 23 Node tests, all 18
browser tests, lint, production build and preview bundle. The Darwin bundle
manifest names that source commit, records ad-hoc native signing, and leaves
notarization and hardware acceptance explicitly unverified.

Commit `76ce6e6` passed all three push CI jobs in
[40904869469](https://github.com/sujanmj/aura-companion/actions/runs/40904869469).
CI uploaded macOS, Windows and Ubuntu previews. This completes software-only
validation for the current group exchange and preview packaging changes. A
signed/notarized public release, installed-device permission and acoustic tests,
Pi capture, multi-room handoff and home acceptance still require the relevant
credentials and physical devices; none is claimed by this CI run.

## 2026-10-29 continuation — check-in quiet-hour boundaries (Phase 11)

Added a regression test with an already-due check-in, proving that overnight
quiet hours suppress it at 23:00 and 07:59 and permit it exactly at the 08:00
end boundary. This isolates quiet-hour behavior from the separate cooldown
condition. The full local Python suite passes 94 tests. Commit `9ed1705` passed
macOS, Ubuntu and Windows push CI in
[40906445069](https://github.com/sujanmj/aura-companion/actions/runs/40906445069),
which uploaded previews for all three platforms. This does not represent
local-timezone/DST or live speaker acceptance.

## 2026-10-29 continuation — chained solo follow-up windows (Phase 9)

Added native lifecycle coverage proving that each accepted solo follow-up may
receive one reply without repeating the wake phrase, and that the reply opens a
new bounded window. The invitation remains off unless freshly enabled for the
ambient session and remains revocable by Pause; no speaker identity is inferred.
Native tests and an ad-hoc Mac app build pass locally. The chained-turn commit
`d560347` passed macOS, Ubuntu and Windows push CI in
[40909846047](https://github.com/sujanmj/aura-companion/actions/runs/40909846047);
the PR Windows browser job hit unrelated 30-second test ceilings twice. The
Windows-only browser-test ceiling is now 60 seconds. Its PR run passed all three
platforms in [40912788103](https://github.com/sujanmj/aura-companion/actions/runs/40912788103),
and push Windows/Ubuntu passed in
[40912780134](https://github.com/sujanmj/aura-companion/actions/runs/40912780134).
An explicit heading wait fixes the existing routine test's tab-navigation
race. Commit `f12edab` passed all three push CI jobs in
[40914132493](https://github.com/sujanmj/aura-companion/actions/runs/40914132493)
and pull-request CI in
[40914144108](https://github.com/sujanmj/aura-companion/actions/runs/40914144108);
both runs uploaded macOS, Windows and Ubuntu preview archives. This verifies
state logic only, not acoustic turn detection or live speech quality.

## 2026-10-30 continuation — enrolled-node room claim client (Phase 5)

Added an explicit one-shot `/rooms/claim` client to the Pi node simulator. It
requires an active invitation's session and generation plus a caller-supplied
canonical UUID for the logical reply, and authenticates with the enrolled node
credential. The client makes one request and fails closed when the response is
lost or rejected, since changing the turn UUID could replay a reply. Automated
coverage checks validation, credential/payload scope, conflict handling and
ambiguous network failure. This establishes a software client seam only; it
does not run a Pi service, access a microphone or speaker, or prove physical
room handoff. Native conversation-loop integration, cancellation/fencing at
playback, reconnect behavior and hardware acceptance remain open.

The first three-platform run for the client found two Windows browser failures
where Memory assertions raced the saved-state refresh. Opening Memory now reloads
the current local memory, and the affected browser tests wait for the chat or
person-save refresh to finish. The full browser suite passes locally (18 tests),
as do lint/build, 94 Python app tests, and the room-client, heartbeat and
service suites. Corrected commit `bfde1c4` passed macOS, Windows and Ubuntu push
CI in [40948677085](https://github.com/sujanmj/aura-companion/actions/runs/40948677085).
The run uploaded all three preview archives. This verifies software and
packaging builds only; it does not add physical-device acceptance.

## 2026-10-30 continuation — TLS for network sensor hubs (Phase 5)

The sensor API now refuses to bind to a network address without a configured
TLS certificate and private key, and negotiates TLS 1.2 or newer. HTTP remains
available on loopback for local development. Sensor event, enrollment, heartbeat
and room-claim clients accept HTTPS for remote hubs and reject remote HTTP before
sending a credential; the heartbeat service validator applies the same rule.
The hub requires absolute regular certificate/key files without symlinks in any
path component and rejects unsafe POSIX private-key permissions; the hardened
systemd preflight checks the same requirements before startup. Updated
the Pi instructions to require a trusted certificate and HTTPS. Automated tests
cover transport URL policy, loopback exceptions, server TLS setup and service
preflight; no live certificate, Pi install or network deployment is claimed.
Commit `d1c7d5d` passed push CI in
[40950505353](https://github.com/sujanmj/aura-companion/actions/runs/40950505353)
and pull-request CI in
[40950517278](https://github.com/sujanmj/aura-companion/actions/runs/40950517278)
on macOS, Windows and Ubuntu; both runs uploaded all three preview archives.
The Pi certificate installation, trust-store setup and network deployment
remain untested.
The follow-up also validates certificate/key paths at server startup, rejecting
symlinks and unsafe POSIX key permissions. Commit `b3087c5` passed push CI in
[40951723853](https://github.com/sujanmj/aura-companion/actions/runs/40951723853)
and pull-request CI in
[40951731217](https://github.com/sujanmj/aura-companion/actions/runs/40951731217)
on all three platforms; both runs uploaded preview archives.
The final path check also rejects symlinked parent directories. Commit `b5695ac`
passed push CI in
[40952983216](https://github.com/sujanmj/aura-companion/actions/runs/40952983216)
and pull-request CI in
[40952990897](https://github.com/sujanmj/aura-companion/actions/runs/40952990897)
on macOS, Windows and Ubuntu, with all three preview archives uploaded.

## 2026-10-30 continuation — owner room invitation controller (Phase 5)

Added `scripts/room_invitation.py` for an owner to inspect, start, transfer and
stop a five-minute room invitation from the command line. It requires the
administrator token, permits remote use only with HTTPS, asks for the exact
typed action before starting/transferring/stopping, sends one request, and
prints only safe session fields. The controller does not activate sensors,
speech, memory recall or playback. A new focused suite and the loopback API
integration test verify the command flow. It refuses redirects and bypasses
machine-wide proxies for hub credentials. Local checks pass: six controller
tests, the seven-test handoff integration suite, all 94 app Python tests, and
the heartbeat, node-client and transport suites. Commit `bd89594` passed push
CI in [40956030944](https://github.com/sujanmj/aura-companion/actions/runs/40956030944)
and pull-request CI in
[40956043251](https://github.com/sujanmj/aura-companion/actions/runs/40956043251)
on macOS, Windows and Ubuntu. Both runs uploaded all three preview archives.
This is software control-plane coverage, not Pi or multi-room hardware
acceptance; room invitations still do not control capture, speech or playback.

## 2026-10-30 continuation — dashboard room invitation controls (Phase 5)

Added an owner-only Room Invitation panel to the local Command Center. It lists
enrolled nodes without displaying their credentials, displays the current
session, and supports invite, transfer and stop with exact typed confirmation.
Requests stay same-origin, bypass browser redirects, and never activate a
camera, microphone, speech or playback. Focused dashboard logic tests cover
consent, one-shot mutation requests, uncertain outcomes and status refresh; a
loopback API check verifies script serving. Commit `62adb72` passed push CI
[40959155691](https://github.com/sujanmj/aura-companion/actions/runs/40959155691)
and PR CI
[40959164879](https://github.com/sujanmj/aura-companion/actions/runs/40959164879)
on macOS, Windows and Ubuntu; both runs uploaded all three preview archives.
That commit also fixes SQLite worker shutdown ordering, covered by a regression
test. These runs validate software and packaging only; no physical room handoff,
Pi, sensor, playback, acoustic or public-signing acceptance is claimed.

## 2026-10-30 continuation — validate room claim acknowledgements (Phase 5)

The enrolled-node claim client now treats a claim as usable only when the hub
explicitly reports success and echoes the exact requested session, generation
and logical turn UUID with a finite, still-live expiry. Missing, malformed,
expired or mismatched acknowledgements fail closed; the simulator does not
retry or authorize playback from them. Focused unit and loopback handoff tests
cover matching claims, stale/incorrect fields, non-finite expiry, conflicts and
ambiguous network failure. Local verification passed: 94 app Python tests, 14
room-claim/handoff tests, 28 Node tests, 18 browser tests, native lifecycle and
speech tests, frontend lint and production build. Commit `03e1a89` passed
macOS, Windows and Ubuntu push CI in
[40960508464](https://github.com/sujanmj/aura-companion/actions/runs/40960508464)
and PR CI
[40960227044](https://github.com/sujanmj/aura-companion/actions/runs/40960227044);
both runs uploaded all three preview archives.
This validates the software reservation response only; no Pi service, speaker
playback, room cancellation/fencing, or physical handoff acceptance is claimed.

## 2026-10-30 continuation — direct Pi hub transport (Phase 5)

The Pi simulator's event, heartbeat and room-claim requests, sensor-node
enrollment, dashboard-status utility and documented sensor API test client now
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
