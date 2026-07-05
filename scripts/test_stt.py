import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from perception.stt import WindowsSpeechRecognizer


def main() -> None:
    print("AURA_STT_TEST_START")
    print("Speak a short sentence after the beep/notice.")

    recognizer = WindowsSpeechRecognizer(timeout_seconds=8)
    text = recognizer.listen_once()

    if text:
        print("AURA_STT_TEST_OK")
        print("TRANSCRIPT:")
        print(text)
        print("NOTE:")
        print("Windows local STT may be inaccurate. In companion console, AURA asks confirmation before storing/responding.")
    else:
        print("AURA_STT_TEST_NO_SPEECH")
        print("Mic recognition returned nothing. Check microphone permission/input device.")


if __name__ == "__main__":
    main()
