import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from perception.tts import WindowsTTSSpeaker


def main() -> None:
    print("AURA_TTS_TEST_START")

    speaker = WindowsTTSSpeaker(enabled=True)
    success = speaker.speak("Hello Sujan. AURA voice output is working.")

    if success:
        print("AURA_TTS_TEST_OK")
    else:
        print("AURA_TTS_TEST_FAILED")


if __name__ == "__main__":
    main()
