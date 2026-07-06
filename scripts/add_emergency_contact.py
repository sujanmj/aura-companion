import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from memory.sqlite_store import AuraMemoryStore


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/add_emergency_contact.py "Name" "+911234567890" "relation"')
        raise SystemExit(1)

    name = sys.argv[1]
    phone = sys.argv[2] if len(sys.argv) > 2 else None
    relation = sys.argv[3] if len(sys.argv) > 3 else None

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    contact_id = store.add_emergency_contact(
        user_id,
        name=name,
        phone=phone,
        relation=relation,
        priority=1,
    )

    store.close()

    print("AURA_EMERGENCY_CONTACT_ADDED")
    print(f"contact_id={contact_id}")
    print(f"name={name}")
    print(f"phone={phone or '-'}")
    print(f"relation={relation or '-'}")


if __name__ == "__main__":
    main()
