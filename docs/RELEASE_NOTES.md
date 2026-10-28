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
and Mac ad-hoc build passed; this milestone's CI remains pending.
