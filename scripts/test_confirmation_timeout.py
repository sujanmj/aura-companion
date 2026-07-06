import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from devices.event_bus import DeviceEventBus
from memory.sqlite_store import AuraMemoryStore
from monitor.confirmation_timeout_watcher import ConfirmationTimeoutWatcher
from safety.confirmation_engine import ConfirmationEngine


def main() -> None:
    store = AuraMemoryStore()
    store.apply_schema()

    user_id = store.get_or_create_user(name="Sujan M J", preferred_name="Sujan")
    event_bus = DeviceEventBus(store)
    published = event_bus.publish_event(
        user_id,
        event_type="fall_detected",
        event_summary="Possible fall detected in bedroom from confirmation timeout test.",
        source="confirmation_timeout_test",
        room="bedroom",
        severity="high",
        confidence=0.9,
        requires_action=True,
    )

    escalation_response = {
        "event_type": "fall_detected",
        "severity": "high",
        "first_action": "Ask user if okay.",
        "second_action": "Notify contact if no response.",
        "requires_user_confirmation": True,
        "spoken_response": "Timeout test confirmation.",
        "wait_seconds_before_escalation": 1,
    }

    engine = ConfirmationEngine(store)
    confirmation = engine.create_for_event(user_id, published, escalation_response)

    if confirmation is None:
        print("AURA_CONFIRMATION_TIMEOUT_TEST_ERROR: expected confirmation")
        raise SystemExit(1)

    if confirmation.get("status") != "pending":
        print("AURA_CONFIRMATION_TIMEOUT_TEST_ERROR: expected pending status")
        raise SystemExit(1)

    time.sleep(2)

    watcher = ConfirmationTimeoutWatcher(store)
    results = watcher.process_once(user_id, limit=5)

    if not results:
        print("AURA_CONFIRMATION_TIMEOUT_TEST_ERROR: expected expired confirmation")
        raise SystemExit(1)

    updated = store.get_confirmation_request_by_id(int(confirmation["id"]))
    if updated is None or updated.get("status") != "expired":
        print("AURA_CONFIRMATION_TIMEOUT_TEST_ERROR: expected expired status")
        raise SystemExit(1)

    recent_actions = store.get_recent_action_logs(user_id, limit=20)
    action_types = {action.get("action_type") for action in recent_actions}

    if "confirmation_timeout" not in action_types:
        print("AURA_CONFIRMATION_TIMEOUT_TEST_ERROR: missing confirmation_timeout action")
        raise SystemExit(1)

    if "notify_contact_simulated" not in action_types:
        print("AURA_CONFIRMATION_TIMEOUT_TEST_ERROR: missing notify_contact_simulated action")
        raise SystemExit(1)

    store.close()
    print("AURA_CONFIRMATION_TIMEOUT_TEST_OK")


if __name__ == "__main__":
    main()
