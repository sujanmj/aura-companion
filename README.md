# AURA Companion

## Recommended dev runtime

Python **3.11** virtual environment on Windows.

See [docs/setup_windows.md](docs/setup_windows.md) for install and venv setup steps.

## Current milestones

- SQLite local memory engine
- Companion Reaction Engine v0.1
- Companion Console v0.1
- Response Style Learning v0.1
- LLM Brain Adapter v0.1
- Cloud Brain Provider v0.1
- Voice Output v0.1
- Windows Voice Selection v0.1
- Microphone Input v0.1
- Context Relevance Filter v0.1
- Context Relevance v0.2
- Camera Observation v0.1
- Camera Observation v0.2
- Camera Observation v0.3
- Device Event Bus v0.1
- People Registry v0.1
- Guest Introduction Flow v0.1
- Emergency Contacts + Escalation Rules v0.1
- Action Dispatcher v0.1
- Sensor Node API v0.1
- Sensor API Token Auth v0.2

Secrets live in `config/keys.env`. That file is ignored by git.

### Local config example (do not commit)

```env
AURA_SENSOR_API_TOKEN=change_this_local_token
```

Generate a real token with `python scripts/generate_sensor_api_token.py` and add it to `config/keys.env` locally.

When `AURA_BRAIN_PROVIDER=claude`, Claude is the primary cloud brain. You must also set `ANTHROPIC_MODEL` in `config/keys.env`. If Claude fails or is unavailable, AURA falls back to the local reaction engine.

Voice output uses built-in Windows `System.Speech` through PowerShell. `AURA_TTS_PROVIDER` defaults to `windows`.

Voice names depend on installed Windows voices. List them with `python scripts/list_windows_voices.py`.

### Voice config example (local only — do not commit)

```env
AURA_TTS_PROVIDER=windows
AURA_WINDOWS_VOICE=Microsoft Zira Desktop
```

If `AURA_WINDOWS_VOICE` is not set, AURA prefers a Zira voice when installed, otherwise the Windows default.

Microphone input uses Windows built-in speech recognition through PowerShell. No paid STT API yet. If recognition fails, AURA falls back to typed input. Microphone permission and the default input device must be working in Windows.

Windows STT is experimental. Transcript confirmation is enabled in the companion console — you can accept, edit, retry, or reject a transcript before AURA stores or responds. Later we will replace this with Whisper/local STT for better accuracy.

AURA uses memory only when it is relevant to the current message or latest observation. Generic greetings should not trigger old test memories. This prevents the companion from feeling clingy or weird.

Context Relevance v0.2: generic greetings bypass the LLM to prevent stale memory overuse. The prompt builder only includes relevant memory and the current user message. If the cloud brain times out or fails, AURA safely falls back to the local response.

Camera Observation v0.3 adds diagnostics (brightness, blur, face count) and clearer observation summaries. Face detection is basic and only used as an early signal — not identity or emotion recognition. Haar cascade will be replaced later by stronger person/pose detection. Captured snapshots under `data/media/snapshots/` are local and ignored by git.

Camera diagnostics commands:

```powershell
python scripts/test_camera.py
python scripts/open_latest_snapshot.py
python scripts/preview_camera.py
```

Device Event Bus v0.1 is the foundation for Raspberry Pi sensors, future mobile app sync, and home safety monitoring. Sensors send normalized events into AURA. The safety engine logs planned actions only — **no police, ambulance, or emergency service calls happen in v0.1**. Emergency escalation will be added later only with confirmation rules and user consent.

Device event commands:

```powershell
python scripts/test_device_event_bus.py
python scripts/simulate_sensor_event.py pill_missed "Morning medicine may have been missed"
python scripts/simulate_sensor_event.py plant_moisture_low "Balcony plant soil moisture is low"
python scripts/simulate_sensor_event.py fall_detected "Possible fall detected in bedroom"
```

People Registry v0.1 adds a manual introduction flow for known guests and family. Face recognition is **not active yet**. Face memory and embeddings require explicit consent (`consent_to_remember`). Unknown person events can trigger the safety engine. Future camera nodes will map person detections into this registry.

People registry commands:

```powershell
python scripts/test_people_registry.py
python scripts/introduce_person.py "Rohan" "cousin" "Family member"
python scripts/list_known_people.py
```

