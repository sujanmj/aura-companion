# AURA Sensor Node API

Local HTTP API for Raspberry Pi, camera, and sensor nodes to send events to the AURA hub over Wi-Fi.

Current version: **v0.3** (required shared token auth)

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

## Authentication (v0.3)

Protected routes always require a shared token of at least 32 characters in
`AURA_SENSOR_API_TOKEN` in `config/keys.env`. Missing or short tokens deny access;
the API never falls back to open event ingestion. `/health` remains public and
contains no user or device data.

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
- `POST /events` — requires the token

If the token is missing or shorter than 32 characters, protected routes return
`401 unauthorized`.

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

url = "http://<hub-ip>:8787/events"
token = "<copy the generated token from the hub's private config>"
payload = {
    "event_type": "fall_detected",
    "event_summary": "Possible fall detected in bedroom.",
    "source": "pi_bedroom_node",
    "room": "bedroom",
    "severity": "high",
    "confidence": 0.85,
    "requires_action": True,
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

v0.3 requires a strong shared token for all data and event routes. Keep the API on
a **trusted LAN only**; do not expose it directly to the internet. Device-specific
credentials and enrollment are still future work; this token currently authorizes
all configured sensor nodes.

## Endpoints

### `GET /health`

Returns service status.

```json
{
  "ok": true,
  "service": "aura-sensor-api",
  "version": "0.3"
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

### `POST /events`

Accepts a JSON sensor event. AURA publishes it through the device event bus, evaluates safety, builds escalation plans when needed, and dispatches **simulated/logged** actions only.

Required fields:

- `event_type`
- `event_summary`

Optional fields:

- `source` (default: `sensor_api`)
- `room`
- `severity` (default: `low`)
- `confidence` (default: `0.5`)
- `requires_action` (default: `false`)
- `metadata` (object)

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

- v0.3 requires `AURA_SENSOR_API_TOKEN` for protected routes and denies access by default.
- Keep the API on a trusted local network only. Do not expose directly to the internet.
- **No real emergency calls** happen in v0.1/v0.2 — police, ambulance, SMS, Telegram, siren, and water pump actions are simulated and logged only.
