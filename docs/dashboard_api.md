# Live Room Dashboard API v0.1

JSON dashboard endpoints for future AURA web/mobile UI. Served by the same hub process as the Sensor API.

## Start the API hub

```powershell
python scripts/run_sensor_api.py
```

## Test and inspect

```powershell
python scripts/test_dashboard_api.py
python scripts/show_dashboard_status.py
```

## Authentication

Dashboard routes use the same token as the Sensor API when `AURA_SENSOR_API_TOKEN` is configured in `config/keys.env`:

```http
X-AURA-API-Token: <token>
```

- `GET /health` — always open
- All `/dashboard/*` routes — require token when configured

## Routes

### `GET /dashboard/status`

Full dashboard snapshot: summary counts, latest events, pending events, recent actions, rooms, and critical/high alerts.

### `GET /dashboard/events?limit=20`

Latest device events (default 20, max 100).

### `GET /dashboard/actions?limit=20`

Latest action logs (default 20, max 100).

### `GET /dashboard/rooms?limit=50`

Room activity grouped from recent events (default 50, max 200).

## Example workflow

```powershell
python scripts/run_sensor_api.py
python scripts/pi_node_simulator.py bedroom fall_detected
python scripts/pi_node_simulator.py kitchen smoke_detected
python scripts/show_dashboard_status.py
```

## Safety notes

- Intended for future mobile/web dashboard on a **trusted local network**.
- Dashboard routes are read-only — **no real emergency calls** are triggered.
- No SMS, Telegram, siren, or water pump actions from dashboard endpoints.
