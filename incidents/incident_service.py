from __future__ import annotations

from typing import Any

from memory.sqlite_store import AuraMemoryStore


def incident_api_summary(incident: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": incident.get("id"),
        "title": incident.get("title"),
        "status": incident.get("status"),
        "severity": incident.get("severity"),
        "room": incident.get("room"),
    }


class IncidentService:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    @staticmethod
    def _event_id(event: dict[str, Any]) -> int | None:
        event_id = event.get("event_id") or event.get("id")
        return int(event_id) if event_id is not None else None

    @staticmethod
    def _room_label(room: str | None) -> str:
        if room and str(room).strip():
            return str(room).strip()
        return "unknown"

    def create_or_get_for_event(self, user_id: int, event: dict[str, Any]) -> dict[str, Any]:
        source_event_id = self._event_id(event)
        if source_event_id is not None:
            existing = self.store.get_incident_by_source_event_id(source_event_id)
            if existing is not None:
                return existing

        event_type = event.get("event_type") or "safety_event"
        room = event.get("room")
        room_label = self._room_label(room)
        title = f"{event_type} in {room_label}"
        event_summary = event.get("event_summary") or event.get("summary") or title

        incident_id = self.store.add_incident(
            user_id=user_id,
            source_event_id=source_event_id,
            incident_type=event_type,
            title=title,
            room=room,
            severity=event.get("severity"),
            status="open",
            summary=event_summary,
        )
        self.store.add_incident_timeline_item(
            incident_id,
            item_type="event_received",
            title="Event received",
            summary=event_summary,
            status=event.get("action_status") or "none",
            source_type="device_event",
            source_id=source_event_id,
        )
        incident = self.store.get_incident_by_id(incident_id)
        if incident is None:
            raise RuntimeError("failed to create incident")
        return incident

    def record_safety_plan(self, incident_id: int, safety_result: dict[str, Any]) -> None:
        if not safety_result:
            return
        self.store.add_incident_timeline_item(
            incident_id,
            item_type="safety_plan",
            title="Safety action planned",
            summary=safety_result.get("action_summary"),
            status=safety_result.get("action_type"),
        )

    def record_dispatch_results(
        self,
        incident_id: int,
        dispatch_results: list[dict[str, Any]],
    ) -> None:
        for result in dispatch_results:
            self.store.add_incident_timeline_item(
                incident_id,
                item_type="dispatch",
                title=str(result.get("action_type") or "dispatch"),
                summary=result.get("summary"),
                status=result.get("status"),
                source_type="action_log",
                source_id=result.get("action_log_id"),
            )

    def record_confirmation_requested(
        self,
        incident_id: int,
        confirmation: dict[str, Any],
    ) -> None:
        self.store.add_incident_timeline_item(
            incident_id,
            item_type="confirmation_requested",
            title="Confirmation requested",
            summary=confirmation.get("prompt"),
            status="pending",
            source_type="confirmation",
            source_id=confirmation.get("id"),
        )

    def _incident_for_confirmation(self, confirmation: dict[str, Any]) -> dict[str, Any] | None:
        source_event_id = confirmation.get("source_event_id")
        if source_event_id is None:
            return None
        return self.store.get_incident_by_source_event_id(int(source_event_id))

    def record_confirmation_resolved(
        self,
        confirmation: dict[str, Any],
        status: str,
        response_text: str | None = None,
    ) -> None:
        incident = self._incident_for_confirmation(confirmation)
        if incident is None:
            return

        incident_id = int(incident["id"])
        self.store.add_incident_timeline_item(
            incident_id,
            item_type="confirmation_resolved",
            title="Confirmation resolved",
            summary=response_text or status,
            status=status,
            source_type="confirmation",
            source_id=confirmation.get("id"),
        )

        if status == "confirmed_ok":
            self.store.update_incident_status(
                incident_id,
                "resolved",
                summary="User confirmed they are okay.",
                close=True,
            )
        elif status == "cancelled":
            self.store.update_incident_status(
                incident_id,
                "cancelled",
                summary="User cancelled the safety confirmation.",
                close=True,
            )
        elif status == "confirmed_escalate":
            self.store.update_incident_status(
                incident_id,
                "simulated_escalated",
                summary="Simulated escalation requested by user.",
                close=True,
            )

    def record_confirmation_timeout(self, confirmation: dict[str, Any]) -> None:
        incident = self._incident_for_confirmation(confirmation)
        if incident is None:
            return

        incident_id = int(incident["id"])
        self.store.add_incident_timeline_item(
            incident_id,
            item_type="confirmation_timeout",
            title="Confirmation timed out",
            summary="No response received before timeout.",
            status="expired",
            source_type="confirmation",
            source_id=confirmation.get("id"),
        )
        self.store.update_incident_status(
            incident_id,
            "expired",
            summary="Confirmation timed out with no user response.",
            close=True,
        )

    def record_timeout_dispatch_results(
        self,
        incident_id: int,
        timeout_action_log_id: int,
        notify_action_log_id: int,
    ) -> None:
        self.record_dispatch_results(
            incident_id,
            [
                {
                    "action_type": "confirmation_timeout",
                    "summary": "No response received before confirmation timeout.",
                    "status": "expired",
                    "action_log_id": timeout_action_log_id,
                },
                {
                    "action_type": "notify_contact_simulated",
                    "summary": "Confirmation timed out. Simulated emergency contact notification.",
                    "status": "simulated_notification_logged",
                    "action_log_id": notify_action_log_id,
                },
            ],
        )
