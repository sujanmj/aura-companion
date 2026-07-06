import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    people = store.get_known_people(user_id)

    print("AURA_KNOWN_PEOPLE")
    if not people:
        print("- (none)")
    else:
        for person in people:
            consent = "yes" if person.get("consent_to_remember") else "no"
            last_seen = person.get("last_seen_at") or "never"
            print(
                f"- {person['display_name']} | {person.get('relation') or '-'} | "
                f"{person.get('trust_level')} | consent={consent} | last_seen={last_seen}"
            )

    store.close()


if __name__ == "__main__":
    main()
