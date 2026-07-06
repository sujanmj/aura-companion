# Safety Confirmation Workflow v0.1

AURA can store **pending safety confirmations** when escalation rules require user confirmation after a safety event.

## What are pending confirmations?

When a safety event triggers escalation with `requires_user_confirmation`, AURA:

1. Logs an `ask_confirmation` action (simulated prompt).
2. Creates a `confirmation_requests` row with status `pending`.
3. Exposes the pending confirmation via API and dashboard.

The user (or dashboard operator) can respond without real emergency calls.

## Enable / disable

No separate env flag is required. Confirmations are created automatically when escalation plans require user confirmation.

Voice output for safety prompts remains controlled by `AURA_ENABLE_VOICE_ACTIONS` (see [live_voice_actions.md](live_voice_actions.md)).

## Dashboard buttons

Open [http://127.0.0.1:8787/dashboard](http://127.0.0.1:8787/dashboard) with your `AURA_SENSOR_API_TOKEN`.

**Pending Confirmations** section:

| Button | API `response` | Result |
|--------|----------------|--------|
| I'm okay | `ok` | `confirmed_ok` |
| Notify simulated contact | `notify` | `confirmed_escalate` (simulated only) |
| Cancel | `cancel` | `cancelled` |

After a response, the dashboard refreshes automatically.

## API endpoints

All routes use the same `X-AURA-API-Token` header as other sensor API routes (when token is configured).

### POST /events

When confirmation is required, response includes:

```json
{
  "ok": true,
  "confirmation": { "id": 1, "status": "pending", "prompt": "..." }
}
```

### GET /confirmations/pending

```json
{ "ok": true, "confirmations": [ ... ] }
```

### GET /confirmations/recent

```json
{ "ok": true, "confirmations": [ ... ] }
```

### POST /confirmations/respond

```json
{
  "confirmation_id": 123,
  "response": "ok"
}
```

Supported `response` values: `ok`, `i_am_ok`, `safe`, `notify`, `escalate`, `cancel`.

```json
{
  "ok": true,
  "result": {
    "confirmation_id": 123,
    "status": "confirmed_ok",
    "action_log_id": 456
  }
}
```

## v0.1 limitations

- **No real emergency calls**, SMS, Telegram, siren, or water pump actions.
- **Notify** records a simulated escalation action log only.
- Confirmations are stored locally in SQLite (`confirmation_requests` table).

## Test commands

```powershell
python scripts/test_confirmation_engine.py
python scripts/test_confirmation_api.py
```

`test_confirmation_api.py` requires the sensor API server:

```powershell
python scripts/run_sensor_api.py
```

## Runtime

```powershell
python scripts/run_sensor_api.py
python scripts/run_live_safety_monitor.py
```

Both paths create pending confirmations when escalation requires user confirmation.
