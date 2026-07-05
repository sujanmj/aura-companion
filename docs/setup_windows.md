# AURA Companion — Windows Setup

This guide helps you set up a local development environment on Windows using **Python 3.11**.

## Why Python 3.11?

- Phase 0 of AURA uses only the Python standard library and works on newer Python versions (including 3.14).
- **Python 3.11 is recommended** before adding camera, audio, and local AI packages such as OpenCV and Whisper. Those tools are more reliable on 3.11 today.

## Install Python 3.11

1. Download Python 3.11 from [python.org](https://www.python.org/downloads/).
2. During install, enable **Add python.exe to PATH** if prompted.
3. Verify:

```powershell
py -3.11 --version
```

## Create a virtual environment

From the project root (`C:\Users\sujan\aura-companion`):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
```

You should see Python 3.11.x.

## Local secrets (not committed)

Create `config/keys.env` locally for cloud brain and voice settings. This file is **ignored by git** and must never be committed.

Example keys (adjust for your setup):

```env
AURA_BRAIN_PROVIDER=claude
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=your_model_here
AURA_TTS_PROVIDER=windows
AURA_WINDOWS_VOICE=Microsoft Zira Desktop
```

## Quick smoke tests

With the virtual environment activated:

```powershell
python scripts/check_runtime.py
python scripts/test_claude_provider.py
python scripts/test_context_relevance.py
python scripts/test_tts.py
python scripts/test_stt.py
```

## Notes

- Python 3.14 may work for current standard-library features.
- Python 3.11 is the recommended baseline before adding camera/Whisper dependencies.
- `data/aura_memory.db` is local dev data and is ignored by git.
