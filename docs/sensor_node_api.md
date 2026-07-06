# AURA Sensor Node API v0.1

Local HTTP API for Raspberry Pi, camera, and sensor nodes to send events to the AURA hub over Wi-Fi.

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
```

## Endpoints

### `GET /health`

Returns service status.

```json
{
  "ok": true,
  "service": "aura-sensor-api",
  "version": "0.1"
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

- **v0.1 has no authentication.** Keep the API on a trusted local network only.
- A future version will add API token/auth.
- **No real emergency calls** happen in v0.1 — police, ambulance, SMS, Telegram, siren, and water pump actions are simulated and logged only.
