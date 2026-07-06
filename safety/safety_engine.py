from __future__ import annotations

from memory.sqlite_store import AuraMemoryStore

EMERGENCY_EVENT_TYPES = {"smoke_detected", "fire_detected", "gas_leak_detected"}


class SafetyEngine:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def evaluate_event(self, user_id: int, event: dict) -> dict:
        event_type = event.get("event_type", "")
        event_id = event.get("event_id")

        if event_type in EMERGENCY_EVENT_TYPES:
            severity = "critical"
            action_type = "emergency_alert"
            action_summary = (
                "Emergency risk detected. Alert trusted contacts and request user confirmation."
            )
        elif event_type == "fall_detected":
            severity = "high"
            action_type = "welfare_check"
            action_summary = (
                "Possible fall detected. Ask user if they are okay before escalating."
            )
        elif event_type == "heart_rate_high":
            severity = "medium"
            action_type = "health_check"
            action_summary = (
                "Unusual heart-rate signal. Ask user how they feel and monitor."
            )
        elif event_type == "pill_missed":
            severity = "medium"
            action_type = "reminder"
            action_summary = (
                "Medication may have been missed. Remind user gently."
            )
        elif event_type == "plant_moisture_low":
            severity = "low"
            action_type = "plant_care"
            action_summary = (
                "Plant soil moisture is low. Watering can be suggested or triggered if enabled."
            )
        elif event_type == "unknown_person_detected":
            severity = "medium"
            action_type = "security_check"
            action_summary = (
                "Unknown person detected. Notify user and record snapshot."
            )
        else:
            return {
                "requires_action": False,
                "action_type": "none",
                "action_summary": "No immediate safety action needed.",
                "severity": event.get("severity", "low"),
            }

        self.store.add_action_log(
            user_id,
            action_type=action_type,
            action_summary=action_summary,
            target=event.get("room"),
            status="planned",
            source_event_id=event_id,
        )

        return {
            "requires_action": True,
            "action_type": action_type,
            "action_summary": action_summary,
            "severity": severity,
        }
