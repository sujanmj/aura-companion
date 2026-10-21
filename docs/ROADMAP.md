# AURA delivery roadmap

AURA is currently a development preview, not a finished always-present companion.
The confirmed repository is https://github.com/sujanmj/aura-companion.

## Long-term companion target

The intended product is a present, personal companion: it can notice useful
context throughout the day, remember user-approved people, events and routines,
and speak naturally without requiring a wake phrase for every exchange. It may
help find recently seen objects, offer timely routine and medication reminders,
and contribute to a shared conversation when invited. This is an aspiration;
these capabilities are not implemented as a complete system today. The active
delivery phase remains Phase 2 below.

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
- Implemented: during an explicitly started Mac ambient session, Apple Vision
  scene labels and a human-presence signal can be saved as derived summaries in
  the existing SQLite observation memory. The authenticated loopback endpoint
  accepts bounded labels only, stores no image/audio, and limits writes to one
  changed summary per minute. The Memory view already supports review/deletion.
  Unit and authenticated API tests pass, and the native helper builds. Hardware
  acceptance of this new persistence path remains outstanding.
- Implemented: the Mac helper checks the existing local check-in endpoint every
  five minutes while ambient mode is active. Existing Setup preferences remain
  the gate: check-ins are off by default, and AURA's local service enforces the
  user's quiet hours and minimum interval. Replies use local speech and do not
  invoke Claude or MCP actions. Local native helper build, API, and Python
  checks pass; cross-platform CI passed in run 39585169657.
  Physical speaker delivery of a due scheduled check-in still needs live
  acceptance.
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
  timeout now identifies the stalled prompt and links to Microphone settings.
  The packaged app now includes Apple's audio-input and camera entitlements and
  Hardened Runtime; its build checks the signed entitlement values. On the
  rebuilt Mac app, TCC logs showed the previous microphone code requirement did
  not match the new ad-hoc signature and a prompt was initiated, but no prompt
  was exposed to the UI automation session and the request again timed out.
  AURA remained paused and did not capture. Stable TCC identity and an observed
  Allow flow still need testing with a Developer ID build.
- Repeated permission attempt (2026-10-20): the rebuilt app paired to an
  isolated temporary service and database; System Settings still showed the
  microphone switch on. Starting ambient mode again produced no visible Allow
  dialog and timed out waiting for macOS microphone permission. AURA stayed
  paused with microphone and camera off. The isolated pairing, service and
  database were cleared. The older local app copy has a different ad-hoc
  signature from the code hash in the prior TCC record, and this Mac has no
  installed code-signing identity. No new live-capture acceptance is claimed.
- Fresh bundle identity permission attempt (2026-10-21): a
  `security find-identity -v -p codesigning` check reported zero valid signing identities. A
  temporary build with the same camera/microphone entitlements and a unique test
  bundle ID still showed no Allow dialog; the microphone request stayed pending
  until the 60-second watchdog returned AURA to PAUSED with both sensors off.
  System Settings continued to show the existing AURA microphone toggle on.
  The temporary app, pairing, isolated service and database were removed. This
  confirms the current ad-hoc test identity cannot complete the clean permission
  path on this Mac; a stable signing identity is still needed for acceptance.
- Remaining: hardware sleep/wake, automatic clean-install permission prompt
  recovery, multi-hour stability of the rebuilt audio-queue version, and
  calibrated acoustic loudness/feedback testing on Mac. Live Claude behavior
  also needs acceptance when credentials are configured.

Exit: automated failure-path tests and CI pass, with real-device acceptance recorded
separately. Missing hardware access must remain an explicit unresolved gate.

## Phase 3 — Usable companion on one device

Status: partial components exist; acceptance not complete.

- Implemented: diagnose configuration and service readiness without exposing secrets.
- Fixed: Anthropic and OpenAI provider failures log only a status code or a
  generic transport/response error. Provider response bodies, arbitrary
  exception text, prompts, and credentials are no longer logged. Tests cover
  HTTP and unexpected failures for both adapters; live provider acceptance
  still requires configured credentials.
- Strengthened: tests now exercise the actual Claude SDK PreToolUse hook through
  the agent bridge. Only the exact allowlisted invocation approved in AURA is
  allowed; default SDK tools remain empty, and cancellation denies a pending
  call and discards a late response. This verifies local bridge wiring, not a
  live Claude or MCP server session.
