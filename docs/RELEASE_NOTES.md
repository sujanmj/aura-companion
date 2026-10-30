# AURA development preview — 2026-10-30

## Continuous dependency advisories (Phase 12)

Ubuntu CI checks the locked npm dependency tree for high-severity or greater
advisories and audits the Python requirements using `pip-audit` in an isolated
temporary environment. The local checks reported no known advisories on
2026-10-30. Commit `811332a` passed push CI
[41049167203](https://github.com/sujanmj/aura-companion/actions/runs/41049167203)
and PR CI
[41049176739](https://github.com/sujanmj/aura-companion/actions/runs/41049176739)
on macOS, Windows and Ubuntu; both runs uploaded preview artifacts for all
three platforms. A Windows SQLite cleanup race found during an earlier PR run
was fixed with bounded file-removal retries and passed in the final matrix.
These checks do not guarantee that future or unknown dependency vulnerabilities
are absent.

## Scheduled dependency updates (Phase 12)

Added weekly Dependabot checks for npm, Python requirements, and GitHub Actions,
with a five-PR limit per ecosystem and no automatic merging. The manifest parses
locally. GitHub only activates Dependabot from the default branch, so this
configuration will take effect after the development branch is merged; no
scheduled update run is claimed yet.

## Reminder daylight-saving fallback test (Phase 11)

Added a regression test ensuring a selected local reminder does not repeat when
the clock's 01:30 occurs twice during a UTC-4 to UTC-5 fallback. All 110 Python
app tests pass locally. Commit `f2625d5` passed push CI
[41052472784](https://github.com/sujanmj/aura-companion/actions/runs/41052472784)
and PR CI
[41052482168](https://github.com/sujanmj/aura-companion/actions/runs/41052482168)
on macOS, Windows and Ubuntu with all preview artifacts uploaded. The test
simulates the two offsets; it does not establish platform timezone, live timer,
or acoustic acceptance.

A second regression covers the spring-forward gap: a 02:30 reminder becomes
due at 03:00 local time after the skipped hour. All 111 Python app tests pass
locally; push run
[41054980576](https://github.com/sujanmj/aura-companion/actions/runs/41054980576)
and PR run
[41054988634](https://github.com/sujanmj/aura-companion/actions/runs/41054988634)
passed on macOS, Windows and Ubuntu and uploaded preview artifacts. Both clock
transitions are fixed-offset simulations; they do not prove a platform's DST
rules or real-device delivery.

## Reminder IANA timezone data for Windows CI (Phase 11)

Added pinned test-only `tzdata==2026.6` (`requirements-test.txt`) so the
America/New_York ZoneInfo reminder DST regression can execute on Windows CI
rather than skip for missing system timezone data. AURA runtime dependencies
are unchanged. The Ubuntu dependency-audit job now audits the test
requirements alongside `requirements.txt`, and CI installs the test pin before
Python unit tests. Local verification passed: the focused New York DST test,
all 21 memory-controls tests, all 112 Python app tests, 30 Node tests, lint,
production build, and browser E2E (19/19). `pip-audit` found no known
vulnerabilities in both requirement files. PR run
[41065495500](https://github.com/sujanmj/aura-companion/actions/runs/41065495500)
passed on macOS, Windows and Ubuntu and uploaded all three preview archives.
Windows installed the pin and ran all 112 Python tests; its three skips were
the POSIX-only symlink checks, so the IANA timezone regression ran. No
physical reminder delivery is claimed.

## Existing-memory upgrade smoke (Phases 6 and 12)

The extracted preview is now tested against a synthetic database created from
AURA's schema immediately before weekday reminder scheduling was introduced.
The check verifies that its startup backup retains the original fact and
reminder before migration, and that startup preserves the fact, conversation
and reminder while adding the reminder schedule and acknowledgment fields. It
also verifies backup and upgraded-database integrity, local-only provider
mode, disabled external actions and authentication. The test uses temporary
files only; no configured home database is opened or changed.

Local checks passed 109 Python app tests, 30 Node tests, 19 browser E2E tests,
lint, build, native Mac lifecycle tests and the packaged clean-install/upgrade
smoke. The Node and Python dependency audits reported no known vulnerabilities
for the resolved trees on 2026-10-30. Commit `75ab2e2` passed all three
platforms in push run
[41040534258](https://github.com/sujanmj/aura-companion/actions/runs/41040534258)
and matching PR run
[41040541589](https://github.com/sujanmj/aura-companion/actions/runs/41040541589)
also passed on all three platforms; both uploaded all three preview archives.
The local Mac preview matches its embedded manifest and has
SHA-256 `885180b0d5d53b1f1c5625c350319f807d6b2554de097c7eb4fccc5473b88a6c`.
It is ad-hoc signed and not notarized. This software simulation does not
establish home upgrade, Pi, multi-room, emergency or hardware acceptance.

## Read-only backup verification (Phases 4 and 12)

Owners can check an existing local SQLite snapshot at any time without restoring
it or changing the active database. The check refuses invalid names and
symlinked files, opens the snapshot read-only, and displays whether SQLite's
integrity check passed. Automated verification passed 108 app Python tests, 30
Node tests, 19 browser E2E tests, lint, production build, and native Mac lifecycle
tests. Commit `b5bc888` passed push CI
[41035336999](https://github.com/sujanmj/aura-companion/actions/runs/41035336999)
and PR CI
[41035347627](https://github.com/sujanmj/aura-companion/actions/runs/41035347627)
on macOS, Windows and Ubuntu; both uploaded preview artifacts for all platforms.
The local Mac preview archive is tied to this commit, verified against its
embedded manifest, and has SHA-256
`997660d6f230a29e7a02d5dd47edacbd32070e9867c0524029966ac32b441e54`. It is
ad-hoc signed, not notarized. This remains software recovery evidence; home
restore and hardware acceptance are not claimed.

## Explicit local backup controls (Phases 4 and 12)

Memory lists local SQLite snapshots by timestamp and size, can create a verified
snapshot on request, and can remove a single selected copy after an explicit
warning. Automatic backups remain intact unless the owner selects one for
deletion; neither action replaces the active database. Creation uses SQLite's
online backup API and checks the copy with `quick_check`. POSIX snapshot files
are owner-readable/writable; Windows uses inherited directory ACLs. Backups
are not encrypted by this feature. Local checks passed 105 Python tests,
30 Node tests, 19 browser E2E tests, lint, and production build. Cross-platform
CI is pending; home recovery and physical-device acceptance are not claimed.

## Editable routine reminders (Phase 11)

Memory now lets the owner change a reminder's wording, local time, and selected
weekdays. The edit is owner-scoped and preserves its active/paused state and
the record of whether today's delivered occurrence was acknowledged or
dismissed, preventing a schedule edit from causing a second delivery that day.
Local verification passed 99 app Python tests, 30 Node tests, 18 browser E2E
tests, lint, and the production build. Cross-platform CI is pending; no
medication or health-device integration is implied.

## Reminder acknowledgment (Phase 11)

After a scheduled reminder is delivered, its owner can acknowledge that they saw
it or dismiss it for that day. Acknowledgment is limited to the delivered
occurrence and never records task or medication completion. The UI says this
explicitly; legacy SQLite databases migrate without replacing existing data.
This remains a general local reminder feature, not a medication tracker or
cross-device health integration.

Commit `36a3b38` passes 98 app Python tests, 30 Node tests, 18 browser tests,
lint, build and the native Mac lifecycle/voice tests. Its push run
[41028802195](https://github.com/sujanmj/aura-companion/actions/runs/41028802195)
and pull-request run
[41028796545](https://github.com/sujanmj/aura-companion/actions/runs/41028796545)
passed on macOS, Windows and Ubuntu with all three preview artifacts uploaded.
The local Mac preview archive is tied to that source commit and has SHA-256
`416315bed9985564943f81468555c5a04c90a7f1949bd91ccb2c413aa485b35e`; it is
ad-hoc signed, not notarized, and does not establish hardware acceptance.

## SQLite backup restore verification (Phase 12)

The temporary-database integration now restores a startup backup to a new
database after stopping the original service, then verifies saved conversation
and facts through a fresh authenticated AURA process. All 30 Node tests pass
locally. This confirms a simulated software recovery path, not a household
upgrade, cross-device restore or hardware result.
Push CI
[41029925282](https://github.com/sujanmj/aura-companion/actions/runs/41029925282)
and PR CI
[41029933353](https://github.com/sujanmj/aura-companion/actions/runs/41029933353)
passed on macOS, Windows and Ubuntu with all three preview artifacts uploaded.
The local Mac preview for source commit `de7dfbd` has SHA-256
`a35787b750a6ac5b4d3e93a2e0401f20844e7ffe10c8353eb1bb65a9eb58ecbd`; it is
ad-hoc signed and not notarized. No hardware acceptance is implied.

## 2026-10-30 — Owner-controlled sensor-node revocation

An owner can now revoke an enrolled node credential from the Command Center or
run `python scripts/revoke_sensor_node.py <node_id>`. Both paths require typing
the exact `REVOKE <node_id>` phrase. The CLI refuses remote HTTP and avoids
system proxies when sending the hub admin credential. Revoking disables that
credential and ends its active room invitation; it does not power down the node.
If a request response is lost, the Command Center blocks retries until status
is refreshed, while the CLI advises checking node status before retrying.

Six dashboard interaction tests, 30 Node tests, 19 sensor-admin tests, 12 room
client tests, all 95 app Python tests, 18 browser E2E tests, lint, production
build and a local preview bundle pass. The latest exact-tree PR workflow
[41018596692](https://github.com/sujanmj/aura-companion/actions/runs/41018596692)
passed on macOS, Windows and Ubuntu with all preview archives uploaded. The
matching push workflow [41018590170](https://github.com/sujanmj/aura-companion/actions/runs/41018590170)
passed macOS and Ubuntu but failed two Windows Memory E2E assertions. The
browser suite shared the check-in opt-in saved by an earlier setup test; a
follow-up now resets that preference and awaits the expiry confirmation. All
18 browser tests pass locally after that change. The follow-up commit
`0bfb4be` passed all three push-CI platforms in
[41019957264](https://github.com/sujanmj/aura-companion/actions/runs/41019957264),
with all preview archives uploaded; its PR run
[41019964090](https://github.com/sujanmj/aura-companion/actions/runs/41019964090)
passed all three platforms and uploaded the same preview archives. A new
read-only `python scripts/list_sensor_nodes.py` command now reports last-seen
and heartbeat freshness without printing credentials. Its 19 focused sensor
admin tests and the full Python suite pass locally. The three-platform PR run
[41020624724](https://github.com/sujanmj/aura-companion/actions/runs/41020624724)
passed and uploaded all preview archives. The Command Center now includes an
enrolled-node heartbeat table and marks online records without a valid last-seen
time as unavailable. Commit `c2da152` passed the three-platform PR
workflow in
[41021377750](https://github.com/sujanmj/aura-companion/actions/runs/41021377750),
which uploaded all preview archives. These results verify software only; Pi
installation and physical node shutdown are untested.

An inconsistent node record with `online=true` but no valid last-seen time is
now shown as unavailable in the CLI and Command Center. Future-dated heartbeat
or malformed heartbeat records are shown as unavailable and cannot pass a room
invitation or claim check. The 97
app Python tests, 30 Node tests, 19 sensor-admin tests, 18 browser E2E tests,
lint and production build pass locally. Push CI
[41024839694](https://github.com/sujanmj/aura-companion/actions/runs/41024839694)
passed on all three platforms and uploaded preview artifacts. The matching PR
run [41024846598](https://github.com/sujanmj/aura-companion/actions/runs/41024846598)
passed on all three platforms after retrying the slow Mac E2E case and a
cancelled Windows job; both retries passed. The documentation snapshot also
passed its three-platform PR workflow and uploaded previews in
[41026034065](https://github.com/sujanmj/aura-companion/actions/runs/41026034065).
The timestamp normalization passed on all three platforms in push run
[41027375513](https://github.com/sujanmj/aura-companion/actions/runs/41027375513)
and PR run
[41027384362](https://github.com/sujanmj/aura-companion/actions/runs/41027384362);
both uploaded preview artifacts.
These checks do not establish a physical Pi or room-playback behavior.

The sensor API now tells HTTP caches not to store any JSON response, including
unauthorized errors. Header regression tests cover both success and auth-failure
responses. Local validation is green; cross-platform CI is pending. The live
hub-auth probe was skipped because no hub token is configured in this workspace.
The latest node-status validation passes all 19 focused sensor-admin tests
locally, including its inconsistent-record regression case; cross-platform CI
is pending. The first two CI attempts passed macOS and Ubuntu but timed out different
Windows E2E assertions at five seconds; each passed 17/18 browser cases. The
Windows-only expectation timeout is now 15 seconds, and the full browser suite
passes locally. Commit `f32a159` then passed all three platforms in push run
[41023358488](https://github.com/sujanmj/aura-companion/actions/runs/41023358488)
and PR run
[41023365160](https://github.com/sujanmj/aura-companion/actions/runs/41023365160),
both uploading macOS, Windows and Ubuntu preview archives.

## Observation expiry

Memory now offers an optional expiry policy for saved observations and event
notes, including corrected notes. Review the affected count and confirm before
saving. Existing installations keep notes until explicitly deleted by default.
Expired notes are removed before future recall or export when AURA processes a
request. Other accounts, facts, people and reminders are unaffected.

Backups and original chat messages remain and require separate management.
The feature does not enable sensors or external tools. Tests use temporary
SQLite databases, never the user's existing memory.

## Release scope

This remains an unsigned-for-distribution development preview (local Mac builds
use ad-hoc signing), not a notarized or production companion release. Developer
ID credentials, clean-install permission acceptance, rebuilt multi-hour soak,
sleep/wake and calibrated acoustics remain open. Pi capture, multi-room hardware,
iPhone/wearables and emergency-response acceptance are not established.

## Verification

Baseline: macOS and Ubuntu workflow 39900633505 passed at 0a121ba9.
New milestone: local Python 61/61, Node 12/12, native lifecycle/speech checks,
frontend build/lint, and ad-hoc Mac build passed. Browser tests passed 14/14. Expiry commit a451ef5 passed macOS and Ubuntu CI run 40680587802, with both preview artifacts uploaded. No hardware acceptance is implied by these checks.

## Upgrade and rollback

Stop the old service before upgrading. Keep the existing database and its
adjacent backups; startup makes a SQLite backup before applying additive schema.
Point AURA_DB_PATH at the same database. Rolling source back to 0a121ba9 leaves
the new retention table unused; it does not recover notes already expired.
Recover any required notes from a separately preserved backup with the service
stopped; never overwrite a running database or publish a private backup.

## Invited turns

Direct native requests now begin with AURA/Hey AURA. Optional solo follow-ups
admit one phrase within 30 seconds of the prior reply, default off and cleared by
Pause/sleep/close. The app does not identify speakers. Use this mode only with
nearby people's agreement; accepted solo turns enter the owner's normal memory.

A separate web form accepts one reviewed group question with fresh agreement.
It includes no saved personal context, starts no tools or sensors, and stores no
question/reply. Provider retention still applies. Pause the separate native
ambient helper before a group session. Automatic group capture is not included.

Local validation: Python 64/64, Node 12/12, browser 15/15, native tests, build/lint
and Mac ad-hoc build passed; invited-turn commit a5f3e12 passed macOS and Ubuntu CI run 40681826266.

## Preview integrity and dependency updates

Builds now record source-input hashes. Packaging rejects stale browser/native
builds, changed web output, dirty source trees, symlink inputs, tracked memory or
runtime files, SQLite contents and selected credential markers. Run the source
check after staging new files and before publishing. It is not a comprehensive
secret scanner. Each ZIP contains a manifest with its source commit and file
hashes; the adjacent SHA-256 verifies the ZIP itself. The manifest explicitly
separates local/ad-hoc signing from notarization and hardware acceptance.

The lockfile now uses body-parser 2.4.0 and fast-uri 3.1.9, addressing the upstream
[body-parser advisory](https://github.com/expressjs/body-parser/security/advisories/GHSA-27r3-jxmh-p828)
and [fast-uri advisory](https://github.com/fastify/fast-uri/security/advisories/GHSA-w74x-v6f9-j3xg).
The local npm audit reports zero known vulnerabilities as of 2026-10-28.
Native settings scroll with a fixed capture control; sensor acceptance is unchanged.

Local verification: Python 73/73, Node 12/12, browser 15/15, native tests, build/lint
and local ad-hoc Mac build passed. Nine packaging tests exercise actual archives
in temporary repositories. Release-integrity commit b3f3b58 passed both platform jobs in CI run 40683350586; both platform archives, checksums and manifests were uploaded.

## 2026-10-29 — reviewed online source checks

Conversation now includes “Check an online source”. Review a query, approve that
exact text and retrieve up to three English Wikipedia summaries with source
links, attribution and retrieval time. Editing clears approval. AURA sends no
saved memory, ambient transcript or provider credentials and saves no results.
The query is disclosed to Wikipedia, which may log requests. Cancel stops local
waiting but cannot retract data already sent. Clear removes displayed results.

This first adapter displays source excerpts, not independently verified facts or
a model-generated factual answer. It is not general web search or a live news,
medical or emergency service. Source failures do not produce an invented answer.
Network destinations are fixed, redirects refused, bodies/time bounded, and
source content cannot run code or tools. Optional conversation panels now have
bounded scrolling and open one at a time to preserve the main conversation.

Local tests: 73 Python, 20 Node, 17 browser; build/lint passed. One real public
Raspberry Pi query returned three cited summaries on 2026-10-29 IST. Commit
`3cfd416` passed macOS and Ubuntu CI run 40772617052 with both preview uploads. Source APIs follow the official
[MediaWiki search](https://www.mediawiki.org/wiki/API:Search) and
[Page Content Service](https://www.mediawiki.org/wiki/Page_Content_Service)
documentation and use an identifying User-Agent.

## 2026-10-29 — invited room reservation prototype

The enrolled-node hub now supports explicit five-minute room invitations,
approved transfers, stop/status and a node-authenticated reply reservation.
Stale generations, cross-owner nodes, offline destinations and duplicate turn
UUIDs fail closed. Rotating or revoking the active node clears its invitation.
Stop removes live session/claim metadata, which is also owner-scoped in export.

This API does not capture, speak, recall personal memory or infer location. A
reservation already returned cannot be recalled. Pi/Mac integration, physical
playback fencing and real multi-room acceptance remain unfinished. See the
[protocol and limitations](ROOM_HANDOFF.md). Local Python suite: 80/80, including
seven new protocol/race/HTTP tests using temporary databases. Node 20/20, browser
17/17, native lifecycle, lint and existing provider/cloud/heartbeat checks also
passed. Commit `0ff2985` passed macOS and Ubuntu CI run 40773910557; both
platform preview archives were uploaded.

## 2026-10-29 — Windows preview preparation

The source/web preview now chooses the appropriate default Python command,
respects an explicit interpreter path, and uses UTF-8 for memory IPC. Packaging
normalizes manifest/archive paths across platforms. Windows has been added to
CI alongside macOS and Linux. Commit `4c9b44a` passed all three platforms in
run 40774579580 with Linux and macOS preview uploads. PowerShell setup is documented
in the app README. No Windows native capture helper or signed installer is
included. Local Mac checks passed: 80 Python, 22 Node, 17 browser, build/lint and
ad-hoc native build. Real Windows devices and permissions remain untested.


## 2026-10-29 — local Ollama transport guard

The existing Ollama provider now accepts only HTTP on a numeric loopback address
and the `/api/generate` path. It does not follow redirects or use environment
HTTP proxies, so prompts remain on the local machine. `OLLAMA_URL` can select a
loopback port, and `OLLAMA_MODEL` is reflected in readiness. Prompts are capped
at 20,000 characters, response bodies at 1 MiB and returned text at 16,000
characters. Network, malformed or oversized responses fail closed to the existing
local fallback.

Four new tests use a disposable loopback HTTP server to cover Unicode, model
selection, rejected off-device URLs, redirects and size/parse failures. They do
not install or invoke an Ollama model. A live Ollama model check still requires
one installed on the user's Mac or Windows device. Commit `be8430e` passed
macOS, Ubuntu and Windows CI in run 40810170044 with preview packages.

## 2026-10-29 — weekday reminder schedules

Local reminders can now repeat on selected weekdays. Existing daily reminders
are preserved and migrate to all seven days. The schedule stays in local SQLite
and is delivered once per selected local date while AURA is running. This does
not confirm a task or dose, and includes no medication or health-data integration.
Commit `84b8e65` passed macOS, Ubuntu and Windows push CI in
[40811353403](https://github.com/sujanmj/aura-companion/actions/runs/40811353403)
and pull-request CI in
[40811359575](https://github.com/sujanmj/aura-companion/actions/runs/40811359575).
All three platform preview packages were uploaded by the push run.

## 2026-10-29 — cautious visual object hints

For a where-is question, AURA may offer a recent local scene estimate when
the requested item matches Vision's top label at 85% confidence or higher and
the observation is no more than 30 minutes old. It includes the saved time and
confidence, warns that the classification may be wrong or outdated, and does
not claim a room or exact location. An explicit user note takes priority.
Secondary labels and human-presence signals cannot answer object questions.
This software path uses saved summaries only; hardware vision accuracy is not
validated by automated tests. Commit `20c5bbc` passed macOS, Ubuntu and Windows
push CI in
[40813822187](https://github.com/sujanmj/aura-companion/actions/runs/40813822187)
and pull-request CI in
[40813827634](https://github.com/sujanmj/aura-companion/actions/runs/40813827634).
All three preview archives were uploaded from the push run.

Memory now displays the confidence stored with each Vision summary and clarifies
that the score applies to the top label only. Users can review that estimate
before correcting or deleting it. Browser validation uses a synthetic summary;
it does not test camera accuracy or hardware behavior. Commit `f4174d6` passed
macOS, Ubuntu and Windows push CI in
[40815574599](https://github.com/sujanmj/aura-companion/actions/runs/40815574599)
and pull-request CI in
[40815578985](https://github.com/sujanmj/aura-companion/actions/runs/40815578985).
The push run uploaded all three preview archives.

## 2026-10-29 — configurable solo follow-up window

With solo follow-ups explicitly enabled for the current Mac ambient session,
the owner can choose a 15, 30 or 60-second window for one phrase after a direct
reply. Pause, sleep and closing the window revoke the invitation. AURA cannot
identify the speaker, and accepted follow-up speech is saved in the owner's
conversation. Native timing tests, local app build and lint pass. Cross-platform
CI passed on macOS, Ubuntu and Windows in push run
[40888876555](https://github.com/sujanmj/aura-companion/actions/runs/40888876555)
and pull-request run
[40888888652](https://github.com/sujanmj/aura-companion/actions/runs/40888888652).
All three preview archives were uploaded by the push run. No acoustic test is
claimed.

## 2026-10-29 — interrupt local speech

The Mac helper now offers Stop speaking without pausing active microphone or
camera capture. It resumes local transcription after stopping; if a reminder is
spoken with sensors off, they stay off. Stale speech completion callbacks are
discarded so they cannot change the state of a later turn. Local native tests,
the app build, 91 Python tests, 23 Node tests, 18 browser tests, frontend build
and lint pass. Commit `6dc3bf6` passed macOS, Ubuntu and Windows pull-request CI
in [40900351981](https://github.com/sujanmj/aura-companion/actions/runs/40900351981),
which uploaded all three preview archives. Ubuntu and Windows push jobs passed
in [40900342769](https://github.com/sujanmj/aura-companion/actions/runs/40900342769);
the macOS push job remained queued when recorded. Acoustic interruption
acceptance remains pending.

The optional Ollama brain now accepts only a numeric loopback URL and fixed API
path. It bypasses proxy settings, never follows redirects, caps prompts/replies,
and exposes the selected `OLLAMA_MODEL` in setup readiness. Custom `OLLAMA_URL`
ports still have to be local. Tests used a temporary loopback server; no real
Ollama installation or model was available or claimed.

Conversation view adds an optional one-message private turn. After fresh approval,
AURA uses only that message and a temporary in-memory SQLite store. It skips
saved memories, extraction and persistent chat/cloud writes. The message and
reply stay in the current page until cleared or refreshed. The selected provider
receives the message and may have its own retention policy. This is not an
ongoing private chat. A regression in greeting matching was fixed so common
words containing “hi” no longer silently force local fallback. Local tests: 85
Python, 23 Node, 18 browser, native lifecycle, build and lint. Commit `3fa324e`
passed macOS, Ubuntu, and Windows push CI in run
[40810690005](https://github.com/sujanmj/aura-companion/actions/runs/40810690005)
and pull-request CI in
[40810695923](https://github.com/sujanmj/aura-companion/actions/runs/40810695923).
All three preview artifacts were uploaded from the push run.

## 2026-10-29 — temporary invited group exchange

The shared question panel can continue for up to three exchanges. Everyone must
agree again for each question, and AURA sends only the displayed shared
exchange and the newly reviewed question to the selected provider. The exchange
is temporary in the page and is absent from saved memory and chat history; the
provider may retain its request. It can be cleared at any time, and no online
lookup, microphone, camera or tools are started. Local verification passes 92
Python, 23 Node and 18 browser tests plus lint and production build. Commit
`fab9f3b` passed macOS, Ubuntu and Windows push CI in
[40903186466](https://github.com/sujanmj/aura-companion/actions/runs/40903186466)
and pull-request CI in
[40903197339](https://github.com/sujanmj/aura-companion/actions/runs/40903197339).
Both runs uploaded preview archives for all three platforms. A follow-up caps
shared provider replies at 4,000 characters so a long answer cannot break the
next turn's bounded transcript. Local Python, Node, browser, lint and production
build checks passed. The preview bundle manifest records the source commit,
Darwin platform, ad-hoc signing, and no notarization or hardware acceptance.
Commit `76ce6e6` passed all three push CI jobs in
[40904869469](https://github.com/sujanmj/aura-companion/actions/runs/40904869469),
which uploaded macOS, Windows and Ubuntu previews.

Phase 11 reminder verification now independently tests a due check-in across an
overnight quiet-hours interval and its exact end boundary. The 94-test Python
suite passes locally. Commit `9ed1705` passed all three push CI jobs in
[40906445069](https://github.com/sujanmj/aura-companion/actions/runs/40906445069),
with preview archives for macOS, Windows and Ubuntu. This does not establish
speaker, timezone or daylight-saving acceptance.

Phase 12 now has a device acceptance record in
[`PHASE_12_ACCEPTANCE.md`](PHASE_12_ACCEPTANCE.md), separating automated software
evidence from Mac, Pi, acoustic, multi-room, privacy and release-signing checks
that remain unrun or blocked.

Phase 9 native tests now cover repeated solo follow-up windows: each spoken AURA
reply renews one bounded window, supporting a short exchange without a repeated
wake phrase while the session-only opt-in remains active. Native tests and an
ad-hoc Mac app build pass locally. The Windows browser timeout increase passed
all PR platforms and Windows/Ubuntu push CI. An explicit heading wait resolves
a routine-test tab-navigation race. Commit `f12edab` passed all three push jobs
in [40914132493](https://github.com/sujanmj/aura-companion/actions/runs/40914132493)
and pull-request CI in
[40914144108](https://github.com/sujanmj/aura-companion/actions/runs/40914144108),
which uploaded preview archives for all three platforms. Acoustic acceptance
remains pending.

## 2026-10-30 — room reservations and sensor transport hardening

Enrolled Pi nodes can now make one explicit room-turn reservation using an
existing owner's invitation and a stable caller-provided UUID. The client fails
closed if the claim response is lost or rejected; it does not retry under a new
ID or start capture, generate speech, or play audio. Physical room handoff is
still not implemented.

Network-bound sensor hubs now require TLS 1.2 or newer and absolute regular
certificate/key files without symlinks in their paths. On POSIX systems the
private key cannot be group-writable or world-accessible. The Pi systemd hub
preflight applies the same checks. Remote node clients reject HTTP before
sending credentials; HTTP remains available for loopback development. Before
upgrading an existing network-bound hub, install a trusted certificate at
`/etc/aura/tls/server.crt` and a private key at `/etc/aura/tls/server.key`, make
the key readable by the `aura` account without world access, and install the
issuing CA in each node's trust store. The updated service intentionally refuses
to start without this configuration.

The Memory panel refreshes saved state when opened, and browser checks now wait
for the corresponding save/refresh. Commit `b5695ac` passed push CI in
[40952983216](https://github.com/sujanmj/aura-companion/actions/runs/40952983216)
and PR CI in
[40952990897](https://github.com/sujanmj/aura-companion/actions/runs/40952990897).
Both runs passed on macOS, Ubuntu and Windows and uploaded all three preview
archives. These are software and packaging checks only. Pi installation, TLS
certificate/trust setup, microphone/camera permissions, room playback, acoustic
quality, and Developer ID signing/notarization remain unverified or blocked.

The owner can now use `scripts/room_invitation.py` to inspect, start, transfer
and stop a five-minute room reservation. Mutating actions require exact typed
confirmation and an administrator token; remote hub requests require HTTPS.
The controller does not start room capture, speech or playback. Local focused
tests and loopback API integration pass. Commit `bd89594` passed push CI in
[40956030944](https://github.com/sujanmj/aura-companion/actions/runs/40956030944)
and PR CI in
[40956043251](https://github.com/sujanmj/aura-companion/actions/runs/40956043251)
on macOS, Windows and Ubuntu; both runs uploaded all three preview archives.
Pi installation, room playback, acoustic acceptance, macOS hardware acceptance,
and Developer ID signing/notarization remain open.

The same owner-approved invitation controls are now available in the local
Command Center. The panel displays an active session, lists enrolled room names
without node credentials, and requires exact typed confirmation for invite,
transfer and stop. It does not start sensors or audio. Commit `62adb72` passed
push CI [40959155691](https://github.com/sujanmj/aura-companion/actions/runs/40959155691)
and PR CI
[40959164879](https://github.com/sujanmj/aura-companion/actions/runs/40959164879)
on macOS, Windows and Ubuntu; both runs uploaded all three preview archives.
The commit also fixes SQLite worker shutdown ordering with a regression test.
These results cover software and packaging, not Pi hardware, room playback,
acoustics, or public-release signing/notarization.

The enrolled-node room-claim client now accepts a reservation only when the hub
explicitly reports success and echoes the exact requested session, generation
and logical turn UUID with a finite, unexpired lease. Missing, malformed, stale
or mismatched acknowledgements fail closed, and the client does not retry an
ambiguous claim or authorize playback from an invalid response. Local focused
room/handoff tests, the full app Python suite, 28 Node tests, 18 browser tests,
native tests, lint and production build pass. No Pi service, speaker playback,
room cancellation/fencing, or physical handoff is claimed by this software
check. Commit `03e1a89` passed all three platforms in push CI
[40960508464](https://github.com/sujanmj/aura-companion/actions/runs/40960508464)
and PR CI
[40960227044](https://github.com/sujanmj/aura-companion/actions/runs/40960227044);
both runs uploaded macOS, Windows and Ubuntu preview archives.

The Pi simulator's authenticated event, heartbeat and room-claim requests, plus
sensor enrollment, dashboard status and the documented sensor API test client,
now use a shared transport
that bypasses system proxies and refuses redirects. Remote HTTP is rejected
before credentials are sent; remote hubs require HTTPS. Focused tests and all
94 app Python tests pass locally. No Pi installation or deployed network hub is
represented by this change. Commit `29061f7` passed macOS, Windows and Ubuntu
push CI
[40964038358](https://github.com/sujanmj/aura-companion/actions/runs/40964038358)
and PR CI
[40964044684](https://github.com/sujanmj/aura-companion/actions/runs/40964044684);
both runs uploaded all three preview archives.

Commit `2de8276` also routes the documented sensor API test client through the
same no-proxy, no-redirect transport and refuses remote HTTP before sending
credentials. Its focused tests and all 94 app Python tests passed locally.
Push CI
[40966173161](https://github.com/sujanmj/aura-companion/actions/runs/40966173161)
and PR CI
[40966180392](https://github.com/sujanmj/aura-companion/actions/runs/40966180392)
passed on macOS, Windows and Ubuntu and uploaded all three preview archives.

The sensor API authentication and event-status test probes also use direct
transport, reject redirects, and refuse remote HTTP before sending tokens with
a non-zero exit status.
The 10-test admin-client suite, 49 focused room/transport tests and all 94 app
Python tests pass locally. Commit `b7c72ff` passed macOS, Windows and Ubuntu
push CI
[40967410539](https://github.com/sujanmj/aura-companion/actions/runs/40967410539)
and PR CI
[40967416698](https://github.com/sujanmj/aura-companion/actions/runs/40967416698);
both runs uploaded all three preview archives.

Commit `5120a4d` makes unsafe hub URL rejection visible to automation by
returning a non-zero exit code before opening a request. Push CI
[40968379151](https://github.com/sujanmj/aura-companion/actions/runs/40968379151)
and PR CI
[40968385143](https://github.com/sujanmj/aura-companion/actions/runs/40968385143)
passed on macOS, Windows and Ubuntu; both uploaded all three preview archives.

Incident, confirmation, dashboard and runtime-heartbeat probes now follow the
same direct transport rule. The Windows loopback integration test explicitly
bypasses system proxies. Twelve focused admin-client tests, 51 focused
room/transport tests and all 94 app Python tests pass locally. Commit `79b8f40`
passed macOS, Windows and Ubuntu push CI
[40970180323](https://github.com/sujanmj/aura-companion/actions/runs/40970180323)
and PR CI
[40970187073](https://github.com/sujanmj/aura-companion/actions/runs/40970187073);
both runs uploaded all three preview archives.

The Three.js holographic scene is now split from the initial React shell, which
uses the static orb while the scene loads. The initial JavaScript chunk fell
from 1,177.90 kB (326.04 kB gzip) to 266.92 kB (82.76 kB gzip); the scene is a
separate 912.29 kB chunk. Local build, lint, Node and browser tests pass.
Commit `dfd56d9` passed macOS, Windows and Ubuntu push CI
[40972148472](https://github.com/sujanmj/aura-companion/actions/runs/40972148472)
and PR CI
[40972155147](https://github.com/sujanmj/aura-companion/actions/runs/40972155147);
both runs uploaded all three preview archives.

The room reply prototype now exposes a fail-closed software gate for a future
speaker callback. It requires a successful one-shot claim followed by fresh
validation, and its hardware-free tests cover denied, stale, blank and
playback-error cases. It does not implement audio output or establish Pi
hardware acceptance. Commit `1b0d791` passed macOS, Windows and Ubuntu push CI
[41069120294](https://github.com/sujanmj/aura-companion/actions/runs/41069120294)
and PR CI
[41069129491](https://github.com/sujanmj/aura-companion/actions/runs/41069129491),
with all three preview archives uploaded in each run.
