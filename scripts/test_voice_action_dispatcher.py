import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from actions.action_dispatcher import ActionDispatcher
from memory.sqlite_store import AuraMemoryStore


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    def speak(self, text: str) -> bool:
        self.spoken.append(text)
        return True


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")

    fake_speaker = FakeSpeaker()
    with_speaker = ActionDispatcher(store, speaker=fake_speaker)
    spoken_result = with_speaker.dispatch(
        user_id,
        action_type="speak_now",
        action_summary="Fallback summary text.",
        speak_text="AURA voice action test.",
    )

    if spoken_result["status"] != "spoken":
        print(f"AURA_VOICE_ACTION_DISPATCHER_TEST_FAILED: expected spoken, got {spoken_result['status']}")
        raise SystemExit(1)

    if fake_speaker.spoken != ["AURA voice action test."]:
        print("AURA_VOICE_ACTION_DISPATCHER_TEST_FAILED: fake speaker text mismatch")
        raise SystemExit(1)

    without_speaker = ActionDispatcher(store)
    logged_result = without_speaker.dispatch(
        user_id,
        action_type="speak_now",
        action_summary="Logged only message.",
        speak_text="Should not be spoken.",
    )

    if logged_result["status"] != "logged":
        print(f"AURA_VOICE_ACTION_DISPATCHER_TEST_FAILED: expected logged, got {logged_result['status']}")
        raise SystemExit(1)

    store.close()
    print("AURA_VOICE_ACTION_DISPATCHER_TEST_OK")


if __name__ == "__main__":
    main()
