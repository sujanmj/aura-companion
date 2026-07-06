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


def main() -> None:
    reset_dev_memory()

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    event_bus = DeviceEventBus(store)

    published = event_bus.publish_event(
        user_id,
        event_type="plant_moisture_low",
        event_summary="Balcony plant soil moisture is low.",
        source="action_status_test",
        room="balcony",
        severity="low",
        confidence=0.8,
        requires_action=True,
    )

    event_id = published["event_id"]
    initial = store.get_device_event_by_id(event_id)
    print(f"INITIAL status={initial.get('action_status') if initial else None}")

    store.update_device_event_action_status(event_id, "dispatched")
    updated = store.get_device_event_by_id(event_id)
    print(f"UPDATED status={updated.get('action_status') if updated else None}")

    if initial is None or initial.get("action_status") != "none":
        print("AURA_EVENT_ACTION_STATUS_TEST_ERROR: expected initial status=none")
        raise SystemExit(1)

    if updated is None or updated.get("action_status") != "dispatched":
        print("AURA_EVENT_ACTION_STATUS_TEST_ERROR: expected updated status=dispatched")
        raise SystemExit(1)

    store.close()
    print("AURA_EVENT_ACTION_STATUS_TEST_OK")


if __name__ == "__main__":
    main()
