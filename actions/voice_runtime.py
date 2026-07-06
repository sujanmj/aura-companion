from __future__ import annotations

import os

from config.env_loader import load_env_file

_ENABLED_VALUES = {"1", "true", "yes", "on"}


def voice_actions_enabled() -> bool:
    load_env_file()
    value = os.environ.get("AURA_ENABLE_VOICE_ACTIONS", "").strip().lower()
    return value in _ENABLED_VALUES


def create_runtime_speaker():
    if not voice_actions_enabled():
        print("AURA_VOICE_ACTIONS_DISABLED")
        return None

    try:
        from perception.tts import get_speaker_from_env

        speaker = get_speaker_from_env()
        print("AURA_VOICE_ACTIONS_ENABLED")
        return speaker
    except Exception as exc:
        print(f"AURA_VOICE_ACTIONS_ERROR: {exc}")
        return None
