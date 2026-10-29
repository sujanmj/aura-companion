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
- Repository-build retest (2026-10-23): the rebuilt helper paired to an isolated
  SQLite service and remained PAUSED while requesting microphone access.
  System Settings showed AURA enabled for both Microphone and Speech
  Recognition, but no Allow prompt appeared. The 60-second watchdog returned
  AURA to PAUSED with both sensors off. The test pairing, service and database
  were cleared. A valid Developer ID identity is still needed to verify the
  clean permission flow. Startup now reports each modern on-device speech
  preparation stage so later attempts can distinguish model setup stalls from
  system permission stalls.
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
- Implemented for Mac preview: choose an installed English system voice and
  bounded speech pace in the native helper. Settings stay in macOS preferences
  and apply to ambient replies and opted-in reminders. Native tests cover
  defaults, saved voice selection, missing-voice fallback, and safe pace bounds;
  macOS and Ubuntu pull-request CI passed in run 39615690020, and acoustic
  quality still needs live acceptance.
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
- Implemented: Claude prompts now include saved routine memories only when the
  current message has relevant terms. Routine context is labeled as potentially
  incomplete and never treated as a live schedule or proof of current behavior.
  Companion tests cover relevant inclusion and unrelated-routine exclusion.
- Implemented: local-only replies can answer matching questions about saved
  routine memories without sending them to a provider. Responses identify the
  source as AURA's memory, flag possible staleness, and omit unrelated routines.
  Companion tests cover provider-free retrieval and unrelated-memory exclusion.
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
not close the unresolved Phase 2 hardware acceptance gates.

### Phase 7 — Continuous, private perception

- Implemented for Mac preview: an optional, off-by-default spoken person-in-view
  notice uses local human-presence detection, waits for stable absence and
  re-entry, and says it cannot identify who is present. It does not claim a
  visitor is unknown, stores no identity, and runs only during explicitly
  started ambient mode. Native tests cover opt-out, debounce, re-arming, and
  one notice per entry; push CI passed in run 39617638169, while pull-request
  CI and live false-positive acceptance remain pending.
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
- Implemented: natural singular/plural item questions can retrieve matching
  user-entered or corrected event notes (for example, asking about “keys” can
  find a note about “key”). Retrieved notes include their saved timestamp and
  are labeled as potentially outdated. This does not infer an object's current
  location from camera imagery. Companion tests cover note retrieval and the
  uncertainty label; the Mac app build and full local test suite pass.
- Implemented: local-only conversations can answer a matching “where is/are”
  question directly from the user's own note without sending it to a provider.
  User-authored notes take priority and the reply identifies their age. A later
  continuation adds a separate, explicitly uncertain camera-estimate hint path.
  Companion tests cover recall and both exclusions.
- Implemented: a fresh on-device object label may provide a limited location
  hint when its top label matches the question with at least 85% confidence and
  was saved within 30 minutes. AURA reports the time and uncertainty and never
  claims a room or precise location. Explicit user notes take priority.

### Phase 9 — Proactive companion conversation

- Implemented for the Mac preview: with a fresh, session-only opt-in, the owner
  can select a 15, 30 or 60-second window for one solo follow-up after a direct
  reply. The window still admits only one phrase, AURA does not identify the
  speaker, and Pause, sleep or closing the window revokes the opt-in. Native
  lifecycle tests cover each deadline and its exclusive boundary.
- Implemented for the Mac preview: a visible Stop speaking control interrupts
  local speech without pausing live sensors; microphone transcription resumes
  only if ambient mode is still active. Stopping invalidates delayed completion
  callbacks, so they cannot alter a later turn. If AURA is speaking a check-in
  with sensors off, stopping leaves them off. Native tests cover stale playback
  completion generations. No acoustic interruption test is claimed.
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
  be paused, resumed, dismissed for that day, or deleted. AURA states it cannot
  confirm task or dose completion. Cross-platform tests cover scheduling,
  delivery, dismissal, account scoping, and active-reminder limits. The native
  helper polls while paired and running, including with ambient sensors paused.
  Pull-request and push CI passed on both platforms in runs 39615337678 and
  39615327822. Live speaker acceptance remains pending.
- Implemented: local reminders can repeat on selected weekdays at a user-set
  local time. Existing reminders migrate to all seven days without changing
  their label, time, delivery history, or enabled state. Empty/duplicate days
  and out-of-range values are rejected; reminders remain owner-scoped and
  deliver once per selected local date while the app/helper is running. This is
  a general reminder schedule, not a medication tracker or proof of completion.
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
- Added a device-by-device acceptance record in
  [`PHASE_12_ACCEPTANCE.md`](PHASE_12_ACCEPTANCE.md). It separates CI evidence
  from physical-device checks, records current hardware and signing blockers,
  and prevents simulated results from being recorded as home acceptance.

