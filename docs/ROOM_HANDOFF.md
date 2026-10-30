# Explicit room handoff protocol — software prototype

The sensor hub can reserve a reply for one explicitly invited, enrolled node.
This prototype does not activate a microphone, camera, speaker, provider, tool,
or memory recall. There is no room tracking or inferred person identity. It is
not integrated into the Pi heartbeat client or native Mac conversation loop yet.

The Pi node simulator now includes a one-shot client for `/rooms/claim`:

```sh
python scripts/pi_node_simulator.py --claim-session SESSION_ID --generation 1 --turn-id TURN_UUID
```

It uses the enrolled `AURA_SENSOR_NODE_TOKEN` and requires a caller-supplied
canonical UUID that remains stable for the logical reply. The client sends one
request only. If its response is lost, the reservation outcome is unknown and
the client fails closed; callers must not mint a new turn ID and replay the same
reply. A successful reservation still does not activate capture, generate a
reply, or play audio. This command is a software integration point, not physical
room handoff acceptance.

The same simulator can recheck an existing reservation just before a future
playback attempt:

```sh
python scripts/pi_node_simulator.py --validate-session SESSION_ID --generation 1 --turn-id TURN_UUID
```

This is one point-in-time check only; it does not start or control playback.

The owner can manage invitations with the admin-only command line controller:

```sh
python scripts/room_invitation.py status
python scripts/room_invitation.py start bedroom
python scripts/room_invitation.py transfer SESSION_ID 1 kitchen
python scripts/room_invitation.py stop SESSION_ID 2
```

Set `AURA_SENSOR_API_TOKEN` to the hub administrator credential and, for a
remote hub, set `AURA_SENSOR_API_URL` to its HTTPS origin. The default URL is
loopback for local development. Start, transfer and stop require typing the
displayed action and destination/session exactly; status is read-only. The
controller sends a single request and does not retry an uncertain result. It
displays only the node, session, generation and expiry fields. These commands
manage the five-minute invitation only; they do not activate sensors, speech,
memory recall or playback.

The local Command Center also has a **Room Invitation** panel. Paste the hub
administrator token into the existing token field, refresh invitation status,
and select an enrolled room. Invite, move and end each require the exact phrase
shown in the confirmation prompt. If the response is lost, refresh status before
trying another change. The browser keeps the token in its existing local-only
storage, sends requests directly to the same hub without following redirects,
and does not expose node credentials in the panel. The panel only manages the
reservation; it does not control capture, speech or playback.

Use the existing private sensor hub deployment and authentication. The hub's
master `X-AURA-API-Token` controls invitations. Enrolled nodes use their separate
credentials only to claim turns; possession of a node token cannot start,
transfer, stop or inspect an owner's invitation. This API retains the existing
single configured owner model; it is not a multi-account login service. Do not
expose the plain HTTP development server to the public internet.

All routes below are JSON POST requests:

| Route | Credential | Body | Result |
| --- | --- | --- | --- |
| `/rooms/start` | Master | `node_id`, `approved: true` | New `session` with `session_id`, `generation: 1`, node and expiry |
| `/rooms/transfer` | Master | `session_id`, current integer `generation`, destination `node_id`, fresh `approved: true` | Same session, increased generation |
| `/rooms/status` | Master | `{}` | Current session or `null` |
| `/rooms/stop` | Master | `session_id`, current `generation` | Deletes session and claims; `session: null` |
| `/rooms/claim` | Enrolled node | `session_id`, current integer `generation`, canonical UUID `turn_id` | `session.reserved: true` once for that turn |
| `/rooms/claim/validate` | Enrolled node | Same identifiers as `/rooms/claim` | Confirms that the reservation and invitation are still current at check time |

Start and transfer need a visible human invitation before a caller sends literal
JSON `true`; string or numeric approximations are rejected. The destination must
belong to the owner, be enabled, and have a heartbeat within 90 seconds. A start
cannot replace an existing active invitation. Transfers do not extend the
original five-minute deadline. After expiry, obtain a new explicit invitation.
Status, start and other successful protocol operations clean expired metadata;
export also cleans it. No background expiry timer is required to reject an
expired claim. Stopping, revoking or re-enrolling the active node deletes its
session and claims. Rotation requires a fresh heartbeat and invitation.

The controller must assign one stable UUID to each logical reply and reuse it
across retries and destinations. Independently generating different UUIDs for
the same spoken utterance does **not** deduplicate it. A SQLite write transaction
serializes reservations across hub connections. The pair of session ID and turn
ID is unique, even after transfer; at most 1,000 claims fit in one session.
Reservations survive a hub process restart within the original lease. A repeated
claim returns HTTP 409, never permission to replay. Missing/incorrect credential
returns 401; stale, expired, uninvited or invalid protocol requests return 409.
A lost response can therefore cause a missed reply: fail closed instead of
retrying speech under a new turn ID.

An enrolled node may call `/rooms/claim/validate` immediately before a future
playback attempt. The hub rechecks the node heartbeat, active invitation,
generation and exact stored claim. A transfer, stop, expiry, revocation or
re-enrollment makes the old claim fail validation. This is a point-in-time
fence check only: it cannot stop sound already playing or eliminate a transfer
race after the response, and it is not connected to speaker playback.

This is at-most-one **software reservation**, not exactly-once physical playback.
A reservation already returned cannot be recalled by a transfer or stop. A real
speaker pipeline still needs cancellation, fencing at the playback boundary,
audio ownership, clock/network-loss acceptance and an explicit UI before use.
Wall-clock rollback or restoration of an old database backup is not addressed by
this prototype; revoke invitations before deployment from a restored backup.

Only owner/session/node/turn identifiers, generation and lease deadline are
stored in the new tables. Memory export includes these records, scoped to the
owner, without credentials. Stop deletes this live metadata; existing backups
and SQLite storage recovery are not securely erased. No conversation text,
ambient media or new profile memory is recorded by these endpoints.

## Reproducible evidence

Run `python3 -m unittest discover -s aura-app/tests -p test_room_handoff.py` from
the repository root. Eight tests use temporary databases and a loopback server:
approval and online prerequisites; transfer fences and duplicate claims; owner
scoping, expiry and process restart; rotation/revocation; two concurrent database
connections racing for a turn; validation/capacity; and actual HTTP role checks,
transfer and stop without conversation-memory writes. No hardware, production
memory database or external service is used.

The node claim and point-in-time validation clients are covered separately with
`python3 scripts/test_room_handoff_client.py`. Its tests verify exact
credentials and stable turn payloads, CLI dispatch, strict input validation,
rejection handling, and fail-closed behavior after an ambiguous network result.
These tests do not connect a client to hardware or exercise speaker playback.

The owner controller is covered with `python3 scripts/test_room_invitation.py`
and the loopback API integration test above. It checks typed consent, admin
credential use, HTTPS policy, safe status output and one-request failure
handling. No deployed hub or physical device is exercised.

The dashboard invitation panel's request logic is covered by
`aura-app/tests/room-invitation-ui.test.mjs`: exact confirmation for each
change, one request after a lost mutation response, status refresh, and safe
rendering. The loopback API test checks that the dashboard serves this script.
