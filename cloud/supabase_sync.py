"""Best-effort immediate sync with a durable, reference-only retry outbox."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT / "data" / "aura_memory.db"
OUTBOX_TABLE = "cloud_sync_outbox"
_flush_lock = threading.Lock()
_worker_lock = threading.Lock()
_worker_started = False


def _configuration() -> tuple[str, str, str] | None:
    url = os.environ.get("AURA_SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("AURA_SUPABASE_SERVICE_ROLE_KEY", "")
    device_id = os.environ.get("AURA_CLOUD_DEVICE_ID", "")
    if not (url and key and device_id):
        return None
    if not url.startswith("https://") or len(device_id) > 100:
        return None
    return url, key, device_id


def _database_path() -> Path:
    return Path(os.environ.get("AURA_DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()


def _ensure_outbox(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""CREATE TABLE IF NOT EXISTS {OUTBOX_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL CHECK(record_type IN ('conversation', 'sensor_event', 'conversation_delete')),
            local_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at REAL NOT NULL DEFAULT 0,
            UNIQUE(record_type, local_id, device_id)
        )"""
    )
    conn.commit()


def _open_outbox() -> sqlite3.Connection | None:
    path = _database_path()
    if not path.is_file():
        return None
    conn = sqlite3.connect(path, timeout=3)
    conn.row_factory = sqlite3.Row
    _ensure_outbox(conn)
    return conn


def _upsert(
    table: str,
    conflict: str,
    row: dict[str, Any],
    device_id: str | None = None,
) -> bool:
    config = _configuration()
    if not config:
        return False
    url, key, configured_device_id = config
    endpoint = f"{url}/rest/v1/{table}?on_conflict={conflict}"
    payload = {"device_id": device_id or configured_device_id, **row}
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
        # Never print response bodies, URLs, keys, prompts, or user content.
        return False


def _delete_remote_conversation(local_id: int, device_id: str) -> bool:
    config = _configuration()
    if not config:
        return False
    url, key, _ = config
    query = urlencode({
        "device_id": f"eq.{device_id}",
        "local_id": f"eq.{int(local_id)}",
    })
    request = urllib.request.Request(
        f"{url}/rest/v1/aura_conversations?{query}",
        headers={
            "apikey": key,
            "authorization": f"Bearer {key}",
            "prefer": "return=minimal",
        },
        method="DELETE",
    )
    try:
        with urllib.request.urlopen(request, timeout=8):
            return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def _enqueue(record_type: str, local_id: int, device_id: str) -> None:
    if record_type not in {"conversation", "sensor_event"} or local_id <= 0:
        return
    try:
        conn = _open_outbox()
        if conn is None:
            return
        try:
            source = "conversation_logs" if record_type == "conversation" else "device_events"
            exists = conn.execute(f"SELECT 1 FROM {source} WHERE id=?", (local_id,)).fetchone()
            if exists:
                conn.execute(
                    f"""INSERT INTO {OUTBOX_TABLE}(record_type, local_id, device_id)
                        VALUES (?, ?, ?)
                        ON CONFLICT(record_type, local_id, device_id) DO NOTHING""",
                    (record_type, local_id, device_id),
                )
                conn.commit()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        # Local conversation and sensor writes remain successful if queueing fails.
        print("AURA_CLOUD_SYNC_QUEUE_FAILED: pending sync was not recorded")


def _load_record(conn: sqlite3.Connection, record_type: str, local_id: int) -> tuple[str, str, dict[str, Any]] | None:
    if record_type == "conversation":
        row = conn.execute(
            "SELECT id, role, message, created_at FROM conversation_logs WHERE id=?",
            (local_id,),
        ).fetchone()
        if not row or row["role"] not in {"user", "assistant"}:
            return None
        message = row["message"]
        if not isinstance(message, str) or not 1 <= len(message) <= 8000:
            return None
        return "aura_conversations", "device_id,local_id", {
            "local_id": int(row["id"]),
            "role": row["role"],
            "message": message,
            "created_at": row["created_at"],
        }

    if record_type == "sensor_event":
        row = conn.execute(
            """SELECT id, event_type, event_summary, source, room, severity,
                      confidence, created_at FROM device_events WHERE id=?""",
            (local_id,),
        ).fetchone()
        if not row or not isinstance(row["event_type"], str) or not isinstance(row["event_summary"], str):
            return None
        return "aura_sensor_events", "device_id,local_id", {
            "local_id": int(row["id"]),
            "event_type": row["event_type"][:100],
            "event_summary": row["event_summary"][:1000],
            "source": str(row["source"] or "unknown")[:100],
            "room": str(row["room"] or "")[:100] or None,
            "severity": str(row["severity"] or "low")[:30],
            "confidence": float(row["confidence"] if row["confidence"] is not None else 0.5),
            "created_at": str(row["created_at"] or "") or None,
        }
    return None


def _read_local_record(record_type: str, local_id: int) -> tuple[str, str, dict[str, Any]] | None:
    conn = _open_outbox()
    if conn is None:
        return None
    try:
        return _load_record(conn, record_type, local_id)
    except (sqlite3.Error, OSError, ValueError, TypeError):
        return None
    finally:
        conn.close()


def _queue_retry(record_type: str, local_id: int, device_id: str) -> None:
    _enqueue(record_type, local_id, device_id)


