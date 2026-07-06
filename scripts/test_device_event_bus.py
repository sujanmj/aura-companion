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
from safety.safety_engine import SafetyEngine


TEST_EVENTS = (
    {
        "event_type": "pill_missed",
        "event_summary": "Morning medicine may have been missed.",
        "source": "medicine_schedule",
        "room": "bedroom",
        "severity": "medium",
        "requires_action": True,
    },
    {
        "event_type": "plant_moisture_low",
        "event_summary": "Balcony plant soil moisture is low.",
        "source": "plant_sensor",
        "room": "balcony",
        "severity": "low",
        "requires_action": True,
    },
    {
        "event_type": "fall_detected",
        "event_summary": "Possible fall detected in bedroom.",
        "source": "camera_pose_detector",
        "room": "bedroom",
        "severity": "high",
        "requires_action": True,
    },
)


def main() -> None:
    reset_dev_memory()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    event_bus = DeviceEventBus(store)
    safety_engine = SafetyEngine(store)

    for event_data in TEST_EVENTS:
        published = event_bus.publish_event(user_id, **event_data)
        evaluation = safety_engine.evaluate_event(user_id, published)

        print("EVENT:")
        print(f"- id={published['event_id']} type={published['event_type']}")
        print(f"  summary={published['event_summary']}")
        print(f"  severity={published['severity']} requires_action={published['requires_action']}")
        print("ACTION:")
        print(f"- type={evaluation.get('action_type')}")
        print(f"  summary={evaluation.get('action_summary')}")
        print(f"  requires_action={evaluation.get('requires_action')}")
        print()

    store.close()
    print("AURA_DEVICE_EVENT_BUS_TEST_OK")


if __name__ == "__main__":
    main()
