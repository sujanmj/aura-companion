import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from companion.people_registry import PeopleRegistry
from memory.sqlite_store import AuraMemoryStore

FAMILY_RELATION_TERMS = ("family", "cousin", "mother", "father", "brother", "sister")


def infer_trust_level(relation: str | None) -> str:
    if not relation:
        return "guest"

    relation_lower = relation.lower()
    if any(term in relation_lower for term in FAMILY_RELATION_TERMS):
        return "family"
    return "guest"


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/introduce_person.py "Name" "relation" "notes"')
        raise SystemExit(1)

    display_name = sys.argv[1]
    relation = sys.argv[2] if len(sys.argv) > 2 else None
    notes = sys.argv[3] if len(sys.argv) > 3 else None
    trust_level = infer_trust_level(relation)

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    registry = PeopleRegistry(store)

    result = registry.introduce_person(
        user_id,
        display_name=display_name,
        relation=relation,
        notes=notes,
        trust_level=trust_level,
        consent_to_remember=False,
    )

    store.close()

    print("AURA_PERSON_INTRODUCED")
    print(f"person_id={result['person_id']}")
    print(f"name={result['display_name']}")
    print(f"relation={result.get('relation')}")
    print(f"trust_level={result.get('trust_level')}")


if __name__ == "__main__":
    main()
