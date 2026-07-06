from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from actions.voice_runtime import voice_actions_enabled
from memory.sqlite_store import AuraMemoryStore

EXPECTED_SERVICES = (
    "sensor_api",
    "live_safety_monitor",
    "confirmation_timeout_watcher",
)
DEFAULT_STALE_SECONDS = 20


class RuntimeHeartbeat:
    def __init__(self, store: AuraMemoryStore, user_id: int) -> None:
        self.store = store
        self.user_id = user_id

    def beat(
        self,
        service_name: str,
        status: str = "online",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.store.upsert_service_heartbeat(
            self.user_id,
            service_name,
            status=status,
            pid=os.getpid(),
            metadata=metadata,
        )


def _parse_sqlite_timestamp(value: str) -> datetime:
    parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return parsed.replace(tzinfo=timezone.utc)


def classify_heartbeat(row: dict[str, Any], stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict[str, Any]:
    classified = dict(row)
    status = (classified.get("status") or "online").lower()
    last_seen_at = classified.get("last_seen_at")

    if status != "online":
        classified["effective_status"] = status
        classified["age_seconds"] = _age_seconds_from_last_seen(last_seen_at)
        return classified

    age_seconds = _age_seconds_from_last_seen(last_seen_at)
    classified["age_seconds"] = age_seconds

    if last_seen_at is None or age_seconds is None:
        classified["effective_status"] = "stale"
        return classified

    if age_seconds > stale_seconds:
        classified["effective_status"] = "stale"
    else:
        classified["effective_status"] = "online"

    return classified


def _age_seconds_from_last_seen(last_seen_at: str | None) -> int | None:
    if not last_seen_at:
        return None
    try:
        last_seen = _parse_sqlite_timestamp(str(last_seen_at))
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    return max(0, int((now - last_seen).total_seconds()))


def build_runtime_health(
    store: AuraMemoryStore,
    user_id: int,
    stale_seconds: int = DEFAULT_STALE_SECONDS,
) -> dict[str, Any]:
    heartbeats = store.get_service_heartbeats(user_id)
    heartbeat_by_name = {row["service_name"]: row for row in heartbeats}

    services: list[dict[str, Any]] = []
    online_count = 0
    stale_count = 0
    missing_count = 0

    for service_name in EXPECTED_SERVICES:
        row = heartbeat_by_name.get(service_name)
        if row is None:
            services.append(
                {
                    "service_name": service_name,
                    "status": "missing",
                    "effective_status": "missing",
                    "pid": None,
                    "last_seen_at": None,
                    "started_at": None,
                    "age_seconds": None,
                    "metadata": None,
                }
            )
            missing_count += 1
            continue

        classified = classify_heartbeat(row, stale_seconds=stale_seconds)
        services.append(classified)
        effective_status = classified.get("effective_status")
        if effective_status == "online":
            online_count += 1
        elif effective_status == "stale":
            stale_count += 1
        else:
            missing_count += 1

    voice_enabled = voice_actions_enabled()
    services.append(
        {
            "service_name": "voice_actions",
            "status": "enabled" if voice_enabled else "disabled",
            "effective_status": "enabled" if voice_enabled else "disabled",
            "pid": None,
            "last_seen_at": None,
            "started_at": None,
            "age_seconds": None,
            "metadata": None,
        }
    )

    return {
        "services": services,
        "summary": {
            "online_count": online_count,
            "stale_count": stale_count,
            "missing_count": missing_count,
            "voice_enabled": voice_enabled,
        },
    }