def flush_pending(limit: int = 25, now: float | None = None) -> int:
    """Retry due records; missing local records are discarded without upload."""
    if not _configuration() or not _flush_lock.acquire(blocking=False):
        return 0
    try:
        conn = _open_outbox()
        if conn is None:
            return 0
        try:
            current_time = time.time() if now is None else now
            pending = conn.execute(
                f"""SELECT id, record_type, local_id, device_id, attempts
                    FROM {OUTBOX_TABLE} WHERE next_attempt_at<=?
                    ORDER BY id LIMIT ?""",
                (current_time, max(1, min(int(limit), 100))),
            ).fetchall()
            completed = 0
            for item in pending:
                if item["record_type"] == "conversation_delete":
                    if _delete_remote_conversation(int(item["local_id"]), item["device_id"]):
                        conn.execute(f"DELETE FROM {OUTBOX_TABLE} WHERE id=?", (item["id"],))
                        completed += 1
                    else:
                        attempts = int(item["attempts"]) + 1
                        delay = min(60 * (2 ** min(attempts - 1, 9)), 21600)
                        conn.execute(
                            f"""UPDATE {OUTBOX_TABLE}
                                SET attempts=?, next_attempt_at=? WHERE id=?""",
                            (attempts, current_time + delay, item["id"]),
                        )
                    # Release SQLite's write lock before the next network call.
                    conn.commit()
                    continue
                record = _load_record(conn, item["record_type"], int(item["local_id"]))
                if record is None:
                    conn.execute(f"DELETE FROM {OUTBOX_TABLE} WHERE id=?", (item["id"],))
                    conn.commit()
                    continue
                table, conflict, payload = record
                if _upsert(table, conflict, payload, device_id=item["device_id"]):
                    conn.execute(f"DELETE FROM {OUTBOX_TABLE} WHERE id=?", (item["id"],))
                    completed += 1
                else:
                    attempts = int(item["attempts"]) + 1
                    delay = min(60 * (2 ** min(attempts - 1, 9)), 21600)
                    conn.execute(
                        f"""UPDATE {OUTBOX_TABLE}
                            SET attempts=?, next_attempt_at=? WHERE id=?""",
                        (attempts, current_time + delay, item["id"]),
                    )
                # Network I/O for later rows must not hold a local write lock.
                conn.commit()
            return completed
        finally:
            conn.close()
    finally:
        _flush_lock.release()


def _retry_loop(interval_seconds: int) -> None:
    while True:
        try:
            flush_pending()
        except Exception:
            print("AURA_CLOUD_SYNC_RETRY_FAILED: retry worker could not process pending records")
        time.sleep(interval_seconds)


def start_retry_worker(interval_seconds: int = 60) -> None:
    """Start one background retry worker per process; safe when sync is disabled."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True
    thread = threading.Thread(
        target=_retry_loop,
        args=(max(10, int(interval_seconds)),),
        name="aura-cloud-sync-retry",
        daemon=True,
    )
    thread.start()


def discard_pending_conversations(local_ids: list[int]) -> None:
    """Drop queued message references after their local conversation was erased."""
    identifiers = sorted({int(value) for value in local_ids if int(value) > 0})
    if not identifiers:
        return
    try:
        conn = _open_outbox()
        if conn is None:
            return
        try:
            conn.executemany(
                f"DELETE FROM {OUTBOX_TABLE} WHERE record_type='conversation' AND local_id=?",
                ((value,) for value in identifiers),
            )
            conn.commit()
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError, TypeError):
        print("AURA_CLOUD_SYNC_QUEUE_CLEANUP_FAILED: erased conversation may remain queued")


def enqueue_conversation_deletions(local_ids: list[int]) -> None:
    """Queue remote deletion IDs after local history is cleared; no text is retained."""
    device_id = os.environ.get("AURA_CLOUD_DEVICE_ID", "").strip()
    if not device_id or len(device_id) > 100:
        return
    try:
        identifiers = sorted({int(value) for value in local_ids if int(value) > 0})
        if not identifiers:
            return
        conn = _open_outbox()
        if conn is None:
            return
        try:
            conn.executemany(
                f"""INSERT INTO {OUTBOX_TABLE}(record_type, local_id, device_id)
                    VALUES ('conversation_delete', ?, ?)
                    ON CONFLICT(record_type, local_id, device_id) DO NOTHING""",
                ((value, device_id) for value in identifiers),
            )
            conn.commit()
        finally:
            conn.close()
    except (sqlite3.Error, OSError, ValueError, TypeError):
        print("AURA_CLOUD_SYNC_QUEUE_CLEANUP_FAILED: remote deletion was not recorded")


def sync_conversation(local_id: int, role: str, message: str, created_at: str) -> bool:
    if role not in {"user", "assistant"} or not 1 <= len(message) <= 8000:
        return False
    config = _configuration()
    if not config:
        return False
    # Re-read the source row at send time. A conversation cleared before this
    # background task runs is not uploaded after the user's deletion.
    record = _read_local_record("conversation", int(local_id))
    if record is None:
        return False
    table, conflict, payload = record
    success = _upsert(table, conflict, payload)
    if not success:
        _queue_retry("conversation", int(local_id), config[2])
    return success


def sync_sensor_event(event: dict[str, Any]) -> bool:
    event_id = event.get("event_id")
    event_type = event.get("event_type")
    summary = event.get("event_summary")
    if not isinstance(event_id, int) or not isinstance(event_type, str) or not isinstance(summary, str):
        return False
    config = _configuration()
    if not config:
        return False
    record = _read_local_record("sensor_event", event_id)
    if record is None:
        return False
    table, conflict, payload = record
    success = _upsert(table, conflict, payload)
    if not success:
        _queue_retry("sensor_event", event_id, config[2])
    return success
