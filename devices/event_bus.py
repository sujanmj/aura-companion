from __future__ import annotations

from memory.sqlite_store import AuraMemoryStore


class DeviceEventBus:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def publish_event(
        self,
        user_id: int,
        event_type: str,
        event_summary: str,
        source: str = "manual",
        room: str | None = None,
        severity: str = "low",
        confidence: float = 0.5,
        requires_action: bool = False,
        metadata: dict | None = None,
    ) -> dict:
        event_id = self.store.add_device_event(
            user_id,
            event_type=event_type,
            event_summary=event_summary,
            source=source,
            room=room,
            severity=severity,
            confidence=confidence,
            requires_action=requires_action,
            metadata=metadata,
        )

        self.store.add_observation(
            user_id,
            event_type=event_type,
            event_summary=event_summary,
            confidence=confidence,
            source=source,
        )

        return {
            "event_id": event_id,
            "event_type": event_type,
            "event_summary": event_summary,
            "severity": severity,
            "requires_action": requires_action,
            "room": room,
        }

    def get_pending_events(self, user_id: int, limit: int = 20) -> list[dict]:
        return self.store.get_pending_device_events(user_id, limit=limit)

    def mark_event_status(self, event_id: int, action_status: str) -> None:
        self.store.update_device_event_action_status(event_id, action_status)
