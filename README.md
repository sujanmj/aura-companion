# AURA Companion

## Current milestones

- SQLite local memory engine
- Companion Reaction Engine v0.1
- Companion Console v0.1
- Response Style Learning v0.1
- LLM Brain Adapter v0.1
- Cloud Brain Provider v0.1
- Voice Output v0.1

Secrets live in `config/keys.env`. That file is ignored by git.

When `AURA_BRAIN_PROVIDER=claude`, Claude is the primary cloud brain. You must also set `ANTHROPIC_MODEL` in `config/keys.env`. If Claude fails or is unavailable, AURA falls back to the local reaction engine.

Voice output uses built-in Windows `System.Speech` through PowerShell. `AURA_TTS_PROVIDER` defaults to `windows`.

## Run commands

```bash
python scripts/reset_dev_memory.py
python scripts/init_memory.py
python scripts/test_memory.py
python scripts/test_reaction_engine.py
python scripts/test_style_learning.py
python scripts/test_claude_provider.py
python scripts/test_llm_brain_adapter.py
python scripts/test_tts.py
python scripts/run_companion_console.py
```

Ollama is optional. If the configured brain is unavailable, AURA uses the local reaction fallback.

## Example console inputs

```
User message: I feel low today
Observation optional: User has been sitting quietly for a long time

User message: I am nervous about my presentation
Observation optional: User appears dressed for office/work mode
```
