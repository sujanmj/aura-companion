# AURA Sensor Node API

Local HTTP API for Raspberry Pi, camera, and sensor nodes to send events to the AURA hub over Wi-Fi.

Current version: **v0.4** (enrolled node credentials and retry-safe events)

## Start the AURA hub API

```powershell
python scripts/run_sensor_api.py
```

Optional host and port:

```powershell
python scripts/run_sensor_api.py 0.0.0.0 8787
```

Defaults: `host=127.0.0.1`, `port=8787`

## Test the API

With the server running in another terminal:

```powershell
python scripts/test_sensor_api_client.py
python scripts/test_sensor_api_auth.py
```

The sensor API, incident, confirmation, dashboard and runtime-heartbeat probes
accept an optional hub URL where documented. HTTP is allowed only for loopback
development; remote hubs must use HTTPS. Authenticated hub clients connect
directly and refuse redirects so administrator credentials are not forwarded
through a machine-wide proxy or to another URL. An unsafe hub URL also exits
with an error status before a request is opened.

## Authentication (v0.4)

Protected data routes require a strong token. The hub's `AURA_SENSOR_API_TOKEN`
must be at least 32 characters. Missing or short tokens deny access; the API
never falls back to open event ingestion. `/health` remains public and contains
no user or device data.

Generate a token:

```powershell
python scripts/generate_sensor_api_token.py
```

Add the printed line to `config/keys.env` (local only — do not commit).

### Header

```http
X-AURA-API-Token: <token>
```

- `GET /health` — always open (no token required)
- `GET /events/latest` — requires the token
- `POST /events` — requires the hub token, or the credential for one enrolled node
- `POST /nodes/enroll` and `POST /nodes/revoke` — require the hub token
- `GET /nodes/status` — requires the hub token
- `POST /nodes/heartbeat` — requires an enrolled node token

If the token is missing or shorter than 32 characters, protected routes return
`401 unauthorized`.

Enroll each node on the hub with a stable ID and assigned room:

```powershell
python scripts/enroll_sensor_node.py pi_bedroom_node bedroom --name "Bedroom Pi"
```

The command returns a one-time `AURA_SENSOR_NODE_TOKEN`. Copy it to that node's
private `config/keys.env`; never place the hub token on sensor nodes. The hub
stores only a SHA-256 hash of each random node token. Enrolling the same ID again
rotates its credential. Revoke a node with an authenticated `POST /nodes/revoke`
request containing `{"node_id":"pi_bedroom_node"}`. The hub's `GET /nodes/status`
lists enrolled nodes and reports them online for 90 seconds after their last
heartbeat or event. The node heartbeat command makes up to three attempts for
temporary network and server failures and stops immediately when the hub rejects
the enrolled credential.

Node credentials are limited to event ingestion and their own heartbeat. A node
event must include `event_uuid`; AURA assigns its registered node ID and room,
ignoring source and room values supplied by the node. The simulator uses
`AURA_SENSOR_NODE_TOKEN` when present and can send a heartbeat with:

```powershell
python scripts/pi_node_simulator.py --heartbeat pi_bedroom_node
```

### PowerShell example

```powershell
$headers = @{
    "Content-Type" = "application/json"
    "X-AURA-API-Token" = "your_token"
}
$body = @{
    event_type = "fall_detected"
    event_summary = "Possible fall detected in bedroom."
    source = "pi_bedroom_node"
    room = "bedroom"
    severity = "high"
    confidence = 0.85
    requires_action = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://<hub-ip>:8787/events" -Method Post -Headers $headers -Body $body
```

### Python urllib example (Raspberry Pi node)

```python
import json
import urllib.request

url = "https://<hub-hostname>:8787/events"
token = "<copy this node's enrollment token from its private config>"
payload = {
    "event_type": "fall_detected",
    "event_summary": "Possible fall detected in bedroom.",
    "source": "pi_bedroom_node",
    "room": "bedroom",
    "severity": "high",
    "confidence": 0.85,
    "requires_action": True,
    "event_uuid": "client-generated-unique-id",
}

data = json.dumps(payload).encode("utf-8")
request = urllib.request.Request(
    url,
    data=data,
    headers={
        "Content-Type": "application/json",
        "X-AURA-API-Token": token,
    },
    method="POST",
)

with urllib.request.urlopen(request, timeout=10) as response:
    print(response.read().decode("utf-8"))
```

For an enrolled node, use `AURA_SENSOR_NODE_TOKEN` and omit `source`/`room`;
the hub takes both values from its node registration.

### Persistent Pi node presence service

`deploy/systemd/aura-pi-node-heartbeat.service` keeps an enrolled node's online
status fresh after reboot. It sends heartbeats only; it does not read sensors,
capture audio/video, or act as the Pi companion runtime. Install the checkout at
`/opt/aura-companion`, create a dedicated `aura-node` system account, and copy
the unit into `/etc/systemd/system/`. Create `/etc/aura/aura-node.env` with the
node ID and one-time enrollment token from this node's private configuration:

```env
AURA_SENSOR_NODE_ID=pi_bedroom_node
AURA_SENSOR_NODE_TOKEN=YOUR_NODE_TOKEN
AURA_SENSOR_API_URL=https://aura-hub.example.com:8787
AURA_SENSOR_NODE_HEARTBEAT_INTERVAL_SECONDS=30
```

