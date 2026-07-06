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

Secrets live in `config/keys.env`. That file is ignored by git.

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

Install camera dependency in the Python 3.11 venv:

```powershell
pip install -r requirements.txt
```

## Run commands

```bash
python scripts/check_runtime.py
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

Ollama is optional. If the configured brain is unavailable, AURA uses the local reaction fallback.

## Example console inputs

```
User message: I feel low today
Observation optional: User has been sitting quietly for a long time

User message: I am nervous about my presentation
Observation optional: User appears dressed for office/work mode
```
