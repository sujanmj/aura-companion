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


from memory.sqlite_store import AuraMemoryStore
from safety.escalation_engine import EscalationEngine


TEST_EVENTS = (
    {
        "event_type": "fall_detected",
        "severity": "high",
        "requires_action": True,
        "event_summary": "Possible fall detected in bedroom.",
    },
    {
        "event_type": "fire_detected",
        "severity": "critical",
        "requires_action": True,
        "event_summary": "Possible fire detected in kitchen.",
    },
    {
        "event_type": "unknown_person_with_possible_weapon",
        "severity": "high",
        "requires_action": True,
        "event_summary": "Unknown person with possible weapon near front door.",
    },
    {
        "event_type": "pill_missed",
        "severity": "medium",
        "requires_action": True,
        "event_summary": "Morning medicine may have been missed.",
    },
)


def main() -> None:
    reset_dev_memory()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    store.add_emergency_contact(
        user_id,
        name="Emergency Contact Test",
        phone="+910000000000",
        relation="family",
        priority=1,
    )

    engine = EscalationEngine(store)
    engine.ensure_default_plans(user_id)

    for event_data in TEST_EVENTS:
        event_id = store.add_device_event(
            user_id,
            event_type=event_data["event_type"],
            event_summary=event_data["event_summary"],
            severity=event_data["severity"],
            requires_action=event_data["requires_action"],
        )
        event = {
            "event_id": event_id,
            "event_type": event_data["event_type"],
            "severity": event_data["severity"],
            "requires_action": event_data["requires_action"],
        }
        safety_result = {
            "requires_action": event["requires_action"],
            "severity": event["severity"],
            "action_summary": f"Planned safety action for {event['event_type']}.",
        }
        response = engine.build_escalation_response(user_id, event, safety_result)

        print(f"EVENT: {event['event_type']}")
        print(f"SEVERITY: {response['severity']}")
        print(f"FIRST ACTION: {response['first_action']}")
        print(f"CONTACTS AVAILABLE: {response['contacts_available']}")
        print(f"TOP CONTACT: {response.get('top_contact')}")
        print(f"SPOKEN: {response['spoken_response']}")
        print()

    store.close()
    print("AURA_ESCALATION_ENGINE_TEST_OK")


if __name__ == "__main__":
    main()
