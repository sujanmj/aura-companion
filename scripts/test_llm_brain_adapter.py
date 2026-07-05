import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from config.env_loader import load_env_file

load_env_file()

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
            try:
                path.unlink()
            except PermissionError:
                pass


from companion.reaction_engine import CompanionReactionEngine
from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    reset_dev_memory()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")

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

    engine = CompanionReactionEngine(store, use_llm=True)
    result = engine.generate_reaction(user_id)

    store.close()

    print("AURA_LLM_BRAIN_ADAPTER_TEST_OK")
    print("RESPONSE:")
    print(result["response"])
    print("LLM/FALLBACK STATUS:")
    for reason in result["reasons"]:
        if "LLM" in reason:
            print(reason)


if __name__ == "__main__":
    main()
