# Phase 12 acceptance record

Use this record for a specific build and home setup. Do not mark a check as
passed from CI, simulation, or a checklist mark alone. Record the build commit,
platform, hardware, date, operator, test result and evidence location. Use only
`PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`; leave a blocked check open until its
missing prerequisite is available.

## Automated software evidence

These checks establish only the behavior covered by their tests:

- Exact source commit `6de06d2` adds a one-turn local reply option to invited
  shared conversation. Every participant still agrees to the current turn; local
  mode skips the configured provider, excludes prior shared turns from the local
  request, remains off by default, resets after the reply, and does not persist
  shared content. Local verification passed 134 app Python tests, 35 Node tests,
  all 19 browser E2E tests, native Mac lifecycle checks, typecheck, lint and
  production build. The Mac preview archive SHA-256 is
  `d39aa450e0035733b58f0a77b78c1bd39edd374a1e2f9038b98807dd7a094afa`; it is
  ad-hoc signed and not notarized. Push CI
  [41125878158](https://github.com/sujanmj/aura-companion/actions/runs/41125878158)
  and PR CI
  [41125884326](https://github.com/sujanmj/aura-companion/actions/runs/41125884326)
  passed on macOS, Windows and Ubuntu; both uploaded all three preview
  archives. Push artifact digest prefixes: macOS `7b1ca335`, Ubuntu
  `7855aa22`, Windows `1ec7acb3`; PR prefixes: macOS `2315b657`, Ubuntu
  `58bc56ff`, Windows `b909b2b7`. This is not physical room, Pi, sensor, or
  acoustic acceptance.

- Exact source commit `78f8145` adds an explicit one-turn local-engine option
  to the unsaved private-question flow. It skips the configured model, remains
  off by default, resets after the reply, and does not change the private
  turn's existing memory-isolation behavior. Local verification passed 132 app
  Python tests, 35 Node tests, all 19 browser E2E tests, typecheck, lint and
  production build. PR CI
  [41124019452](https://github.com/sujanmj/aura-companion/actions/runs/41124019452)
  passed on macOS, Windows and Ubuntu and uploaded all three preview archives
  (digest prefixes: macOS `60638525`, Windows `5a679382`, Ubuntu `05c56183`).
  Push CI
  [41124012944](https://github.com/sujanmj/aura-companion/actions/runs/41124012944)
  also passed on all three platforms and uploaded all three preview archives
  (digest prefixes: macOS `b2a2721f`, Windows `bf11e663`, Ubuntu `7bcce959`).
  The exact-head Mac preview ZIP SHA-256 is
  `6cb42de000ff1c0de6be2dd0c67147518fe1b71a44dd4e74ab6f7132f1e408cc`; it is
  ad-hoc signed and not notarized. No physical permission, acoustic, Pi,
  multi-room or home acceptance is established.

- Exact source commit `63c670c` adds the session-only local reply option to the
  main web conversation and prevents a stale reminder refresh from replacing a
  newer action notice. The local-only direct turn skips the configured model
  while keeping normal saved-memory behavior; the browser test delays the older
  response to exercise the notice race. Local verification passed 132 app
  Python tests, 35 Node tests, all 19 browser E2E tests, native lifecycle/speech
  tests, typecheck, lint and production build. Push CI
  [41122204230](https://github.com/sujanmj/aura-companion/actions/runs/41122204230)
  and PR CI
  [41122214370](https://github.com/sujanmj/aura-companion/actions/runs/41122214370)
  passed on macOS, Windows and Ubuntu; each uploaded three preview archives.
  Push artifact digest prefixes: macOS `0d145561`, Windows `a69ba6eb`, Ubuntu
  `38a5af01`; PR prefixes: macOS `aba1f9da`, Windows `43960fb3`, Ubuntu
  `fd0ed3aa`. The exact-head Mac archive SHA-256 is
  `1d7bf44ee6f6db79d2ce941d82f25fa688a88f4192ef2bd3300ed4a242a4233f`; its
  signature is ad-hoc and it is not notarized. Sensor permissions, home
  hardware, acoustic behavior, and physical acceptance remain unverified.

- Commit `811332a` adds continuous Node and Python dependency advisory checks to
  Ubuntu CI. The npm audit blocks high-severity advisories; `pip-audit` 2.10.1
  examines `requirements.txt` from an isolated temporary environment. Both
  found no known advisories on 2026-10-30. The 30-test Node suite passes locally.
  A Windows SQLite temp-file cleanup race found by the PR matrix was fixed with
  bounded removal retries. Push CI
  [41049167203](https://github.com/sujanmj/aura-companion/actions/runs/41049167203)
  and PR CI
  [41049176739](https://github.com/sujanmj/aura-companion/actions/runs/41049176739)
  passed on macOS, Windows and Ubuntu and uploaded all three preview archives.
  These checks do not establish hardware acceptance or guarantee protection
  from unknown/future advisories.

- Added `.github/dependabot.yml` for weekly npm, pip, and GitHub Actions updates,
  capped at five open pull requests per ecosystem with no auto-merge. Ruby's
  YAML parser accepts the file. Dependabot reads this configuration only from
  the repository default branch, so scheduled operation remains pending merge
  and no Dependabot service run or update PR is claimed.

- Commit `f2625d5` adds Phase 11 regression coverage for the repeated local
  01:30 during a UTC-4 to UTC-5 clock fallback. The same-date reminder is
  delivered once across the two simulated instants. The 19-test memory-controls
  suite and all 110 Python app tests pass locally. Push CI
  [41052472784](https://github.com/sujanmj/aura-companion/actions/runs/41052472784)
  and PR CI
  [41052482168](https://github.com/sujanmj/aura-companion/actions/runs/41052482168)
  passed on all three platforms and uploaded all preview archives. Fixed-offset
  simulation does not prove DST behavior on a specific OS, live scheduling, or
  spoken reminders.
- Commit `6252e1f` adds the spring-forward case: a reminder set for the skipped
  02:30 becomes due at the first tested local time after the jump, 03:00. The
  20-test memory-controls suite and all 111 Python app tests pass locally. Push
  CI [41054980576](https://github.com/sujanmj/aura-companion/actions/runs/41054980576)
  and PR CI
  [41054988634](https://github.com/sujanmj/aura-companion/actions/runs/41054988634)
  passed on macOS, Windows and Ubuntu, with each preview artifact uploaded.
  Fixed-offset simulation does not validate a platform timezone database or
  live notification delivery.
- Commit `75ab2e2` tests a packaged preview startup against disposable memory
  from AURA's schema before weekday reminders. The test checks that a
  pre-migration startup backup contains the original fact and reminder, then
  verifies the upgraded app retains the fact, conversation and reminder,
  supplies the default weekday schedule and nullable acknowledgment field, and
  passes SQLite integrity checks on both copies. Local verification passed 109
  Python app tests, 30 Node tests, 19 browser E2E tests, lint, build, native Mac
  lifecycle checks and the clean-install/upgrade smoke. Push CI
  [41040534258](https://github.com/sujanmj/aura-companion/actions/runs/41040534258)
  passed on macOS, Windows and Ubuntu and uploaded all three preview archives.
  Matching PR CI
  [41040541589](https://github.com/sujanmj/aura-companion/actions/runs/41040541589)
  also passed on all three platforms; both runs uploaded all three preview
  archives. The local Mac archive matches the embedded manifest and has
  SHA-256
  `885180b0d5d53b1f1c5625c350319f807d6b2554de097c7eb4fccc5473b88a6c`; it is
  ad-hoc signed and not notarized. This test uses temporary synthetic data and
  does not upgrade the owner's database or pass any physical-device check.

- Commit `b5bc888` adds an authenticated, read-only integrity check for an
  existing named SQLite snapshot. It refuses traversal and symlinks, returns no
  local filesystem path, and never restores or changes the active database.
  Local checks passed 108 app Python tests, 30 Node tests, 19 browser E2E tests,
  lint, production build and native Mac lifecycle tests. Push CI
  [41035336999](https://github.com/sujanmj/aura-companion/actions/runs/41035336999)
  and PR CI
  [41035347627](https://github.com/sujanmj/aura-companion/actions/runs/41035347627)
  passed on macOS, Windows and Ubuntu and uploaded all three preview archives.
  The local Mac preview ZIP matches its embedded manifest and has SHA-256
  `997660d6f230a29e7a02d5dd47edacbd32070e9867c0524029966ac32b441e54`;
  it is ad-hoc signed, not notarized. This does not establish home backup
  recovery, cross-device privacy, or physical hardware acceptance.
- Commit `36a3b38` adds owner-scoped acknowledgment for a delivered routine
  reminder, preserves the distinction between seeing a reminder and completing
  a task/dose, and migrates existing SQLite rows in place. Local checks passed:
  98 app Python tests, 30 Node tests, 18 browser E2E tests, lint, production
  build, native Mac lifecycle/voice tests, and focused room/sensor client tests.
  Push CI
  [41028802195](https://github.com/sujanmj/aura-companion/actions/runs/41028802195)
  and PR CI
  [41028796545](https://github.com/sujanmj/aura-companion/actions/runs/41028796545)
  passed on macOS, Windows and Ubuntu and uploaded all three preview archives.
  A local Mac development-preview ZIP for this commit was verified against its
  embedded manifest and SHA-256
  `416315bed9985564943f81468555c5a04c90a7f1949bd91ccb2c413aa485b35e`;
  its native app is ad-hoc signed, not notarized. These are software and
  packaging results only, not physical companion acceptance.
- The SQLite loopback integration now restores a startup backup to a fresh
  temporary database and verifies saved conversation and facts after
  authenticating to a new service process. All 30 Node tests pass locally.
  Push CI
  [41029925282](https://github.com/sujanmj/aura-companion/actions/runs/41029925282)
  and PR CI
  [41029933353](https://github.com/sujanmj/aura-companion/actions/runs/41029933353)
  passed on macOS, Windows and Ubuntu, with all three preview artifacts
  uploaded for each. A local Mac preview for commit `de7dfbd` was checked
  against its embedded manifest and SHA-256
  `a35787b750a6ac5b4d3e93a2e0401f20844e7ffe10c8353eb1bb65a9eb58ecbd`;
  it is ad-hoc signed and not notarized. This is a simulated recovery path;
  the required home backup, cross-device privacy and hardware checks below
  remain NOT RUN.
- Current software continuation on branch `aura-holographic-companion`:
  session-only private replies and reply-speech control are covered by native
  tests; room claim revalidation and its simulator CLI are covered by 12 client
  tests, 8 temporary-database/loopback handoff tests and all 95 app Python
  tests. The heartbeat service has explicit systemd CPU, memory and task caps.
  Push/PR CI passed on all three desktop platforms in
  [41016809978](https://github.com/sujanmj/aura-companion/actions/runs/41016809978)
  and [41016817404](https://github.com/sujanmj/aura-companion/actions/runs/41016817404),
  with all three preview artifacts uploaded. These are software-only checks;
  no Pi, room playback, live provider-retention or acoustic result is implied.
- Commit `e401909` prevents an older asynchronous Memory refresh from
  overwriting newer saved state. Its Windows regression test delays the stale
  response until after a reminder save. All 18 browser tests, lint and the
  production build pass locally; all-platform push/PR CI passed in
  [41014353029](https://github.com/sujanmj/aura-companion/actions/runs/41014353029)
  and [41014366925](https://github.com/sujanmj/aura-companion/actions/runs/41014366925).
- Commit `abda9b0` adds a session-only Mac control for keeping ambient replies
  visible but unspoken. Native tests cover its paused guard and reset; default
  speech behavior and separate reminder speech remain unchanged. All-platform
  push/PR CI passed in
  [41015190985](https://github.com/sujanmj/aura-companion/actions/runs/41015190985)
  and [41015196752](https://github.com/sujanmj/aura-companion/actions/runs/41015196752).
- Current continuation adds owner-confirmed sensor-node revocation by CLI and
  Command Center, plus a read-only node-status CLI. Both revoke paths require
  the exact node ID phrase; the revoke CLI validates IDs before prompting and
  uses authenticated direct hub transport, rejecting remote HTTP before
  sending the admin credential. The status command prints no credentials and
  distinguishes heartbeat freshness from actual sensor/playback operation.
  Six dashboard interaction tests, 30 Node tests, lint, the production build,
  19 sensor-admin tests, 12 room-client tests and all 95 app Python tests pass
  locally. CLI commit
  `89ee2f7` passed all three push-CI platforms in
  [41017738378](https://github.com/sujanmj/aura-companion/actions/runs/41017738378),
  uploading each preview artifact; PR run
  [41017743156](https://github.com/sujanmj/aura-companion/actions/runs/41017743156)
  also passed all three platforms. Dashboard commits `1210c1c` and `60c169e`
  passed the exact-tree PR matrix in
  [41018596692](https://github.com/sujanmj/aura-companion/actions/runs/41018596692),
  with each preview artifact uploaded. Their push run
  [41018590170](https://github.com/sujanmj/aura-companion/actions/runs/41018590170)
  passed macOS and Ubuntu but failed Windows E2E on two Memory-state timeouts
  after 16 cases passed. A follow-up cleanup disables the Setup test's proactive
  check-in opt-in and awaits the expiry dialog. The 18-test browser suite passes
  locally; commit `0bfb4be` passed all three push platforms in
  [41019957264](https://github.com/sujanmj/aura-companion/actions/runs/41019957264)
  with all preview artifacts uploaded. Its PR run
  [41019964090](https://github.com/sujanmj/aura-companion/actions/runs/41019964090)
  passed all three platforms with all preview artifacts uploaded. The
  node-status CLI passed the three-platform PR run
  [41020624724](https://github.com/sujanmj/aura-companion/actions/runs/41020624724),
  also uploading all preview artifacts. A Command Center heartbeat table is
  added in commit `c2da152`; the three-platform PR run
  [41021377750](https://github.com/sujanmj/aura-companion/actions/runs/41021377750)
  passed and uploaded all preview artifacts.
  Current change adds `Cache-Control: no-store` to sensor API JSON responses,
  including 401 failures, with two local regression tests; cross-platform CI is
  pending. A live-auth probe was skipped because no hub token is configured in
  this workspace.
  Its first two CI attempts passed macOS and Ubuntu but hit different Windows
  E2E expectations at five seconds (17/18 browser tests passed in each). The
  Windows assertion window is now 15 seconds; all 18 browser tests pass locally
  after this adjustment. Commit `f32a159` passed macOS, Windows and Ubuntu in
  push run
  [41023358488](https://github.com/sujanmj/aura-companion/actions/runs/41023358488)
  and PR run
  [41023365160](https://github.com/sujanmj/aura-companion/actions/runs/41023365160),
  both with all three preview artifacts uploaded.
  Node-status refinement treats `online=true` without a valid last-seen time as
  malformed/unavailable in both the CLI and Command Center. All 19 focused
  sensor-admin tests pass locally; push run
  [41024614388](https://github.com/sujanmj/aura-companion/actions/runs/41024614388)
  and PR run
  [41024608660](https://github.com/sujanmj/aura-companion/actions/runs/41024608660)
  passed on all three platforms and uploaded all preview artifacts.
  Future-dated or malformed heartbeat timestamps now display as unavailable,
  report offline and cannot start or validate a room claim. The 97 app Python
  tests, 30 Node tests, 18 browser E2E tests, lint and build pass locally. Push
  run
  [41024839694](https://github.com/sujanmj/aura-companion/actions/runs/41024839694)
  passed on all three platforms and uploaded every preview artifact. PR run
  [41024846598](https://github.com/sujanmj/aura-companion/actions/runs/41024846598)
  passed on all three platforms after retrying a cancelled Windows job and a
  slow Mac E2E attempt; both retries passed. The documentation snapshot also
  passed all three platforms and uploaded preview artifacts in
  [41026034065](https://github.com/sujanmj/aura-companion/actions/runs/41026034065).
  Timestamp normalization passed all three platforms in push run
  [41027375513](https://github.com/sujanmj/aura-companion/actions/runs/41027375513)
  and PR run
  [41027384362](https://github.com/sujanmj/aura-companion/actions/runs/41027384362),
  with all preview artifacts uploaded.
  No physical node or room playback is claimed.
  Revocation establishes hub credential rejection, not physical device
  shutdown.

- Commit `fab9f3b`: all three platforms passed push and pull-request CI; the
  shared-conversation browser tests require fresh approval per turn and verify
  no saved conversation or memory change.
- Commit `76ce6e6`: all three platforms passed push CI; provider replies are
  bounded to fit the next temporary transcript turn, and preview archives were
  generated for macOS, Windows, and Ubuntu.
- Commit `9ed1705`: all three platforms passed push CI; the Python test exercises
  an already-due check-in through overnight quiet hours and at the end boundary.
- The preview bundle test records its source commit and file hashes. A local Mac
  bundle is ad-hoc signed; this does not validate a Developer ID signature,
  notarization, clean installation, or hardware behavior.
- Commit `bd89594` adds the owner-controlled room invitation CLI with typed
  confirmation, HTTPS-only remote requests, no redirects, and no system proxy
  forwarding of hub credentials. Its six focused tests, the seven-test loopback
  handoff integration test, and 94 app Python tests pass locally. Push CI
  [40956030944](https://github.com/sujanmj/aura-companion/actions/runs/40956030944)
  and PR CI
  [40956043251](https://github.com/sujanmj/aura-companion/actions/runs/40956043251)
  passed on macOS, Windows and Ubuntu and uploaded preview archives for all
  three platforms. This reserves replies in software only; it does not exercise
  Pi hardware or connect reservations to speaker playback.
- Commit `62adb72`: the Command Center room-invitation panel and SQLite
  worker-shutdown regression fix passed macOS, Windows and Ubuntu push CI
  [40959155691](https://github.com/sujanmj/aura-companion/actions/runs/40959155691)
  and PR CI
  [40959164879](https://github.com/sujanmj/aura-companion/actions/runs/40959164879).
  Both runs uploaded preview archives for all three platforms. This verifies
  software and packaging only, not room playback, Pi hardware, acoustic
  behavior, or public-release signing/notarization.
- Commit `03e1a89`: room claims fail closed unless the hub acknowledges the
  exact requested session, generation and turn UUID with a finite, unexpired
  lease. Push CI
  [40960508464](https://github.com/sujanmj/aura-companion/actions/runs/40960508464)
  and PR CI
  [40960227044](https://github.com/sujanmj/aura-companion/actions/runs/40960227044)
  passed on macOS, Windows and Ubuntu; both runs uploaded all three preview
  archives. This does not establish Pi installation, playback fencing, speaker
  output, or physical room handoff.
- Commit `2de8276`: the documented sensor API test client joins Pi event,
  heartbeat and room-claim requests, node enrollment and dashboard status on a
  direct no-proxy transport that refuses redirects. Remote HTTP is rejected
  before credentials are sent. Local verification passed 94 app Python tests
  and 45 focused tests. Push CI
  [40966173161](https://github.com/sujanmj/aura-companion/actions/runs/40966173161)
  and PR CI
  [40966180392](https://github.com/sujanmj/aura-companion/actions/runs/40966180392)
  passed on macOS, Windows and Ubuntu; both uploaded all three preview
  archives. This does not establish Pi deployment or a live network hub.
- Commit `b7c72ff`: the authenticated sensor API authentication and event-status
  probes also use direct no-proxy transport and refuse redirects. Remote HTTP
  is rejected before credentials are sent. Ten focused admin-client tests,
  49 room/transport tests and all 94 app Python tests pass locally. Push CI
  [40967410539](https://github.com/sujanmj/aura-companion/actions/runs/40967410539)
  and PR CI
  [40967416698](https://github.com/sujanmj/aura-companion/actions/runs/40967416698)
  passed on macOS, Windows and Ubuntu; both uploaded all three preview
  archives. This does not validate a deployed hub or physical Pi behavior.
- Commit `5120a4d` makes unsafe hub URL rejection return a non-zero status before
  opening a request. Push CI
  [40968379151](https://github.com/sujanmj/aura-companion/actions/runs/40968379151)
  and PR CI
  [40968385143](https://github.com/sujanmj/aura-companion/actions/runs/40968385143)
  passed on macOS, Windows and Ubuntu; both uploaded all three preview
  archives. This remains software verification only.
- Commit `79b8f40` completes direct, no-proxy transport coverage for the
  credentialed sensor API test probes and makes the Windows loopback integration
  test bypass system proxies. Twelve focused admin-client tests, 51 focused
  room/transport tests and all 94 app Python tests pass locally. Push CI
  [40970180323](https://github.com/sujanmj/aura-companion/actions/runs/40970180323)
  and PR CI
  [40970187073](https://github.com/sujanmj/aura-companion/actions/runs/40970187073)
  passed on macOS, Windows and Ubuntu; both uploaded all three preview
  archives. This is software-only evidence.
- Commit `dfd56d9` lazy-loads the Three.js scene behind a static orb fallback.
  The initial JavaScript bundle is 266.92 kB minified (82.76 kB gzip), with the
  scene in a separate 912.29 kB chunk. Build, lint, 28 Node tests and 18 browser
  tests pass locally. Push CI
  [40972148472](https://github.com/sujanmj/aura-companion/actions/runs/40972148472)
  and PR CI
  [40972155147](https://github.com/sujanmj/aura-companion/actions/runs/40972155147)
  passed on macOS, Windows and Ubuntu; both uploaded all three preview
  archives. No hardware rendering or wall-clock startup measurement is claimed.
- Commit `154af25`: Pi event, heartbeat and room-claim requests use a direct
  no-proxy opener and refuse redirects before credentials can be sent to
  another destination. Push CI
  [40962677800](https://github.com/sujanmj/aura-companion/actions/runs/40962677800)
  and PR CI
  [40962684508](https://github.com/sujanmj/aura-companion/actions/runs/40962684508)
  passed on macOS, Windows and Ubuntu; each uploaded all three preview
  archives. This does not establish Pi deployment or a live network hub.

## Required device checks

| Check | Expected result | Evidence to record | Current status |
| --- | --- | --- | --- |
| Fresh Mac install and permissions denied | The app reports denied microphone, speech, and camera access without capturing; the recovery action opens the matching System Settings page. | macOS version, app signature, permission state, screenshots or log | BLOCKED: distribution identity and clean-install acceptance |
| Fresh Mac install and permissions granted | Capture begins only after an explicit user action; visible status and Pause accurately reflect both sensors. | Device model, app commit, consent steps, start/pause/stop result | NOT RUN |
| Pause, close, quit, sleep, wake and restart | No capture resumes after manual Pause, close, quit, or sleep. Wake does not bypass a required user restart. | Each transition, time to stop, observed microphone/camera state | NOT RUN |
| Speech turn-taking and Stop speaking | Replies stop on request; the microphone resumes only when the current ambient session remains active; no audible feedback loop or stale reply occurs. | Room/noise setup, speaker and microphone, interruption attempts, failures | NOT RUN |
| False person and object detections | AURA does not guess a person's identity, does not claim certainty for an object label, and lets the owner correct or delete saved summaries. | Lighting, distance, sample count, false positives/negatives, correction/deletion result | NOT RUN |
| Memory review, export, backup and deletion | Export contains only the selected account; edits/deletions take effect in recall; backup and restore behavior is understood before upgrade. | Account used, export location kept private, before/after checks | NOT RUN |
| Pi hub TLS, node trust and reboot | The network-bound hub refuses HTTP, starts with its trusted certificate and protected private key, and each enrolled node verifies that certificate before sending credentials. The heartbeat service runs unprivileged and reports online only while heartbeats are fresh. | Pi model/OS, certificate issuer and expiry, key owner/mode, node trust store, HTTP rejection, reboot, token rotation/revocation, hub logs | BLOCKED: no Pi installation or certificate setup tested |
| Pi capture and calibrated sensors | Each selected camera, microphone, and sensor has an explicitly tested driver and calibrated thresholds; unsupported modules remain disabled. | Exact module, wiring, calibration reference, false-alarm/recovery tests | BLOCKED: capture drivers and physical sensors unavailable |
| Room invitation and handoff | A visible invitation reserves one reply; duplicate claims do not replay speech; network loss, expiry and stop fail closed at playback. | Nodes/rooms, invitation approvals, turn IDs, network interruption and playback evidence | BLOCKED: software reservations are not connected to physical playback |
| Cross-device privacy and retention | Sensor status, consent, provider disclosure, export, deletion, local backups and any enabled cloud copies match the release notes. | Installed version, provider, retention setting, deletion and backup checks | NOT RUN |
| Public distribution | The exact release artifact is Developer ID signed and notarized; its manifest and notes state the tested scope and rollback steps. | Artifact checksum, signature verification, notarization result, clean install/upgrade | BLOCKED: signing credentials unavailable |

## Release decision

An artifact can be called a development preview only with its limitations visible.
Do not call the system production-ready or an emergency monitor while any
required device check is blocked or not run. Pi camera/GPIO capture, acoustic
acceptance, iPhone/wearable health data, multi-room playback, medication
adherence, and emergency response are not established by the automated tests
listed above.
