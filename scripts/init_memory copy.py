import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")

    store.remember_fact(user_id, "preferred_name", "Sujan", confidence=1.0, source="setup")
    store.remember_fact(user_id, "project", "AURA Companion", confidence=1.0, source="setup")
    store.remember_fact(
        user_id,
        "preferred_response_style",
        "User prefers human-like, natural, warm, contextual responses that do not feel robotic or hardcoded.",
        confidence=0.95,
        source="setup",
    )
    store.remember_fact(
        user_id,
        "disliked_response_style",
        "User dislikes fake robotic replies such as 'Formal clothes detected' or generic motivation without context.",
        confidence=0.95,
        source="setup",
    )
    store.remember_fact(
        user_id,
        "companion_personality",
        "AURA should feel like a loyal virtual human companion: emotionally present, calm, encouraging, practical, and not overly sweet.",
        confidence=0.9,
        source="setup",
    )
    store.remember_routine(user_id, "gym_time", "around 7 PM", confidence=0.8)
    store.remember_routine(user_id, "work_mode", "office/formal clothes usually means work context", confidence=0.7)

    store.close()

    print("AURA_MEMORY_INIT_OK")
    print(f"user_id={user_id}")


if __name__ == "__main__":
    main()