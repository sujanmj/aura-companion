import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from perception.tts import WindowsTTSSpeaker, get_selected_windows_voice


def main() -> None:
    selected_voice = get_selected_windows_voice()
    print(f"AURA_WINDOWS_VOICE={selected_voice or 'default'}")
    print("AURA_TTS_TEST_START")

    speaker = WindowsTTSSpeaker(enabled=True)
    success = speaker.speak("Hello Sujan. This is AURA. My local voice is working.")

    if success:
        print("AURA_TTS_TEST_OK")
    else:
        print("AURA_TTS_TEST_FAILED")


if __name__ == "__main__":
    main()
