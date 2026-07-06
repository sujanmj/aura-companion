from __future__ import annotations

from typing import Any

from memory.sqlite_store import AuraMemoryStore

OK_RESPONSES = {"ok", "i_am_ok", "safe"}
ESCALATE_RESPONSES = {"notify", "escalate"}
CANCEL_RESPONSES = {"cancel"}


class ConfirmationEngine:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def create_for_event(
        self,
        user_id: int,
        event: dict[str, Any],
        escalation_response: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not escalation_response.get("requires_user_confirmation"):
            return None

        event_type = event.get("event_type") or "safety_confirmation"
        source_event_id = event.get("event_id") or event.get("id")
        prompt = (
            escalation_response.get("spoken_response")
            or escalation_response.get("first_action")
            or "Please confirm your safety status."
        )
        metadata = {
            "event_type": event_type,
            "severity": escalation_response.get("severity"),
            "first_action": escalation_response.get("first_action"),
            "second_action": escalation_response.get("second_action"),
        }

        confirmation_id = self.store.add_confirmation_request(
            user_id=user_id,
            source_event_id=source_event_id,
            confirmation_type=event_type,
            prompt=prompt,
            metadata=metadata,
        )
        return self.store.get_confirmation_request_by_id(confirmation_id)

    def resolve_confirmation(
        self,
        user_id: int,
        confirmation_id: int,
        response: str,
    ) -> dict[str, Any]:
        confirmation = self.store.get_confirmation_request_by_id(confirmation_id)
        if confirmation is None or int(confirmation["user_id"]) != int(user_id):
            raise ValueError("confirmation_not_found")

        if confirmation.get("status") != "pending":
            raise ValueError("confirmation_not_pending")

        normalized = (response or "").strip().lower()
        source_event_id = confirmation.get("source_event_id")

        if normalized in OK_RESPONSES:
            status = "confirmed_ok"
            action_type = "confirmation_ok"
            action_status = "resolved"
            action_summary = "User confirmed they are okay."
        elif normalized in ESCALATE_RESPONSES:
            status = "confirmed_escalate"
            action_type = "confirmation_escalate"
            action_status = "simulated_escalation_requested"
            action_summary = "Simulated escalation requested by user confirmation."
        elif normalized in CANCEL_RESPONSES:
            status = "cancelled"
            action_type = "confirmation_cancelled"
            action_status = "resolved"
            action_summary = "User cancelled the safety confirmation request."
        else:
            raise ValueError("invalid_response")

        self.store.update_confirmation_request_status(
            confirmation_id,
            status,
            response_text=response,
        )
        action_log_id = self.store.add_action_log(
            user_id,
            action_type=action_type,
            action_summary=action_summary,
            target=confirmation.get("confirmation_type"),
            status=action_status,
            source_event_id=source_event_id,
        )

        updated = self.store.get_confirmation_request_by_id(confirmation_id)
        return {
            "confirmation_id": confirmation_id,
            "status": status,
            "response": response,
            "action_log_id": action_log_id,
            "confirmation": updated,
        }
