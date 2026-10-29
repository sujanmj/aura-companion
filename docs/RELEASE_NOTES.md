# AURA development preview — 2026-10-28

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
ad-hoc Mac app build pass locally. Slow Windows browser runs now have a 60-second
per-test ceiling; fresh PR CI and acoustic acceptance are pending.