Guest Introduction Flow v0.1 connects the people registry, device event bus, and safety engine in the companion console. Real face recognition is **not active yet** — this is manual introduction and the foundation for future face enrollment. AURA asks for consent before remembering face or person details. Unknown person events can trigger a security check and prompt you to introduce the guest.

Console commands (inside `run_companion_console.py`):

- `/people` — list known people
- `/introduce` — manually introduce a guest
- `/unknown-person` — simulate unknown person at front door

```powershell
python scripts/test_guest_introduction_flow.py
```

Emergency Contacts + Escalation Rules v0.1 adds a safe escalation layer for falls, fire/smoke, health signals, and unknown person events. Emergency contacts are stored locally. Escalation plans create **planned** actions only — no real police, ambulance, SMS, or Telegram calls happen yet. Later app/Telegram/SMS integration will use these plans. AURA requires user confirmation before serious escalation.

```powershell
python scripts/add_emergency_contact.py "Test Contact" "+910000000000" "family"
python scripts/list_emergency_contacts.py
python scripts/test_escalation_engine.py
python scripts/test_safety_escalation_flow.py
```

Action Dispatcher v0.1 routes planned actions into simulated channels — speak, confirmation prompts, contact notifications, app alerts, sirens, and plant watering. No real emergency calls, SMS, Telegram, siren, or water pump actions happen yet. This prepares future integrations safely.

```powershell
python scripts/test_action_dispatcher.py
python scripts/test_full_safety_action_flow.py
```

Sensor Node API v0.1 exposes a local HTTP API so Raspberry Pi, camera, and sensor nodes can send events over Wi-Fi. Uses built-in `http.server` — no FastAPI yet. See [docs/sensor_node_api.md](docs/sensor_node_api.md) for endpoint details and example payloads.

Sensor API Token Auth v0.2 adds optional shared-token protection for `GET /events/latest` and `POST /events`. `GET /health` stays open. If `AURA_SENSOR_API_TOKEN` is not set, the API remains open with a runtime warning. Keep the API on a trusted local network only.

```powershell
python scripts/generate_sensor_api_token.py
python scripts/run_sensor_api.py
python scripts/test_sensor_api_auth.py
python scripts/test_sensor_api_client.py
```

Dev inspection commands:

```powershell
python scripts/list_recent_events.py
python scripts/list_action_logs.py
```

Install camera dependency in the Python 3.11 venv:

```powershell
pip install -r requirements.txt
```

## Run commands

```bash
python scripts/check_runtime.py
python scripts/test_device_event_bus.py
python scripts/test_escalation_engine.py
python scripts/test_safety_escalation_flow.py
python scripts/test_action_dispatcher.py
python scripts/test_full_safety_action_flow.py
python scripts/run_sensor_api.py
python scripts/generate_sensor_api_token.py
python scripts/test_sensor_api_auth.py
python scripts/test_sensor_api_client.py
python scripts/list_recent_events.py
python scripts/list_action_logs.py
python scripts/list_emergency_contacts.py
python scripts/test_people_registry.py
python scripts/test_guest_introduction_flow.py
python scripts/list_known_people.py
python scripts/test_camera.py
python scripts/open_latest_snapshot.py
python scripts/preview_camera.py
python scripts/capture_camera_observation.py
python scripts/reset_dev_memory.py
python scripts/init_memory.py
python scripts/test_memory.py
python scripts/test_reaction_engine.py
python scripts/test_style_learning.py
python scripts/test_context_relevance.py
python scripts/test_claude_provider.py
python scripts/test_llm_brain_adapter.py
python scripts/list_windows_voices.py
python scripts/test_tts.py
python scripts/test_stt.py
python scripts/run_companion_console.py
python scripts/run_voice_companion_console.py
```

If `reset_dev_memory.py` prints `AURA_DEV_MEMORY_RESET_BLOCKED`, the SQLite database is locked by another process. Stop the sensor API server with Ctrl+C, or kill the process using port 8787, then retry `python scripts/reset_dev_memory.py`.

Ollama is optional. If the configured brain is unavailable, AURA uses the local reaction fallback.

## Example console inputs

```
User message: I feel low today
Observation optional: User has been sitting quietly for a long time

User message: I am nervous about my presentation
Observation optional: User appears dressed for office/work mode
```
