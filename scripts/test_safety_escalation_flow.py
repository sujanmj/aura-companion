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


from devices.event_bus import DeviceEventBus
from memory.sqlite_store import AuraMemoryStore
from safety.escalation_engine import EscalationEngine
from safety.safety_engine import SafetyEngine


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

    escalation_engine = EscalationEngine(store)
    escalation_engine.ensure_default_plans(user_id)

    event_bus = DeviceEventBus(store)
    safety_engine = SafetyEngine(store)

    published = event_bus.publish_event(
        user_id,
        event_type="fall_detected",
        event_summary="Possible fall detected in bedroom.",
        source="camera_pose_detector",
        room="bedroom",
        severity="high",
        confidence=0.8,
        requires_action=True,
    )
    safety_result = safety_engine.evaluate_event(user_id, published)
    escalation = escalation_engine.build_escalation_response(
        user_id,
        published,
        safety_result,
    )

    print("AURA_SAFETY_ESCALATION_FLOW_TEST_OK")
    print("EVENT:")
    print(f"- id={published['event_id']} type={published['event_type']}")
    print(f"  summary={published['event_summary']}")
    print(f"  severity={published['severity']} requires_action={published['requires_action']}")
    print("ACTION:")
    print(f"- type={safety_result.get('action_type')}")
    print(f"  summary={safety_result.get('action_summary')}")
    print(f"  requires_action={safety_result.get('requires_action')}")
    print("ESCALATION:")
    print(f"- severity={escalation.get('severity')}")
    print(f"  first_action={escalation.get('first_action')}")
    print(f"  second_action={escalation.get('second_action')}")
    print(f"  final_action={escalation.get('final_action')}")
    print(f"  contacts_available={escalation.get('contacts_available')}")
    print("SPOKEN RESPONSE:")
    print(escalation.get("spoken_response"))

    store.close()


if __name__ == "__main__":
    main()
