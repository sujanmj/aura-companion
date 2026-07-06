import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from actions.voice_runtime import voice_actions_enabled
from config.env_loader import load_env_file


def main() -> None:
    load_env_file()
    env_value = os.environ.get("AURA_ENABLE_VOICE_ACTIONS")
    enabled = voice_actions_enabled()

    print(f"AURA_VOICE_ACTIONS_ENV={env_value if env_value is not None else 'missing'}")
    print(f"AURA_VOICE_ACTIONS_ENABLED={str(enabled).lower()}")
    print("AURA_VOICE_RUNTIME_CONFIG_TEST_OK")


if __name__ == "__main__":
    main()
