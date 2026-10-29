# Phase 12 acceptance record

Use this record for a specific build and home setup. Do not mark a check as
passed from CI, simulation, or a checklist mark alone. Record the build commit,
platform, hardware, date, operator, test result and evidence location. Use only
`PASS`, `FAIL`, `BLOCKED`, or `NOT RUN`; leave a blocked check open until its
missing prerequisite is available.

## Automated software evidence

These checks establish only the behavior covered by their tests:

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

## Required device checks

| Check | Expected result | Evidence to record | Current status |
| --- | --- | --- | --- |
| Fresh Mac install and permissions denied | The app reports denied microphone, speech, and camera access without capturing; the recovery action opens the matching System Settings page. | macOS version, app signature, permission state, screenshots or log | BLOCKED: distribution identity and clean-install acceptance |
| Fresh Mac install and permissions granted | Capture begins only after an explicit user action; visible status and Pause accurately reflect both sensors. | Device model, app commit, consent steps, start/pause/stop result | NOT RUN |
| Pause, close, quit, sleep, wake and restart | No capture resumes after manual Pause, close, quit, or sleep. Wake does not bypass a required user restart. | Each transition, time to stop, observed microphone/camera state | NOT RUN |
| Speech turn-taking and Stop speaking | Replies stop on request; the microphone resumes only when the current ambient session remains active; no audible feedback loop or stale reply occurs. | Room/noise setup, speaker and microphone, interruption attempts, failures | NOT RUN |
| False person and object detections | AURA does not guess a person's identity, does not claim certainty for an object label, and lets the owner correct or delete saved summaries. | Lighting, distance, sample count, false positives/negatives, correction/deletion result | NOT RUN |
| Memory review, export, backup and deletion | Export contains only the selected account; edits/deletions take effect in recall; backup and restore behavior is understood before upgrade. | Account used, export location kept private, before/after checks | NOT RUN |
| Pi service installation and reboot | The documented heartbeat service runs unprivileged, uses the enrolled node credential, and reports online only while heartbeats are fresh. | Pi model/OS, service unit, reboot, token rotation/revocation, hub logs | BLOCKED: no Pi installation tested |
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
