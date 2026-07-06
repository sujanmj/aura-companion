import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from devices.event_bus import DeviceEventBus
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
        event_summary="Possible fall detected in bedroom from confirmation engine test.",
        source="confirmation_engine_test",
        room="bedroom",
        severity="high",
        confidence=0.9,
        requires_action=True,
    )

    escalation_response = {
        "event_type": "fall_detected",
        "severity": "high",
        "first_action": "Ask user if they are okay.",
        "second_action": "If no response, notify top emergency contact.",
        "requires_user_confirmation": True,
        "spoken_response": "Sujan, are you okay after the possible fall?",
    }

    engine = ConfirmationEngine(store)
    confirmation = engine.create_for_event(user_id, published, escalation_response)

    if confirmation is None:
        print("AURA_CONFIRMATION_ENGINE_TEST_ERROR: expected confirmation")
        raise SystemExit(1)

    if confirmation.get("status") != "pending":
        print("AURA_CONFIRMATION_ENGINE_TEST_ERROR: expected pending status")
        raise SystemExit(1)

    result = engine.resolve_confirmation(user_id, int(confirmation["id"]), "ok")

    if result.get("status") != "confirmed_ok":
        print("AURA_CONFIRMATION_ENGINE_TEST_ERROR: expected confirmed_ok")
        raise SystemExit(1)

    updated = store.get_confirmation_request_by_id(int(confirmation["id"]))
    if updated is None or updated.get("status") != "confirmed_ok":
        print("AURA_CONFIRMATION_ENGINE_TEST_ERROR: confirmation not updated")
        raise SystemExit(1)

    store.close()
    print("AURA_CONFIRMATION_ENGINE_TEST_OK")


if __name__ == "__main__":
    main()
