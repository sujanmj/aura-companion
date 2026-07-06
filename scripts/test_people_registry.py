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

    introduced = registry.introduce_person(
        user_id,
        display_name="Rohan",
        relation="cousin",
        notes="Family member, allowed in hall and kitchen.",
        trust_level="family",
        consent_to_remember=True,
        room="hall",
    )
    print("INTRODUCED:")
    print(introduced)

    known_seen = registry.mark_person_seen(user_id, display_name="Rohan", room="hall")
    print("KNOWN SEEN:")
    print(known_seen)

    unknown_seen = registry.mark_person_seen(
        user_id,
        display_name="Unknown Visitor",
        room="front_door",
    )
    print("UNKNOWN SEEN:")
    print(unknown_seen)

    print("KNOWN PEOPLE:")
    for person in store.get_known_people(user_id):
        print(
            f"- {person['display_name']} | {person.get('relation')} | "
            f"{person.get('trust_level')} | consent={bool(person.get('consent_to_remember'))}"
        )

    print("PERSON EVENTS:")
    for event in store.get_recent_person_events(user_id):
        print(
            f"- {event['event_type']}: {event['event_summary']} "
            f"(person_id={event.get('person_id')}, room={event.get('room')})"
        )

    store.close()
    print("AURA_PEOPLE_REGISTRY_TEST_OK")


if __name__ == "__main__":
    main()
