import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.env_loader import load_env_file
from perception.tts import list_windows_voices


def main() -> None:
    load_env_file()
    voices = list_windows_voices()

    print("AURA_WINDOWS_VOICES")
    if not voices:
        print("AURA_WINDOWS_VOICES_NONE")
        return

    for voice in voices:
        print(f"- {voice}")


if __name__ == "__main__":
    main()