Exit for these future phases: the behavior is useful in real homes, stays under
the user's control, has passed privacy and reliability acceptance, and is never
described as human-level or production-ready without evidence.

## 2026-10-28 continuation — observation expiry (Phases 4, 7, 8)

Baseline `0a121ba9589155f8bee311d50380b817a3c2775f` was verified against
GitHub Actions run [39900633505](https://github.com/sujanmj/aura-companion/actions/runs/39900633505):
both macOS and Ubuntu jobs passed, including preview artifact upload.

Added opt-in note expiry (1, 7, 30, 90 or 365 days) with a deletion-count preview
and explicit confirmation in Memory. The default preserves all existing notes.
Expiry covers observations, explicit event notes and corrections, is scoped to
the account, and runs on service requests before recall/export. It does not erase
original chat messages or existing SQLite backups. Turning expiry off cannot
restore removed notes. No background deletion is promised while AURA is stopped.

Local validation: 61 Python tests, 12 Node tests, frontend build/lint and native
lifecycle/speech tests passed; the ad-hoc Mac preview built successfully. Browser
validation and new-commit CI are recorded in the accompanying release evidence.
No live sensor, provider, acoustic, Pi or health integration acceptance was run.

## 2026-10-28 continuation — invited turns (Phases 3, 9, 10)

Observation expiry commit `a451ef5` passed macOS and Ubuntu CI in
[40680587802](https://github.com/sujanmj/aura-companion/actions/runs/40680587802),
including preview artifacts for both platforms.

Native direct requests now require a leading “AURA” or “Hey AURA”. Generic
nearby phrases such as “I need help” or “what do you think” no longer trigger a
reply by themselves. A fresh per-session solo-follow-up toggle allows one phrase
within 30 seconds after a direct reply finishes. Pause, sleep and close revoke
it; stale replies cannot reopen a revoked window. This is not speaker recognition
or acoustic acceptance, and nearby consenting speech may still be attributed to
the owner's conversation when this explicitly enabled solo mode is used.

The web conversation offers a separate reviewed shared question. Each submission
requires participant agreement; editing the question clears that agreement. This
path uses no private-memory context, saves neither question nor reply, invokes no
tools and does not claim online verification. Configured providers may retain
requests under their own policies. It is a one-question contribution, not ambient
group capture. Pause any separately running native ambient helper before a group
session; this web form does not control that helper's sensors.

Local validation: 64 Python tests, 12 Node tests, 15 browser tests, native tests,
frontend build/lint and ad-hoc Mac build passed. New-commit CI pending. No live
speech, participant, provider or hardware test is claimed.

## 2026-10-28 continuation — preview release integrity (Phases 6, 12)

Invited-turn commit `a5f3e12` passed both macOS and Ubuntu jobs in
[40681826266](https://github.com/sujanmj/aura-companion/actions/runs/40681826266).

Preview packaging now requires clean committed source, verifies browser input and
output hashes, checks native source provenance and the local code signature, and
rejects private/runtime paths, symlinks, SQLite contents and selected credential
markers. These checks can also run before committing/publishing newly staged
files. They are a guardrail, not a comprehensive secret scanner or a hardware
certificate. Existing backups and databases are never packaged or modified.
A release manifest records the source commit, packaged-file hashes, platform,
native signing scope and explicit absence of notarization/hardware verification.
CI uploads only the ZIP, its checksum and the manifest.

Dependency lockfile updates body-parser to 2.4.0 and fast-uri to 3.1.9; npm audit
reported zero known vulnerabilities on 2026-10-28. Native settings now scroll
below a fixed capture control, and text matches the direct-address trigger.
Local checks passed: Python 73/73 (including nine real-archive packaging tests),
Node 12/12, browser 15/15, native lifecycle/speech tests, frontend build/lint and
ad-hoc Mac build. Archive creation is checked after committing; new CI pending.
No clean-install, live sensor, acoustic or distribution-signing claim is added.

## 2026-10-29 continuation — explicit online sources (Phase 10)

Release-integrity commit `b3f3b58` passed macOS and Ubuntu CI in
[40683350586](https://github.com/sujanmj/aura-companion/actions/runs/40683350586),
with both platform ZIPs, checksums and release manifests uploaded.

The web Conversation view now offers a separate Wikipedia source check. Each
exact query requires fresh approval, and editing cancels that approval. The
server sends only the reviewed text to fixed English Wikipedia API endpoints;
it sends no personal memory, ambient transcript, provider key or session cookie.
Sources are plain-text excerpts with direct citations, attribution, retrieval
time, ambiguity/truncation notices and explicit uncertainty. The source's claims
are not independently verified, and no model-generated synthesis is presented.
This is the first public-knowledge source adapter, not general web search, live
news, medical advice, or complete conversational grounding across all providers.

Requests have an eight-second deadline, bounded response bodies, at most three
source summaries, no redirects, cancellation, and a short cooldown. Source data
cannot select arbitrary URLs or invoke tools. The lookup does not touch SQLite
and results can be cleared. Cancellation cannot retract a query already sent to
Wikipedia. The feature never activates automatically from ambient speech.

Local evidence: Python 73/73, Node 20/20, browser 17/17, frontend build and lint
passed. Browser tests cover fresh approval, edited queries, inert rendering of
malicious-looking text, clear, and cancellation. An authenticated API test with
mocked source transport verifies no memory changes. A real public query for
“Raspberry Pi” on 2026-10-29 IST returned Raspberry Pi, Raspberry Pi OS and
Raspberry Pi 4 summaries with no unavailable sources (retrieved UTC
2026-10-28T21:28:39.588Z). This verifies that single public-source path, not answer
accuracy or ongoing availability. Commit `3cfd416` passed both macOS and Ubuntu
CI in [40772617052](https://github.com/sujanmj/aura-companion/actions/runs/40772617052),
including both preview archive uploads.

## 2026-10-29 continuation — invited room reservations (Phase 5)

Added the [room handoff protocol](ROOM_HANDOFF.md) to the existing enrolled-node
hub. An explicit invitation creates a five-minute lease for one online node;
transfers require fresh approval and a matching generation. Old-node requests,
expired invitations, cross-owner nodes, duplicate turn UUIDs and stale stops are
rejected. Revocation or credential rotation clears the active invitation.
SQLite transactions enforce one reservation per logical turn across connections
and room transfers. Stop removes live invitation/claim metadata; memory export
includes only owner-scoped metadata and no node credential.

This is an API/software prototype, not a working multi-room audio companion.
The caller must preserve the logical reply's UUID across retries. A returned
reservation cannot be recalled, so physical playback still needs cancellation
and fencing. There is no capture, speaker action, location inference, shared
memory retrieval, or Pi/Mac conversation integration in this milestone. The
original five-minute deadline never renews on transfer. Device/API changes now
trigger the application CI workflow.

Local evidence: 80 Python tests passed, including seven new handoff tests with
a real loopback HTTP server, independent SQLite connections racing for one turn,
restart/expiry, auth, consent, scope, rotation/revocation and deletion checks.
The 20 Node tests, 17 browser tests, native lifecycle tests, lint and existing
provider/cloud/heartbeat regression tests also passed. Commit `0ff2985` passed
macOS and Ubuntu CI in [40773910557](https://github.com/sujanmj/aura-companion/actions/runs/40773910557),
with both preview archives uploaded. Physical multi-room acceptance remains pending.

## 2026-10-29 continuation — cross-platform preview checks (Phases 6, 12)

Windows joins the CI matrix for the source/web/Python preview. Build helpers and
the server select `python` on Windows, `python3` elsewhere, or the user's explicit
`AURA_PYTHON` executable. Python IPC forces UTF-8 to preserve multilingual names
and notes regardless of the console code page. Build provenance and archive
member paths use forward slashes on every platform. Test fixtures use file URLs
for module loading and SQLite read-only access, and directory symlinks declare
their type explicitly.

Local Mac evidence: 80 Python, 22 Node and 17 browser tests passed; build, lint,
and ad-hoc native build passed. The new IPC test round-trips Hindi, accented text
and emoji through a real Python process despite an inherited ASCII setting.
The packaging test verifies archive/member hashes and slash-normalized paths.
Commit `4c9b44a` passed macOS, Ubuntu and Windows CI in
[40774579580](https://github.com/sujanmj/aura-companion/actions/runs/40774579580),
including Linux and macOS preview uploads. This does not provide a Windows native ambient
helper, installer, signing, acoustic tests or device-permission acceptance.

## 2026-10-29 continuation — keep Ollama prompts on device (Phase 2)

Hardened the existing optional Ollama provider. It connects through a direct
HTTP socket only to a numeric loopback address and fixed `/api/generate` path;
it does not consult proxies or follow redirects. Prompts, response bodies and
returned text have fixed size bounds. Bad or unavailable local responses fall
back through the existing behavior. `OLLAMA_MODEL` is now consistent between
provider selection and the setup panel. A loopback `OLLAMA_URL` may select a
custom local port; external hosts, DNS names, credentials, queries, fragments
and other paths are refused before sending any prompt.

Four temporary local-server tests cover Unicode request/reply, model setting,
rejected remote destinations, no redirects, size limits and malformed output.
The complete local validation passed: 84 Python tests, 22 Node tests, 17 browser
tests, lint, the provider/cloud/node regressions and Mac native tests/build.
These HTTP tests do not verify an installed Ollama model, its quality, or its
availability on a physical device. That live check remains optional and must be
run by the user with a model installed.

## 2026-10-29 continuation — one unsaved private turn (Phases 4, 9, 10)

Conversation view now offers a separate, explicitly approved private question.
AURA builds that reply in a new SQLite `:memory:` database and uses only the one
reviewed message. It does not query or expire the user's saved memory, extract
facts/routines, write the saved conversation/observation tables, create a backup,
or enqueue cloud sync. The transcript stays in the current browser state and can
be cleared; refreshing the tab clears it. Tools, microphones, cameras, and online
lookup are not started. The selected provider receives the text; when remote,
its own handling and retention policy still applies.

The message and reply survive no page refresh and are not part of chat export or
memory retrieval. This is one turn, not a continuous private conversation. The
server requires literal fresh consent, authentication and the existing CSRF
origin check. A temporary Ollama HTTP service integration test seeds sentinels
in the owner's facts, conversation, observations and routines, verifies none
reach the model prompt, and confirms each saved-table count stays unchanged.
Browser tests verify approval reset, reply clearing and no saved history. A
related context-filter bug was fixed: substring matching had mistaken `hi`
inside ordinary words such as “this” and “thinking” for a generic greeting,
which skipped the configured provider; greeting detection now compares words.

Local evidence: 85 Python, 23 Node, 18 browser; native lifecycle tests, Mac
ad-hoc app build, lint, provider/cloud/node regressions and frontend build pass.
Commit `3fa324e` passed macOS, Ubuntu and Windows push CI in [40810690005](https://github.com/sujanmj/aura-companion/actions/runs/40810690005) and pull-request CI in [40810695923](https://github.com/sujanmj/aura-companion/actions/runs/40810695923), with all three preview artifacts uploaded from the push run. The temporary Ollama service is simulated and does
not represent a live model quality or device-privacy acceptance result. The
Ollama guard itself passed macOS, Ubuntu and Windows CI in [40810170044](https://github.com/sujanmj/aura-companion/actions/runs/40810170044),
with preview packages uploaded for all three runners.

## 2026-10-29 continuation — weekday reminder schedules (Phase 11)

Added selected-weekday repetition to local reminders, retaining the existing
once-per-selected-day behavior and local-time schedule. The authenticated API
validates a non-empty unique weekday list. SQLite migrates existing daily
reminders to every weekday while preserving each row, and the Memory UI shows
the selected days. AURA delivers only while the app or paired Mac helper is
running and cannot confirm that a task or dose was completed.

Local verification: 88 Python tests, 23 Node tests, all 18 browser tests,
native lifecycle/speech tests, provider/cloud/Pi heartbeat regressions, frontend
build/lint and an ad-hoc signed Mac app build pass. Migration tests preserve
legacy reminders, and simulated weekday tests confirm local weekday gating.
Commit `84b8e65` passed macOS, Ubuntu and Windows push CI in [40811353403](https://github.com/sujanmj/aura-companion/actions/runs/40811353403) and pull-request CI in [40811359575](https://github.com/sujanmj/aura-companion/actions/runs/40811359575). The push run uploaded all three preview artifacts. The initial Windows browser attempt timed out during UI state refresh; rerunning that job passed. No speaker or medical integration test is claimed.

## 2026-10-29 continuation — cautious visual object hints (Phase 8)

When the owner asks where an item is, local recall can offer a recent on-device
scene estimate only if the requested item matches Vision's top label, the
top-label confidence is at least 85%, and the estimate is no more than 30
minutes old. A matching explicit user note takes priority. The reply includes
the saved time and confidence, warns that the object may be misidentified or
outdated, and says AURA cannot name its room or exact spot. Human presence is
not used as identity or object evidence. Low-confidence, stale, unrelated and
secondary classification labels do not produce a hint. Images remain unstored.

Automated tests use temporary SQLite observations and cover fresh, high-
confidence matching labels, stale or low-confidence rows, secondary-label
label rejection, unrelated/person queries, and explicit-note priority. The full
suite passes locally. This does not verify Vision's real-world object accuracy
or guarantee that AURA can find an object on a particular Mac. Commit
`20c5bbc` passed macOS, Ubuntu and Windows push CI in
[40813822187](https://github.com/sujanmj/aura-companion/actions/runs/40813822187)
and pull-request CI in
[40813827634](https://github.com/sujanmj/aura-companion/actions/runs/40813827634).
All three preview archives were uploaded from the push run.

## 2026-10-29 continuation — camera estimate review clarity (Phases 4, 8)

The Memory view now shows the confidence score attached to each locally saved
Vision summary and states that it applies only to the top classification label.
This makes the evidence behind a visual hint reviewable before the user edits
or deletes the observation. No images are shown or retained. The browser test
submits a bounded synthetic camera-summary event and verifies the displayed
confidence; this is a UI/API test, not camera hardware acceptance.
Commit `f4174d6` passed macOS, Ubuntu and Windows push CI in [40815574599](https://github.com/sujanmj/aura-companion/actions/runs/40815574599) and pull-request CI in [40815578985](https://github.com/sujanmj/aura-companion/actions/runs/40815578985). All three preview artifacts were uploaded from the push run. The first PR Windows browser attempt timed out in an unrelated Setup-tab click; rerunning the job passed.

## 2026-10-29 continuation — configurable solo follow-up window (Phase 9)

The Mac preview lets the owner choose a 15, 30 or 60-second window for one
follow-up after a direct reply. Solo follow-ups remain off until explicitly
enabled for the current ambient session; AURA does not identify who is speaking.
Pause, sleep and closing the window revoke the invitation. Native tests cover
all supported timeout boundaries. Local native lifecycle/speech tests, frontend
build and lint passed. Commit `1e2d03e` passed macOS, Ubuntu and Windows push CI
in [40888876555](https://github.com/sujanmj/aura-companion/actions/runs/40888876555)
and pull-request CI in
[40888888652](https://github.com/sujanmj/aura-companion/actions/runs/40888888652).
The push run uploaded all three preview archives. No acoustic acceptance is
claimed.

## 2026-10-29 continuation — interrupt local speech (Phase 9)

The Mac helper now has a Stop speaking button. It stops local speech while
leaving an active ambient session running and resumes local transcription; if
AURA was speaking a check-in with sensors off, the sensors stay off. Playback
generation invalidation prevents an old speech completion from changing the
state of a later turn. Local checks passed: 91 Python tests, 23 Node tests, all
18 browser tests, native lifecycle/speech tests, frontend build/lint and an
ad-hoc signed Mac app build. Commit `6dc3bf6` passed macOS, Ubuntu and Windows
pull-request CI in
[40900351981](https://github.com/sujanmj/aura-companion/actions/runs/40900351981),
which uploaded all three preview archives. The push run passed Ubuntu and
Windows in [40900342769](https://github.com/sujanmj/aura-companion/actions/runs/40900342769);
its macOS job remained queued when this evidence was recorded. No acoustic
interruption acceptance is claimed.

## 2026-10-29 continuation — temporary invited group exchange (Phase 10)

The shared contribution panel now supports up to three short question-and-answer
pairs in one page session. Every new question requires fresh agreement from the
group and sends the displayed exchange plus the new question to the configured
provider. The exchange stays in browser page state, is excluded from AURA's
memory and saved chat history, and can be cleared; a refresh also clears it.
The provider may retain requests under its own policy. Server validation limits
the exchange to six alternating messages, caps each question and reply at 4,000
characters, and rejects malformed histories before provider access. Provider
prompts label the entire transcript as untrusted content and prohibit
private-memory access, identity inference, and tools. Online lookup remains
disabled for this path.

Commit `fab9f3b` passed macOS, Ubuntu and Windows push CI in
[40903186466](https://github.com/sujanmj/aura-companion/actions/runs/40903186466)
and pull-request CI in
[40903197339](https://github.com/sujanmj/aura-companion/actions/runs/40903197339).
Both runs uploaded all three preview archives. The first browser run used stale
built assets and failed on the old button label; rebuilding and rerunning passed.
A follow-up caps provider replies at 4,000 characters, so they fit in the next
turn's bounded history. Local verification after that fix: 93 Python tests, 23
Node tests, all 18 browser tests, frontend lint and production build pass. The
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
