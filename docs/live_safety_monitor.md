# Live Safety Monitor v0.1

Always-on monitor that watches unhandled device events and safely processes each one exactly once.

## Run once

Process all pending events (`action_status = "none"`) and exit:

```powershell
python scripts/run_live_safety_monitor.py --once
```

Optional flags:

```powershell
python scripts/run_live_safety_monitor.py --once --limit 20
```

## Run continuously

Poll for pending events every few seconds:

```powershell
python scripts/run_live_safety_monitor.py
```

```powershell
python scripts/run_live_safety_monitor.py --interval 5 --limit 10
```

Stop with Ctrl+C. Prints `AURA_LIVE_SAFETY_MONITOR_STOPPED`.

## How it works

1. Finds `device_events` where `action_status = "none"` (oldest first).
2. Evaluates each event with `SafetyEngine`.
3. If no action required → marks `ignored`.
4. If action required → builds escalation plan, dispatches **simulated/logged** actions, marks `dispatched`.
5. Never processes the same event twice.

## API vs monitor

- **Sensor API** (`POST /events`) processes and dispatches immediately, then marks events `dispatched` or `ignored`.
- **Live monitor** is mainly for events inserted directly by local devices/services (e.g. via `DeviceEventBus`) that were not handled by the API.

## Inspect results

```powershell
python scripts/list_recent_events.py
python scripts/list_action_logs.py
```

## Tests

```powershell
python scripts/test_event_action_status.py
python scripts/test_live_safety_monitor.py
```

## Safety notes

- v0.1 only **simulates** notifications and actions.
- No real emergency calls, SMS, Telegram, siren, or water pump actions.
- No real emergency escalation without future confirmation rules.
