# Incident Timeline v0.1

AURA connects device events, safety plans, dispatch actions, confirmations, and timeouts into one **incident story**.

## Example flow

**Incident #12: fall_detected in bedroom**

1. Event received
2. Safety action planned
3. AURA spoke alert (`speak_now`)
4. Confirmation requested
5. User confirmed okay **or** timeout happened
6. Simulated contact notification logged (if applicable)
7. Incident closed (`resolved`, `expired`, `cancelled`, or `simulated_escalated`)

## What incidents are

Each safety-related device event can create an `incidents` row linked by `source_event_id`. Timeline items in `incident_timeline_items` record each step.

### Incident statuses

| Status | Meaning |
|--------|---------|
| `open` | Active incident |
| `resolved` | User confirmed okay |
| `expired` | Confirmation timed out |
| `cancelled` | User cancelled confirmation |
| `simulated_escalated` | User chose simulated notify/escalate |

## API endpoints

All routes use `X-AURA-API-Token` when token auth is configured.

### POST /events

Response includes:

```json
{
  "incident": {
    "id": 12,
    "title": "fall_detected in bedroom",
    "status": "open",
    "severity": "high",
    "room": "bedroom"
  }
}
```

### GET /incidents/recent?limit=20

```json
{ "ok": true, "incidents": [ ... ] }
```

### GET /incidents/open?limit=20

```json
{ "ok": true, "incidents": [ ... ] }
```

### GET /incidents/<id>

```json
{
  "ok": true,
  "incident": { ... },
  "timeline": [
    {
      "item_type": "event_received",
      "title": "Event received",
      "summary": "...",
      "status": "dispatched",
      "created_at": "..."
    }
  ]
}
```

## Dashboard

Open [http://127.0.0.1:8787/dashboard](http://127.0.0.1:8787/dashboard).

- **Open Incidents** — active incidents
- **Recent Incidents** — latest incident history
- **View Timeline** — loads `GET /incidents/<id>` and shows the full story

## v0.1 limitations

- **No real emergency calls**, SMS, Telegram, siren, or water pump actions.
- Simulated escalation and notify actions are logged only.
- Timelines are stored locally in SQLite.

## Test commands

```powershell
python scripts/test_incident_timeline_service.py
python scripts/test_incident_api.py
```

`test_incident_api.py` requires the sensor API:

```powershell
python scripts/run_sensor_api.py
```

Or start everything:

```powershell
python scripts/run_aura_runtime.py
```

## Related docs

- [safety_confirmations.md](safety_confirmations.md)
- [confirmation_timeout_watcher.md](confirmation_timeout_watcher.md)
- [aura_runtime_supervisor.md](aura_runtime_supervisor.md)
