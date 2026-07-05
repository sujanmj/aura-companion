# AURA Companion

## Current milestones

- SQLite local memory engine
- Companion Reaction Engine v0.1
- Companion Console v0.1
- Response Style Learning v0.1
- LLM Brain Adapter v0.1

## Run commands

```bash
python scripts/reset_dev_memory.py
python scripts/init_memory.py
python scripts/test_memory.py
python scripts/test_reaction_engine.py
python scripts/test_style_learning.py
python scripts/test_llm_brain_adapter.py
python scripts/run_companion_console.py
```

Ollama is optional. If Ollama is not running, AURA uses the local reaction fallback.

## Example console inputs

```
User message: I feel low today
Observation optional: User has been sitting quietly for a long time

User message: I am nervous about my presentation
Observation optional: User appears dressed for office/work mode
```
