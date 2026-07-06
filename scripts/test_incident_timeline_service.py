import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from devices.event_bus import DeviceEventBus
from incidents.incident_service import IncidentService
from memory.sqlite_store import AuraMemoryStore
from safety.confirmation_engine import ConfirmationEngine


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    event_bus = DeviceEventBus(store)
    published = event_bus.publish_event(
        user_id,
        event_type="fall_detected",
        event_summary="Possible fall detected in bedroom from incident timeline test.",
        source="incident_timeline_test",
        room="bedroom",
        severity="high",
        confidence=0.9,
        requires_action=True,
    )

    incident_service = IncidentService(store)
    incident = incident_service.create_or_get_for_event(user_id, published)

    safety_result = {
        "requires_action": True,
        "action_type": "welfare_check",
        "action_summary": "Possible fall detected. Ask user if they are okay before escalating.",
        "severity": "high",
    }
    incident_service.record_safety_plan(int(incident["id"]), safety_result)

    dispatch_results = [
        {
            "action_log_id": 9001,
            "action_type": "speak_now",
            "status": "logged",
            "summary": "Sujan, are you okay?",
        }
    ]
    incident_service.record_dispatch_results(int(incident["id"]), dispatch_results)

    confirmation = {
        "id": 9002,
        "source_event_id": published["event_id"],
        "prompt": "Sujan, are you okay after the possible fall?",
        "status": "pending",
    }
    incident_service.record_confirmation_requested(int(incident["id"]), confirmation)

    engine = ConfirmationEngine(store)
    real_confirmation = engine.create_for_event(
        user_id,
        published,
        {
            "requires_user_confirmation": True,
            "spoken_response": "Resolve test confirmation.",
            "first_action": "Ask user if okay.",
            "wait_seconds_before_escalation": 60,
            "severity": "high",
        },
    )
    if real_confirmation is not None:
        engine.resolve_confirmation(user_id, int(real_confirmation["id"]), "ok")

    timeline = store.get_incident_timeline_items(int(incident["id"]), limit=100)
    item_types = {item.get("item_type") for item in timeline}

    required_types = {"event_received", "safety_plan", "dispatch", "confirmation_requested"}
    missing = required_types - item_types
    if missing:
        print(f"AURA_INCIDENT_TIMELINE_SERVICE_TEST_ERROR: missing timeline types {missing}")
        raise SystemExit(1)

    print("INCIDENT TIMELINE:")
    for item in timeline:
        print(
            f"- {item.get('created_at')} | {item.get('item_type')} | "
            f"{item.get('title')} | status={item.get('status')}"
        )

    store.close()
    print("AURA_INCIDENT_TIMELINE_SERVICE_TEST_OK")


if __name__ == "__main__":
    main()
