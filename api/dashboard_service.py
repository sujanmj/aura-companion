from __future__ import annotations

from typing import Any

from memory.sqlite_store import AuraMemoryStore
from runtime.heartbeat import build_runtime_health

SEVERITY_RANK = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
    "unknown": 0,
}

DASHBOARD_VERSION = "0.1"


def _normalize_room(room: str | None) -> str:
    if not room or not str(room).strip():
        return "unknown"
    return str(room).strip()


def _severity_rank(severity: str | None) -> int:
    return SEVERITY_RANK.get((severity or "unknown").lower(), 0)


def _highest_severity(severities: list[str | None]) -> str:
    if not severities:
        return "unknown"
    return max((s or "unknown" for s in severities), key=_severity_rank)


def _build_critical_alerts(events: list[dict[str, Any]], limit: int = 10) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for event in events:
        severity = (event.get("severity") or "unknown").lower()
        if severity not in {"critical", "high"}:
            continue
        alerts.append(
            {
                "event_id": event.get("id"),
                "event_type": event.get("event_type"),
                "room": _normalize_room(event.get("room")),
                "severity": event.get("severity"),
                "action_status": event.get("action_status") or "none",
                "created_at": event.get("created_at"),
                "summary": event.get("event_summary"),
            }
        )
        if len(alerts) >= limit:
            break
    return alerts


class DashboardService:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def build_events(self, user_id: int, limit: int = 20) -> dict[str, Any]:
        events = self.store.get_recent_device_events(user_id, limit=limit)
        return {
            "ok": True,
            "service": "aura-dashboard",
            "version": DASHBOARD_VERSION,
            "events": events,
        }

    def build_actions(self, user_id: int, limit: int = 20) -> dict[str, Any]:
        actions = self.store.get_recent_action_logs(user_id, limit=limit)
        return {
            "ok": True,
            "service": "aura-dashboard",
            "version": DASHBOARD_VERSION,
            "actions": actions,
        }

    def build_rooms(self, user_id: int, limit: int = 50) -> dict[str, Any]:
        events = self.store.get_recent_device_events(user_id, limit=limit)
        rooms_map: dict[str, dict[str, Any]] = {}

        for event in events:
            room = _normalize_room(event.get("room"))
            entry = rooms_map.setdefault(
                room,
                {
                    "room": room,
                    "last_event_at": None,
                    "latest_event_type": None,
                    "highest_severity": "unknown",
                    "pending_count": 0,
                    "dispatched_count": 0,
                    "event_count": 0,
                    "_severities": [],
                },
            )

            entry["event_count"] += 1
            entry["_severities"].append(event.get("severity"))

            created_at = event.get("created_at")
            if entry["last_event_at"] is None or (
                created_at and str(created_at) > str(entry["last_event_at"])
            ):
                entry["last_event_at"] = created_at
                entry["latest_event_type"] = event.get("event_type")

            status = event.get("action_status") or "none"
            if status == "none":
                entry["pending_count"] += 1
            elif status == "dispatched":
                entry["dispatched_count"] += 1

        rooms: list[dict[str, Any]] = []
        for entry in rooms_map.values():
            severities = entry.pop("_severities")
            entry["highest_severity"] = _highest_severity(severities)
            rooms.append(entry)

        rooms.sort(key=lambda item: str(item.get("last_event_at") or ""), reverse=True)

        return {
            "ok": True,
            "service": "aura-dashboard",
            "version": DASHBOARD_VERSION,
            "rooms": rooms,
        }

    def build_status(self, user_id: int) -> dict[str, Any]:
        latest_events = self.store.get_recent_device_events(user_id, limit=20)
        pending_events = self.store.get_pending_device_events(user_id, limit=20)
        recent_actions = self.store.get_recent_action_logs(user_id, limit=20)
        pending_confirmations = self.store.get_pending_confirmation_requests(user_id, limit=20)
        recent_confirmations = self.store.get_recent_confirmation_requests(user_id, limit=20)
        recent_incidents = self.store.get_recent_incidents(user_id, limit=20)
        open_incidents = self.store.get_open_incidents(user_id, limit=20)
        rooms_data = self.build_rooms(user_id, limit=50)
        rooms = rooms_data["rooms"]

        critical_or_high_count = sum(
            1
            for event in latest_events
            if (event.get("severity") or "").lower() in {"critical", "high"}
        )

        runtime_health = build_runtime_health(self.store, user_id)
        health_summary = runtime_health["summary"]

        return {
            "ok": True,
            "service": "aura-dashboard",
            "version": DASHBOARD_VERSION,
            "summary": {
                "recent_event_count": len(latest_events),
                "pending_event_count": len(pending_events),
                "recent_action_count": len(recent_actions),
                "pending_confirmation_count": len(pending_confirmations),
                "recent_incident_count": len(recent_incidents),
                "open_incident_count": len(open_incidents),
                "critical_or_high_event_count": critical_or_high_count,
                "rooms_active_count": len(rooms),
                "service_online_count": health_summary.get("online_count", 0),
                "service_stale_count": health_summary.get("stale_count", 0),
                "service_missing_count": health_summary.get("missing_count", 0),
                "voice_enabled": health_summary.get("voice_enabled", False),
            },
            "latest_events": latest_events,
            "pending_events": pending_events,
            "pending_confirmations": pending_confirmations,
            "recent_confirmations": recent_confirmations,
            "recent_incidents": recent_incidents,
            "open_incidents": open_incidents,
            "recent_actions": recent_actions,
            "rooms": rooms,
            "critical_alerts": _build_critical_alerts(latest_events, limit=10),
            "runtime_health": runtime_health,
        }
