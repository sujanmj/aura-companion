import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
DB_FILES = (
    "aura_memory.db",
    "aura_memory.db-wal",
    "aura_memory.db-shm",
)


def reset_dev_memory() -> None:
    for name in DB_FILES:
        path = DATA_DIR / name
        if path.exists():
            path.unlink()


from companion.reaction_engine import CompanionReactionEngine
from memory.sqlite_store import AuraMemoryStore

STYLE_FACTS = (
    (
        "preferred_response_style",
        "User prefers human-like, natural, warm, contextual responses that do not feel robotic or hardcoded.",
        0.95,
    ),
    (
        "disliked_response_style",
        "User dislikes fake robotic replies such as 'Formal clothes detected' or generic motivation without context.",
        0.95,
    ),
)


def ensure_style_facts(store: AuraMemoryStore, user_id: int) -> None:
    existing = {fact["fact_key"] for fact in store.get_memory_facts(user_id)}
    for fact_key, fact_value, confidence in STYLE_FACTS:
        if fact_key not in existing:
            store.remember_fact(
                user_id,
                fact_key=fact_key,
                fact_value=fact_value,
                confidence=confidence,
                source="setup",
            )


def main() -> None:
    reset_dev_memory()
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    ensure_style_facts(store, user_id)

    store.add_response_feedback(
        user_id,
        response_text="Formal clothes detected. All the best.",
        rating="bad",
        feedback_text="too robotic and fake",
        situation="work mode",
        tone="robotic",
    )

    store.add_conversation(
        user_id,
        role="user",
        message="I am nervous about my presentation today",
        emotion_tag="anxious",
    )

    store.remember_fact(
        user_id,
        fact_key="recent_anxiety",
        fact_value="User recently expressed anxiety or stress and may need calm encouragement.",
        confidence=0.75,
        source="conversation",
    )

    store.remember_fact(
        user_id,
        fact_key="important_work_event",
        fact_value="User mentioned an important work-related event and may appreciate encouragement before it.",
        confidence=0.8,
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
    feedback = store.get_recent_response_feedback(user_id, limit=5)

    store.close()

    banned_phrases = ("Formal clothes detected", "I detected", "According to my database")
    response = result["response"]
    for phrase in banned_phrases:
        if phrase.lower() in response.lower():
            raise AssertionError(f"Response contains banned phrase: {phrase}")

    print("AURA_STYLE_LEARNING_TEST_OK")
    print("RESPONSE:")
    print(response)
    print("RECENT FEEDBACK:")
    for item in feedback:
        note = item.get("feedback_text") or ""
        print(f"- {item['rating']}: {item['response_text']} ({note})")


if __name__ == "__main__":
    main()
