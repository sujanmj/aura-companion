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
from monitor.live_safety_monitor import LiveSafetyMonitor


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

    event_bus = DeviceEventBus(store)
    published = event_bus.publish_event(
        user_id,
        event_type="fall_detected",
        event_summary="Possible fall detected in bedroom from live monitor test.",
        source="live_monitor_test",
        room="bedroom",
        severity="high",
        confidence=0.82,
        requires_action=True,
    )

    event_id = published["event_id"]
    initial = store.get_device_event_by_id(event_id)
    print(f"INITIAL action_status={initial.get('action_status') if initial else None}")

    monitor = LiveSafetyMonitor(store)

    for _ in range(200):
        current = store.get_device_event_by_id(event_id)
        if current and current.get("action_status") != "none":
            break
        batch = monitor.process_once(user_id, limit=1)
        if not batch:
            break

    updated = store.get_device_event_by_id(event_id)
    print(f"UPDATED action_status={updated.get('action_status') if updated else None}")
    print("RESULT:")
    print(
        {
            "event_id": event_id,
            "event_type": updated.get("event_type") if updated else None,
            "status": updated.get("action_status") if updated else None,
        }
    )

    if initial is None or initial.get("action_status") != "none":
        print("AURA_LIVE_SAFETY_MONITOR_TEST_ERROR: expected initial action_status=none")
        raise SystemExit(1)

    if updated is None or updated.get("action_status") != "dispatched":
        print("AURA_LIVE_SAFETY_MONITOR_TEST_ERROR: expected updated action_status=dispatched")
        raise SystemExit(1)

    store.close()
    print("AURA_LIVE_SAFETY_MONITOR_TEST_OK")


if __name__ == "__main__":
    main()
