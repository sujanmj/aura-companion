import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from devices.event_bus import DeviceEventBus
from memory.sqlite_store import AuraMemoryStore
from safety.safety_engine import SafetyEngine

DEFAULT_SOURCES = {
    "pill_missed": "medicine_schedule",
    "plant_moisture_low": "plant_sensor",
    "fall_detected": "camera_pose_detector",
    "smoke_detected": "smoke_sensor",
    "fire_detected": "smoke_sensor",
    "gas_leak_detected": "gas_sensor",
    "heart_rate_high": "wearable_sensor",
    "unknown_person_detected": "camera",
}

DEFAULT_ROOMS = {
    "pill_missed": "bedroom",
    "plant_moisture_low": "balcony",
    "fall_detected": "bedroom",
    "unknown_person_detected": "front_door",
}

DEFAULT_SEVERITIES = {
    "pill_missed": "medium",
    "plant_moisture_low": "low",
    "fall_detected": "high",
    "smoke_detected": "critical",
    "fire_detected": "critical",
    "gas_leak_detected": "critical",
    "heart_rate_high": "medium",
    "unknown_person_detected": "medium",
}


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python scripts/simulate_sensor_event.py <event_type> <summary>")
        raise SystemExit(1)

    event_type = sys.argv[1]
    event_summary = sys.argv[2]

    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    event_bus = DeviceEventBus(store)
    safety_engine = SafetyEngine(store)

    published = event_bus.publish_event(
        user_id,
        event_type=event_type,
        event_summary=event_summary,
        source=DEFAULT_SOURCES.get(event_type, "manual_sensor"),
        room=DEFAULT_ROOMS.get(event_type),
        severity=DEFAULT_SEVERITIES.get(event_type, "low"),
        requires_action=True,
    )
    evaluation = safety_engine.evaluate_event(user_id, published)

    store.close()

    print("AURA_SENSOR_EVENT_SIMULATED")
    print(f"event_id={published['event_id']}")
    print(f"event_type={published['event_type']}")
    print(f"event_summary={published['event_summary']}")
    print(f"severity={published['severity']}")
    print(f"action_type={evaluation.get('action_type')}")
    print(f"action_summary={evaluation.get('action_summary')}")
    print(f"requires_action={evaluation.get('requires_action')}")


if __name__ == "__main__":
    main()
