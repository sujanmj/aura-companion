import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from actions.action_dispatcher import ActionDispatcher
from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    dispatcher = ActionDispatcher(store)

    dispatches = (
        {
            "action_type": "speak_now",
            "action_summary": "Speak a welfare check message to the user.",
            "speak_text": "Sujan, are you okay?",
        },
        {
            "action_type": "ask_confirmation",
            "action_summary": "Ask user to confirm before notifying emergency contact.",
        },
        {
            "action_type": "notify_contact_simulated",
            "action_summary": "Simulated notification to top emergency contact.",
            "target": "Emergency Contact Test",
        },
        {
            "action_type": "plant_water_simulated",
            "action_summary": "Simulated plant watering for balcony plant.",
            "target": "balcony",
        },
    )

    for item in dispatches:
        result = dispatcher.dispatch(user_id, **item)
        print(f"DISPATCH: {result['action_type']}")
        print(f"  status={result['status']}")
        print(f"  action_log_id={result['action_log_id']}")
        print(f"  summary={result['summary']}")
        print()

    store.close()
    print("AURA_ACTION_DISPATCHER_TEST_OK")


if __name__ == "__main__":
    main()
