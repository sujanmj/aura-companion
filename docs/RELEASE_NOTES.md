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
Python unit tests. Local verification: 3 focused DST reminder tests OK; 21
memory-controls tests OK including the New York ZoneInfo case; 112 Python app
tests OK; `pip-audit` found no known vulnerabilities on both requirement
files; lint OK; 30 Node tests OK. Cross-platform CI remains pending; Windows
execution is not claimed from this non-Windows host.

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
symlinked files, opens the snapshot read-only, and displays whether SQLi