- Implemented: Setup includes a guided first-device acceptance checklist for
  conversation/provider, reviewed voice input, spoken output/Stop, memory
  continuity, Mac ambient mode and optional MCP approvals. Checklist marks are
  manual notes stored in that browser only; they do not run tests or claim that
  a provider, microphone, speaker, camera or tool worked. Browser end-to-end
  coverage checks persistence and clearing of those notes.
- Implemented: Setup can explicitly send a fixed, memory-free test prompt to the
  selected configured provider. AURA returns only whether the provider replied;
  it does not save the response or expose provider credentials. Refreshing
  readiness remains configuration-only, and the test action is unavailable
  until readiness identifies a supported provider to test. Unit, authenticated API/CSRF integration,
  and browser tests cover the opt-in and default local-only behavior. A live
  provider check still requires user configuration and a button click.
- Implemented: browser spoken replies can use an installed system voice and a
  selectable 0.8×–1.2× pace. Preferences stay in the current browser and also
  apply when configured cloud speech falls back to local browser speech. The
  default voice and existing opt-in Speak replies behavior are unchanged;
  end-to-end tests verify persistence and the actual utterance settings.
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
- Implemented: Memory can add a manually introduced person only after the user
  records their agreement, lists that consent without exposing private notes,
  and can explicitly forget the person and associated timeline. When the user
  names a consented person, the existing companion prompt can use their name
  and relationship; no camera matching is implied. Changes are scoped to their
  SQLite account. This does not enroll or recognize faces.
- Implemented: routines can be corrected or explicitly forgotten; a forgotten
  routine is suppressed from automatic conversation extraction until the user
  explicitly asks AURA to remember it again.
- Implemented: ambient observations can be deleted individually from the
  authenticated Memory view; deletion is scoped to the current user's SQLite
  records and removes that observation from future exports.
- Implemented: Memory can clear all saved observations and explicit event notes
  for the signed-in account in one confirmed action. Other memory categories
  remain intact. The operation is authenticated, CSRF-protected, owner-scoped,
  and covered by storage, API, and browser tests; CI verification is pending.
- Implemented and CI-verified in commit `eadd6a6`: saved observations can also
  be corrected in Memory. A correction replaces the selected SQLite row, is
  marked `user_correction` with explicit user-authored wording, and enters a
  reply only when relevant to the current message. The authenticated API bounds
  the input and scopes edits to the owning account. Browser, API, prompt and
  storage tests pass; macOS and Ubuntu push and pull-request workflows passed
  in runs 39592037061, 39592050401.
- Fixed: emotional cues are inferred from the current user turn instead of
  accumulating across unrelated older messages. Quiet or still camera context
  no longer counts as evidence that someone is sad or lonely.
- Fixed: simple explicit negation such as “I am not anxious” no longer creates
  or reuses anxiety and low-mood labels from the current turn.
- Fixed: explicitly uncertain emotional wording such as “I'm not sure whether
  I'm anxious” no longer creates a mood fact or reactivates an older mood cue
  through generic stress wording in that saved fact. A separate clear positive
  cue still takes precedence. Companion tests cover both cases.
- Implemented: consent-based local check-ins default off, wait for a saved idle
  interval, honor quiet hours, and only appear while the web companion is open.
- Implemented: an explicit “remember that …” request saves a user-provided event
  note in the existing SQLite observation history. Related notes enter reply
  context only when the user mentions matching terms; unrelated notes stay out.
  Notes are marked unverified, shown in Memory, and can be deleted there. Simple
  credential and payment-secret requests are excluded from event-note storage.
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
- Improved: the enrolled-node heartbeat client retries request timeouts and
  temporary HTTP 429/5xx failures for up to three total attempts, reusing the
  same authenticated request. It stops on credential rejection and does not
  print untrusted response bodies. Four focused tests cover retries, immediate
  rejection, and malformed responses; CI run 39550555145 passed on macOS and
  Ubuntu. This is client reliability coverage, not Raspberry Pi hardware
  acceptance.
- Added: a hardened systemd presence service keeps an enrolled Pi node's
  heartbeat fresh after reboot. It runs as a dedicated unprivileged account,
  validates its node credential, hub URL, and interval before startup, and has
  no writable application-state paths. It sends no sensor, audio, or video data.
  Unit, configuration, and service-loop tests are part of CI. This has not been
  installed on a Raspberry Pi and is not a capture runtime.
