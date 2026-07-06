# Confirmation Timeout Watcher v0.1

Pending safety confirmations expire automatically when the user does not respond in time.

## Run once

```powershell
python scripts/run_confirmation_timeout_watcher.py --once
```

Processes due confirmations once and prints `AURA_CONFIRMATION_TIMEOUT_WATCHER_ONCE_OK`.

## Run continuously

```powershell
python scripts/run_confirmation_timeout_watcher.py
```

Optional flags:

- `--interval` — polling interval in seconds (default: `5`)
- `--limit` — max confirmations per cycle (default: `20`)

## Behavior

When a confirmation is created, `expires_at` is set from the escalation plan's `wait_seconds_before_escalation` (default **30 seconds** if missing or zero).

The watcher finds pending confirmations where:

- `expires_at` is not null
- `expires_at <= CURRENT_TIMESTAMP`

For each due confirmation:

1. Status becomes `expired`
2. `response_text` is set to `No response before timeout.`
3. Action log: `confirmation_timeout` (status `expired`)
4. Simulated action log: `notify_contact_simulated` (status `simulated_notification_logged`)

## v0.1 limitations

- **No real emergency calls**, SMS, Telegram, siren, or water pump actions.
- **Notify** is simulated only — logged locally in `action_logs`.
- Expired confirmations appear in the dashboard **Recent Confirmations** table.

## Test

```powershell
python scripts/test_confirmation_timeout.py
```

## Related

- [safety_confirmations.md](safety_confirmations.md) — confirmation workflow and dashboard buttons
- Run alongside `python scripts/run_sensor_api.py` and `python scripts/run_live_safety_monitor.py` for full local safety flow
