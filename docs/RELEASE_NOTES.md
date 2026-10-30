# AURA development preview — 2026-10-30

## Local voice retry recovery (Phase 5)

If a requested push-to-talk retry encounters a microphone error or no speech,
the Python console now returns to typed input instead of exiting. The transcript
confirmation says that approved text enters AURA's normal memory/provider
flow. Three new regression tests and all 127 app Python tests pass locally;
the Node suite (30 tests), lint and production build pass. Cross-platform CI is
pending. This does not claim microphone, acoustic or Raspberry Pi acceptance.

## Optional local push-to-talk speech on Pi and Linux (Phase 5)

The Python companion console can use Vosk with a manually installed local model
on Linux/Raspberry Pi and macOS. Microphone access remains opt-in, opens only
after the user presses Enter for an individual turn, and stops after at most 15
seconds. AURA displays the transcript for confirmation before it enters the
existing SQLite companion flow; raw audio is not persisted. Audio/model
dependencies are optional and are not installed by the normal preview setup.
Injected tests cover consent/lifecycle boundaries, transcript handling, and
cleanup on device errors. This is a push-to-talk prototype, not wake-word or
background listening; no microphone or Pi hardware acceptance is claimed.
Commit `010735b` passed push CI
[41098719544](https://github.com/sujanmj/aura-companion/actions/runs/41098719544)
and PR CI
[41098727230](https://github.com/sujanmj/aura-companion/actions/runs/41098727230)
on macOS, Windows and Ubuntu; each uploaded all three preview archives. The
push archive SHA-256 prefixes are macOS `26ee08b2`, Windows `84de1dab`, and
Ubuntu `5d61c697`; PR prefixes are macOS `932de5d8`, Windows `413c688b`, and
Ubuntu `ed06d217`.

The console also supports optional local Linux/Pi replies through `espeak-ng`,
selected only with `AURA_TTS_PROVIDER=espeak-ng` and the existing voice-output
confirmation. Replies are passed over stdin with bounded length and runtime;
the feature does not generate saved audio. Mocked process tests cover failure
handling. No Pi speaker, voice-quality or acoustic check has been run; CI
verification for this follow-up is pending.

The Python console now saves only the derived one-shot camera summary to
SQLite. It disables the camera observer's optional JPEG snapshot for this flow;
camera failure still falls back to typed context. Injected tests cover this
storage boundary. No camera permission or hardware acceptance is claimed, and
CI verification for this change is pending.

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
locally, including its inco