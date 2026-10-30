# Phase 12 acceptance record

Use this record for a specific build and home setup. Do not mark a check as
passed from CI, simulation, or a checklist mark alone. Record the build commit,
platform, hardware, date, operator, test result and evidence location. Use only
`PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`; leave a blocked check open until its
missing prerequisite is available.

## Automated software evidence

These checks establish only the behavior covered by their tests:

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
  Future-dated heartbeats now report offline and cannot start or validate a
  room claim. The 96 app Python tests, 30 Node tests, 18 browser E2E tests,
  lint and build pass locally. Push run
  [41024839694](https://github.com/sujanmj/aura-companion/actions/runs/41024839694)
  passed on all three platforms and uploaded every preview artifact. PR run
  [41024846598](https://github.com/sujanmj/aura-companion/actions/runs/41024846598)
  passed on Mac and Ubuntu; a Windows rerun is in progress after its first job
  was cancelled. A first Mac run exceeded the whole-test timeout under runner
  load; its retry passed. No physical node or room playback is claimed.
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
