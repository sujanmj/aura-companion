import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")

    store.add_conversation(
        user_id,
        role="user",
        message="I am nervous about tomorrow's presentation.",
        emotion_tag="anxious",
    )

    store.remember_fact(
        user_id,
        fact_key="presentation_anxiety",
        fact_value="Sujan felt nervous about an upcoming presentation and may need encouragement.",
        confidence=0.85,
        source="conversation",
    )

    store.add_observation(
        user_id,
        event_type="visual_context",
        event_summary="User appears dressed for office/work mode.",
        confidence=0.65,
        source="camera_mock",
    )

    store.add_mood_log(
        user_id,
        detected_mood="slightly_anxious",
        mood_reason="User mentioned nervousness about presentation.",
        confidence=0.8,
    )

    facts = store.get_memory_facts(user_id)
    observations = store.get_latest_observations(user_id)
    conversations = store.get_recent_conversations(user_id)

    store.close()

    print("AURA_MEMORY_TEST_OK")
    print("\nFACTS:")
    for item in facts:
        print(f"- {item['fact_key']}: {item['fact_value']}")

    print("\nOBSERVATIONS:")
    for item in observations:
        print(f"- {item['event_type']}: {item['event_summary']}")

    print("\nRECENT CONVERSATIONS:")
    for item in conversations:
        print(f"- {item['role']}: {item['message']} [{item['emotion_tag']}]")


if __name__ == "__main__":
    main()