# Local Web Dashboard v0.1

Browser UI for the AURA Live Room Dashboard, served from the same hub process as the Sensor API.

## Start the API hub

```powershell
python scripts/run_sensor_api.py
```

## Open the dashboard

[http://127.0.0.1:8787/dashboard](http://127.0.0.1:8787/dashboard)

On your LAN, replace `127.0.0.1` with the hub machine IP.

## API token

If `AURA_SENSOR_API_TOKEN` is set in `config/keys.env`, paste the same token into the dashboard token panel.

- Stored only in browser `localStorage` as `AURA_SENSOR_API_TOKEN`
- Sent as header `X-AURA-API-Token` for JSON calls to `/dashboard/status`
- The HTML page itself is open; JSON endpoints still require the token when configured

## Test

```powershell
python scripts/test_web_dashboard_routes.py
python scripts/test_dashboard_api.py
```

Simulate events:

```powershell
python scripts/pi_node_simulator.py bedroom fall_detected
python scripts/pi_node_simulator.py kitchen smoke_detected
```

Refresh the browser — data updates every 5 seconds.

## Static routes

| Route | Content |
|-------|---------|
| `GET /dashboard` | HTML dashboard page |
| `GET /static/dashboard.css` | Styles |
| `GET /static/dashboard.js` | Client logic |

## Safety notes

- **Local dashboard only** — keep on a trusted LAN.
- Do not expose directly to the internet.
- **No real police, ambulance, SMS, siren, or water pump** actions in v0.1.
- Dashboard is read-only; it does not trigger emergency escalation.
