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

BANNED_GREETING_TERMS = ("presentation", "work", "nervous", "anxiety")


def reset_dev_memory() -> None:
    for name in DB_FILES:
        path = DATA_DIR / name
        if path.exists():
            try:
                path.unlink()
            except PermissionError:
                pass


from companion.reaction_engine import CompanionReactionEngine
from memory.sqlite_store import AuraMemoryStore


def seed_old_facts(store: AuraMemoryStore, user_id: int) -> None:
    store.remember_fact(
        user_id,
        fact_key="presentation_anxiety",
        fact_value="Sujan felt nervous about an upcoming presentation and may need encouragement.",
        confidence=0.85,
        source="conversation",
    )
    store.remember_fact(
        user_id,
        fact_key="important_work_event",
        fact_value="User mentioned an important work-related event and may appreciate encouragement before it.",
        confidence=0.8,
        source="conversation",
    )
    store.remember_fact(
        user_id,
        fact_key="recent_anxiety",
        fact_value="User recently expressed anxiety or stress and may need calm encouragement.",
        confidence=0.75,
        source="conversation",
    )


def validate_greeting_response(response: str, label: str) -> None:
    lowered = response.lower()
    for term in BANNED_GREETING_TERMS:
        if term in lowered:
            raise AssertionError(f"{label} should not mention '{term}'")


def main() -> None:
    reset_dev_memory()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    seed_old_facts(store, user_id)

    store.add_conversation(
        user_id,
        role="user",
        message="hello aura how are you?",
    )

    local_engine = CompanionReactionEngine(store, use_llm=False)
    llm_engine = CompanionReactionEngine(store, use_llm=True)

    local_result = local_engine.generate_reaction(user_id)
    llm_result = llm_engine.generate_reaction(user_id)

    validate_greeting_response(local_result["response"], "LOCAL_GREETING_RESPONSE")
    validate_greeting_response(llm_result["response"], "LLM_GREETING_RESPONSE")

    print("AURA_CONTEXT_RELEVANCE_TEST_OK")
    print("LOCAL_GREETING_RESPONSE:")
    print(local_result["response"])
    print("LLM_GREETING_RESPONSE:")
    print(llm_result["response"])

    store.add_conversation(
        user_id,
        role="user",
        message="I am nervous about my presentation today",
        emotion_tag="anxious",
    )

    relevant_result = local_engine.generate_reaction(user_id)
    print("RELEVANT_RESPONSE:")
    print(relevant_result["response"])

    store.close()


if __name__ == "__main__":
    main()
