import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from actions.voice_runtime import create_runtime_speaker, voice_actions_enabled


def main() -> None:
    if not voice_actions_enabled():
        print("AURA_LIVE_VOICE_SMOKE_SKIPPED")
        print("Set AURA_ENABLE_VOICE_ACTIONS=1 in config/keys.env to test real voice.")
        return

    speaker = create_runtime_speaker()
    if speaker is None:
        print("AURA_LIVE_VOICE_SMOKE_SKIPPED")
        print("Voice actions enabled but speaker could not be created.")
        return

    try:
        spoke = speaker.speak("AURA live voice safety actions are enabled.")
    except Exception as exc:
        print(f"AURA_LIVE_VOICE_SMOKE_ERROR: {exc}")
        return

    if not spoke:
        print("AURA_LIVE_VOICE_SMOKE_ERROR: speaker returned false")
        return

    print("AURA_LIVE_VOICE_SMOKE_OK")


if __name__ == "__main__":
    main()