- Implemented: optional Supabase sync now has a durable SQLite retry outbox for
  conversation and sensor-event rows. The outbox stores source-row references,
  device IDs and retry metadata rather than duplicating message/event text;
  capped backoff avoids rapid repeat requests, and each item releases SQLite's
  write lock before the next network request so local memory writes can proceed.
  A cleared local conversation
  cancels pending uploads and queues an idempotent remote delete for any already
  synced row. Offline tests cover queue/retry, backoff, source-row deletion and
  remote cleanup. This does not sync profile facts/routines or verify a live
  Supabase account.
- Added a hardened systemd service template for the Pi sensor API hub. It uses a
  dedicated non-root account, private state directory, restrictive filesystem
  settings and a startup guard requiring a unique 32-character sensor token.
  Automated checks cover configuration rejection and unit hardening. This starts
  only the authenticated sensor API; it is not a Pi companion runtime or GPIO
  driver and has not been installed on target hardware.
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

## Future companion capability phases

These phases extend the delivery work above. They are not complete, and they do
not change the current status: Phase 2 is active.

### Phase 7 — Continuous, private perception

- Finish and validate continuous perception on Mac first, with explicit
  camera/microphone indicators, a visible pause, resource limits, and reliable
  offline behavior; port the validated runtime to Pi afterward.
- Process live streams locally where supported; separate transient perception
  from information deliberately saved to SQLite. Raw audio/video retention stays
  off unless the user makes a specific, informed choice.
- Validate consent, sensor shutdown, reconnects, sleep/wake, storage bounds and
  multi-hour operation on target hardware before describing it as always-on.

### Phase 8 — People, objects and episodic memory

- Let the user enroll and name consenting household members; give the user a
  way to review, correct and remove those profiles and related memories.
- Support configurable notices for unrecognized visitors without guessing who
  they are. Detect and remember useful object sightings, such as where keys were
  last seen, only with confidence and clear age/context.
- Store concise local event summaries with time, source and uncertainty, and
  provide retrieval, expiry, export and deletion controls.

### Phase 9 — Proactive companion conversation

- Offer natural back-and-forth speech without requiring a repeated wake phrase,
  using turn detection, echo control, speaker preference and interruption rules.
- Learn routines only from user-approved memory and feedback. Make check-ins,
  meal/bedtime prompts and other nudges configurable, quiet-hour aware and easy
  to dismiss or correct.
- Ask when context is ambiguous; do not present inferred mood or activity as
  certain knowledge.

### Phase 10 — Shared conversation and grounded knowledge

- Let the owner choose when AURA may join nearby conversations, while making
  ambient sensing visible and respecting other people's privacy.
- Distinguish a helpful, invited contribution from an interruption. For claims
  that need checking, use an explicitly enabled online source, cite or name the
  basis in the reply, and state uncertainty rather than confidently guessing.
- Keep online lookup separate from ambient tool execution; every consequential
  action continues to require explicit user approval.

### Phase 11 — Opt-in routine and wellness support

- Implemented for Mac preview: user-created daily local reminders require an
  explicit enable checkbox, are delivered at most once per local day, and can
  be dismissed for that day or deleted. AURA states it cannot confirm task or
  dose completion. Cross-platform tests cover scheduling, delivery, dismissal
  and account scoping; live speaker delivery still needs Mac acceptance.
- Add optional, user-controlled links to iPhone or wearable health data where
  supported, and show what is collected, where it is stored and how to remove it.
- Summarize trends in sleep, activity and meals as non-diagnostic observations
  the user can correct, rather than claiming to optimize health automatically.
- Support explicit medication schedules and reminders across enrolled devices,
  with a clear way to acknowledge or dismiss each reminder. Never infer a dose
  was taken from camera footage or treat a reminder as confirmation.

### Phase 12 — Companion acceptance and release

- Test end-to-end across Mac and Pi, including room handoff, false detections,
  mistaken memories, interruptions, network loss, privacy controls and deletion.
- Publish only a signed, documented build whose tested sensors, providers,
  retention behavior and known limitations match its release notes.

Exit for these future phases: the behavior is useful in real homes, stays under
the user's control, has passed privacy and reliability acceptance, and is never
described as human-level or production-ready without evidence.
