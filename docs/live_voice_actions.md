# Live Voice Safety Actions v0.1

Optional Windows TTS speech for safety `speak_now` actions during live runtime (Sensor API and Live Safety Monitor).

Voice is **disabled by default**.

## Enable voice actions

Add to `config/keys.env` (local only — do not commit):

```env
AURA_ENABLE_VOICE_ACTIONS=1
```

## Disable voice actions

```env
AURA_ENABLE_VOICE_ACTIONS=0
```

Accepted enable values: `1`, `true`, `yes`, `on` (case-insensitive).

## How it works

- `actions/voice_runtime.py` checks `AURA_ENABLE_VOICE_ACTIONS`
- When enabled, reuses `perception/tts.py` (`get_speaker_from_env()` / Windows TTS)
- `ActionDispatcher` `speak_now` status:
  - `spoken` — TTS succeeded
  - `logged` — no speaker (voice disabled)
  - `voice_error_logged` — speaker failed
- Sensor API caches the runtime speaker once per server process
- Live Safety Monitor creates speaker at startup when you run `run_live_safety_monitor.py`

## Test commands

```powershell
python scripts/test_voice_runtime_config.py
python scripts/test_voice_action_dispatcher.py
python scripts/test_live_voice_smoke.py
python scripts/test_tts.py
```

`test_live_voice_smoke.py` only speaks when `AURA_ENABLE_VOICE_ACTIONS=1`.

## Runtime

```powershell
python scripts/run_sensor_api.py
python scripts/run_live_safety_monitor.py
```

When voice is enabled, safety escalation spoken responses may be read aloud through Windows TTS.

## Safety notes

- Voice is disabled by default.
- Only local Windows TTS speech is enabled — **no real emergency calls, SMS, siren, or water pump** actions.
- Uses the same `AURA_WINDOWS_VOICE` / Windows TTS settings as the companion console.
