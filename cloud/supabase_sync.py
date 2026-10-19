"""Best-effort server-side sync for AURA conversations and sensor events."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def _configuration() -> tuple[str, str, str] | None:
    url = os.environ.get("AURA_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("AURA_SUPABASE_SERVICE_ROLE_KEY", "")
    device_id = os.environ.get("AURA_CLOUD_DEVICE_ID", "")
    if not (url and key and device_id):
        return None
    if not url.startswith("https://") or len(device_id) > 100:
        return None
    return url, key, device_id


def _upsert(table: str, conflict: str, row: dict[str, Any]) -> bool:
    config = _configuration()
    if not config:
        return False
    url, key, device_id = config
    endpoint = f"{url}/rest/v1/{table}?on_conflict={conflict}"
    payload = {"device_id": device_id, **row}
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
            "content-type": "application/json",
            "prefer": "resolution=merge-duplicates,return=minimal",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        # Do not print response bodies, URLs, keys, or user content into logs.
        print("AURA_CLOUD_SYNC_FAILED: cloud record was not synchronized")
        return False


def sync_conversation(local_id: int, role: str, message: str, created_at: str) -> bool:
    if role not in {"user", "assistant"} or not 1 <= len(message) <= 8000:
        return False
    return _upsert(
        "aura_conversations",
        "device_id,local_id",
        {"local_id": int(local_id), "role": role, "message": message, "created_at": created_at},
    )


def sync_sensor_event(event: dict[str, Any]) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    summary = event.get("event_summary")
    if not isinstance(event_id, int) or not isinstance(event_type, str) or not isinstance(summary, str):
        return False
    return _upsert(
        "aura_sensor_events",
        "device_id,local_id",
        {
            "local_id": event_id,
            "event_type": event_type[:100],
            "event_summary": summary[:1000],
            "source": str(event.get("source", "unknown"))[:100],
            "room": str(event.get("room", ""))[:100] or None,
            "severity": str(event.get("severity", "low"))[:30],
            "confidence": float(event.get("confidence", 0.5)),
            "created_at": str(event.get("created_at", "")) or None,
        },
    )
