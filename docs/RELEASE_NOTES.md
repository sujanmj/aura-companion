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
passed. CI is pending.
