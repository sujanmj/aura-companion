import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    contacts = store.get_emergency_contacts(user_id)

    print("AURA_EMERGENCY_CONTACTS")
    if not contacts:
        print("- (none)")
    else:
        for contact in contacts:
            print(
                f"- {contact.get('priority')} | {contact['name']} | "
                f"{contact.get('relation') or '-'} | {contact.get('phone') or '-'} | "
                f"{contact.get('email') or '-'}"
            )

    store.close()


if __name__ == "__main__":
    main()
