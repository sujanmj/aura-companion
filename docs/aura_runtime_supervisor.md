# AURA Runtime Supervisor v0.1

Start the main local AURA services with one command instead of opening multiple terminals.

## Start full runtime

```powershell
python scripts/run_aura_runtime.py
```

This starts:

1. **Sensor API / Web Dashboard** — `scripts/run_sensor_api.py`
2. **Live Safety Monitor** — `scripts/run_live_safety_monitor.py`
3. **Confirmation Timeout Watcher** — `scripts/run_confirmation_timeout_watcher.py`

## Open dashboard

[http://127.0.0.1:8787/dashboard](http://127.0.0.1:8787/dashboard)

Health check: [http://127.0.0.1:8787/health](http://127.0.0.1:8787/health)

Paste your `AURA_SENSOR_API_TOKEN` from `config/keys.env` in the dashboard if token auth is enabled.

## Stop

Press **Ctrl+C** in the runtime terminal. The supervisor terminates all child services cleanly.

## Optional flags

```powershell
python scripts/run_aura_runtime.py --no-monitor
python scripts/run_aura_runtime.py --no-timeout-watcher
python scripts/run_aura_runtime.py --no-api
```

Combine flags to start only the services you need.

## Runtime Health

Services write heartbeats to SQLite while running. The dashboard **Runtime Health** section shows whether each service is **online**, **stale** (~20s without heartbeat), or **missing**.

```powershell
python scripts/show_runtime_health.py
python scripts/test_runtime_heartbeat.py
```

Heartbeats are updated by:

- `sensor_api` — on server start and each `GET /health`
- `live_safety_monitor` — each monitor cycle
- `confirmation_timeout_watcher` — each watcher cycle

`voice_actions` shows **enabled** or **disabled** from `AURA_ENABLE_VOICE_ACTIONS`.

## Notes

- **Voice actions** only run when `AURA_ENABLE_VOICE_ACTIONS=1` in `config/keys.env`. See [live_voice_actions.md](live_voice_actions.md).
- **No real emergency calls**, SMS, Telegram, siren, or water pump actions in v0.1.
- Keep the API on a **trusted local network** only. Use `AURA_SENSOR_API_TOKEN` when exposing beyond localhost.

## Test

```powershell
python scripts/test_aura_runtime_supervisor.py
```

## Related docs

- [local_web_dashboard.md](local_web_dashboard.md)
- [safety_confirmations.md](safety_confirmations.md)
- [confirmation_timeout_watcher.md](confirmation_timeout_watcher.md)