Keep the file root-owned with mode `0600`. The startup check rejects missing or
weak tokens, invalid IDs, remote HTTP URLs, and heartbeat intervals outside
5–60 seconds. Remote hub connections require HTTPS with a certificate trusted
by the node's operating system. Plain HTTP is permitted only for loopback local
development. Enable the service with
`systemctl enable --now aura-pi-node-heartbeat.service`.
The unit runs as `aura-node` with a read-only filesystem view and does not write
application state. It is tested on CI only and has not been installed on Pi
hardware.

v0.4 uses one hub token for administration and separate revocable node tokens for
each enrolled sensor. Keep the API on a **trusted LAN only**; do not expose it
directly to the internet. Network-bound hubs require TLS 1.2 or newer and a
configured certificate and private key. The packaged systemd template expects
`/etc/aura/tls/server.crt` and `/etc/aura/tls/server.key`; install a certificate
trusted by every node and make the private key readable by the `aura` service
account without world access. The service preflight rejects missing TLS files
or a world-readable/writable private key. HTTP remains available only when the
hub binds to loopback for development. Node clients reject remote HTTP before
sending their credential.
trusted network and protect access to each node's private config.

## Endpoints

### `GET /health`

Returns service status.

```json
{
  "ok": true,
  "service": "aura-sensor-api",
  "version": "0.4"
}
```

### `GET /events/latest`

Returns the 10 most recent device events for the default user.

```json
{
  "ok": true,
  "events": []
}
```

### `GET /nodes/status`

Returns enrolled nodes and their last heartbeat. A node is online for 90 seconds
after its latest authenticated heartbeat or event.

### `POST /nodes/enroll`

Requires the hub token. Provide `node_id`, `room`, and optional `display_name`.
The response includes a random node token once; re-enrolling the same ID rotates
the old token.

### `POST /nodes/heartbeat`

Requires that node's own token and a JSON body containing its registered
`node_id`. Returns 401 for a revoked or unknown token and 403 if the ID does not
match the credential.

### `POST /nodes/revoke`

Requires the hub token and a JSON body such as `{"node_id":"pi_bedroom_node"}`.
The revoked credential stops working immediately.

### `POST /events`

Accepts a JSON sensor event. AURA publishes it through the device event bus, evaluates safety, builds escalation plans when needed, and dispatches **simulated/logged** actions only.

Required fields:

- `event_type`
- `event_summary`

Optional fields:

- `source` (default: `sensor_api`)
- `event_uuid` (client-generated identifier, recommended for retries; max 128 characters)
- `room`
- `severity` (default: `low`)
- `confidence` (default: `0.5`)
- `requires_action` (default: `false`)
- `metadata` (object)

When an `event_uuid` is supplied, AURA stores at most one event for that identifier
and source. Repeating the request returns the original event with `duplicate: true`
and does not repeat observations, safety evaluation, or escalation processing.
Clients should reuse the same `event_uuid` for every retry of one event.

Send from another device on your network:

```http
POST http://<hub-ip>:8787/events
Content-Type: application/json
```

## Example payloads

### Pill missed

```json
{
  "event_type": "pill_missed",
  "event_summary": "Morning medicine may have been missed.",
  "source": "medicine_schedule",
  "room": "bedroom",
  "severity": "medium",
  "confidence": 0.9,
  "requires_action": true
}
```

### Plant moisture low

```json
{
  "event_type": "plant_moisture_low",
  "event_summary": "Balcony plant soil moisture is low.",
  "source": "plant_sensor",
  "room": "balcony",
  "severity": "low",
  "confidence": 0.8,
  "requires_action": true
}
```

### Fall detected

```json
{
  "event_type": "fall_detected",
  "event_summary": "Possible fall detected in bedroom.",
  "source": "pi_bedroom_node",
  "room": "bedroom",
  "severity": "high",
  "confidence": 0.85,
  "requires_action": true,
  "metadata": {
    "camera_id": "bedroom_01"
  }
}
```

### Smoke detected

```json
{
  "event_type": "smoke_detected",
  "event_summary": "Possible smoke detected in kitchen.",
  "source": "smoke_sensor",
  "room": "kitchen",
  "severity": "critical",
  "confidence": 0.9,
  "requires_action": true
}
```

### Unknown person detected

```json
{
  "event_type": "unknown_person_detected",
  "event_summary": "Unknown person detected near front door.",
  "source": "camera_front_door",
  "room": "front_door",
  "severity": "medium",
  "confidence": 0.7,
  "requires_action": true
}
```

### Unknown person with possible weapon

```json
{
  "event_type": "unknown_person_with_possible_weapon",
  "event_summary": "Unknown person with possible weapon-like object near front door.",
  "source": "camera_front_door",
  "room": "front_door",
  "severity": "high",
  "confidence": 0.75,
  "requires_action": true
}
```

## Safety notes

- v0.4 requires `AURA_SENSOR_API_TOKEN` for administration and denies access by default.
- Keep the API on a trusted local network only. Do not expose directly to the internet.
- **No real emergency calls** happen in v0.1/v0.2 — police, ambulance, SMS, Telegram, siren, and water pump actions are simulated and logged only.
