from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from incidents.incident_service import IncidentService
from memory.sqlite_store import AuraMemoryStore

OK_RESPONSES = {"ok", "i_am_ok", "safe"}
ESCALATE_RESPONSES = {"notify", "escalate"}
CANCEL_RESPONSES = {"cancel"}
DEFAULT_CONFIRMATION_WAIT_SECONDS = 30
TIMEOUT_RESPONSE_TEXT = "No response before timeout."


class ConfirmationEngine:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    @staticmethod
    def _wait_seconds_from_escalation(escalation_response: dict[str, Any]) -> int:
        wait_seconds = escalation_response.get("wait_seconds_before_escalation")
        if wait_seconds is None or int(wait_seconds) <= 0:
            return DEFAULT_CONFIRMATION_WAIT_SECONDS
        return int(wait_seconds)

    @staticmethod
    def _expires_at_from_wait_seconds(wait_seconds: int) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=wait_seconds)
        return expires_at.strftime("%Y-%m-%d %H:%M:%S")

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
        wait_seconds = self._wait_seconds_from_escalation(escalation_response)
        expires_at = self._expires_at_from_wait_seconds(wait_seconds)

        confirmation_id = self.store.add_confirmation_request(
            user_id=user_id,
            source_event_id=source_event_id,
            confirmation_type=event_type,
            prompt=prompt,
            expires_at=expires_at,
            metadata=metadata,
        )
        return self.store.get_confirmation_request_by_id(confirmation_id)

    def expire_due_confirmations(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        due_confirmations = self.store.get_expired_pending_confirmation_requests(
            user_id,
            limit=limit,
        )
        results: list[dict[str, Any]] = []

        for confirmation in due_confirmations:
            confirmation_id = int(confirmation["id"])
            confirmation_type = confirmation.get("confirmation_type")
            source_event_id = confirmation.get("source_event_id")

            self.store.update_confirmation_request_status(
                confirmation_id,
                "expired",
                response_text=TIMEOUT_RESPONSE_TEXT,
            )
            timeout_action_log_id = self.store.add_action_log(
                user_id,
                action_type="confirmation_timeout",
                action_summary="No response received before confirmation timeout.",
                target=confirmation_type,
                status="expired",
                source_event_id=source_event_id,
            )
            notify_action_log_id = self.store.add_action_log(
                user_id,
                action_type="notify_contact_simulated",
                action_summary="Confirmation timed out. Simulated emergency contact notification.",
                target=confirmation_type,
                status="simulated_notification_logged",
                source_event_id=source_event_id,
            )

            updated = self.store.get_confirmation_request_by_id(confirmation_id)
            incident_service = IncidentService(self.store)
            incident_service.record_confirmation_timeout(updated)
            incident = incident_service._incident_for_confirmation(updated)
            if incident is not None:
                incident_service.record_timeout_dispatch_results(
                    int(incident["id"]),
                    timeout_action_log_id,
                    notify_action_log_id,
                )

            results.append(
                {
                    "confirmation_id": confirmation_id,
                    "status": "expired",
                    "confirmation": updated,
                    "timeout_action_log_id": timeout_action_log_id,
                    "notify_action_log_id": notify_action_log_id,
                }
            )

        return results

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
        IncidentService(self.store).record_confirmation_resolved(
            updated or confirmation,
            status,
            response_text=response,
        )

        return {
            "confirmation_id": confirmation_id,
            "status": status,
            "response": response,
            "action_log_id": action_log_id,
            "confirmation": updated,
        }
