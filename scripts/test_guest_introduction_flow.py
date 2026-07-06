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
            try:
                path.unlink()
            except PermissionError:
                pass


from companion.people_registry import PeopleRegistry
from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    reset_dev_memory()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    registry = PeopleRegistry(store)

    guest_prompt = registry.build_guest_prompt(user_id, room="front_door")

    introduced = registry.introduce_person(
        user_id,
        display_name="Sheetal",
        relation="friend",
        notes="Trusted friend.",
        trust_level="friend",
        consent_to_remember=True,
        room="hall",
    )
    registry.mark_person_seen(user_id, display_name="Sheetal", room="hall")

    print("AURA_GUEST_INTRODUCTION_FLOW_TEST_OK")
    print("GUEST PROMPT:")
    print(guest_prompt)
    print("INTRODUCED:")
    print(introduced)
    print("KNOWN PEOPLE:")
    for line in registry.format_known_people(user_id):
        print(f"- {line}")

    store.close()


if __name__ == "__main__":
    main()
