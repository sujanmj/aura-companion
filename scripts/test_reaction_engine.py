import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from companion.reaction_engine import CompanionReactionEngine
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

    engine = CompanionReactionEngine(store)
    result = engine.generate_reaction(user_id)

    store.close()

    print("AURA_REACTION_ENGINE_TEST_OK")
    print()
    print("SITUATION:")
    print(result["situation"])
    print()
    print("EMOTIONAL NEED:")
    print(result["emotional_need"])
    print()
    print("TONE:")
    print(result["tone"])
    print()
    print("RESPONSE:")
    print(result["response"])
    print()
    print("REASONS:")
    for reason in result["reasons"]:
        print(f"- {reason}")


if __name__ == "__main__":
    main()
