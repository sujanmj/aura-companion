Warning: truncated output (original token count: 18783)
Total output lines: 1971

from __future__ import annotations

import json
import hashlib
import secrets
import sqlite3
from pathlib import Path
from typing import Any
from datetime import datetime, time, timedelta, timezone
import re


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "aura_memory.db"
SCHEMA_PATH = PROJECT_ROOT / "memory" / "schema.sql"


class AuraMemoryStore:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON;")

    def apply_schema(self) -> None:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        self.conn.executescript(schema)
        device_event_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(device_events)").fetchall()
        }
        if "external_event_id" not in device_event_columns:
            self.conn.execute("ALTER TABLE device_events ADD COLUMN external_event_id TEXT")
        reminder_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(routine_reminders)").fetchall()
        }
        if "days_of_week" not in reminder_columns:
            self.conn.execute(
                "ALTER TABLE routine_reminders ADD COLUMN days_of_week TEXT NOT NULL DEFAULT '1,2,3,4,5,6,7'"
            )
            reminder_columns.add("days_of_week")
        if "acknowledged_on" not in reminder_columns:
            self.conn.execute("ALTER TABLE routine_reminders ADD COLUMN acknowledged_on TEXT")
        self.conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS idx_device_events_external_id
               ON device_events(user_id, source, external_event_id)"""
        )
        self.conn.commit()

    def create_user(
        self,
        name: str,
        preferred_name: str | None = None,
        comfort_style: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO users (name, preferred_name, comfort_style)
            VALUES (?, ?, COALESCE(?, 'warm, loyal, motivational, not fake'))
            """,
            (name, preferred_name, comfort_style),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_or_create_user(self, name: str, preferred_name: str | None = None) -> int:
        cur = self.conn.execute(
            "SELECT id FROM users WHERE name = ? ORDER BY id LIMIT 1",
            (name,),
        )
        row = cur.fetchone()
        if row:
            return int(row["id"])

        return self.create_user(name=name, preferred_name=preferred_name)

    def enroll_sensor_node(
        self,
        user_id: int,
        node_id: str,
        display_name: str,
        room: str,
    ) -> tuple[dict[str, Any], str]:
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        self.conn.execute(
            """INSERT INTO sensor_nodes (user_id, node_id, display_name, room, token_hash)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id, node_id) DO UPDATE SET
                   display_name=excluded.display_name,
                   room=excluded.room,
                   token_hash=excluded.token_hash,
                   last_seen_at=NULL,
                   disabled=0""",
            (user_id, node_id, display_name, room, token_hash),
        )
        self.conn.execute(
            "DELETE FROM room_sessions WHERE user_id=? AND node_id=?", (user_id, node_id)
        )
        self.conn.commit()
        node = self.conn.execute(
            """SELECT id, node_id, display_name, room, created_at, last_seen_at, disabled
               FROM sensor_nodes WHERE user_id = ? AND node_id = ?""",
            (user_id, node_id),
        ).fetchone()
        return dict(node), token

    def get_sensor_node_by_token(self, token: str) -> dict[str, Any] | None:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row = self.conn.execute(
            """SELECT id, user_id, node_id, display_name, room, created_at, last_seen_at
               FROM sensor_nodes WHERE token_hash = ? AND disabled = 0""",
            (token_hash,),
        ).fetchone()
        return dict(row) if row else None

    def touch_sensor_node(self, user_id: int, node_id: str) -> bool:
        cur = self.conn.execute(
            """UPDATE sensor_nodes SET last_seen_at=CURRENT_TIMESTAMP
               WHERE user_id = ? AND node_id = ? AND disabled = 0""",
            (user_id, node_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def list_sensor_nodes(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT id, node_id, display_name, room, created_at,
                      CASE WHEN last_seen_at IS NULL THEN NULL
                           WHEN datetime(last_seen_at) IS NULL
                             OR datetime(last_seen_at) > datetime('now')
                           THEN 'Unavailable'
                           ELSE last_seen_at END AS last_seen_at,
                      CASE WHEN datetime(last_seen_at) >= datetime('now', '-90 seconds')
                                AND datetime(last_seen_at) <= datetime('now')
                           THEN 1 ELSE 0 END AS online
               FROM sensor_nodes WHERE user_id = ? AND disabled = 0
               ORDER BY node_id""",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def revoke_sensor_node(self, user_id: int, node_id: str) -> bool:
        cur = self.conn.execute(
            "UPDATE sensor_nodes SET disabled=1 WHERE user_id = ? AND node_id = ?",
            (user_id, node_id),
        )
        self.conn.execute(
            "DELETE FROM room_sessions WHERE user_id=? AND node_id=?", (user_id, node_id)
        )
        self.conn.commit()
        return cur.rowcount == 1

    def export_user_memory(self, user_id: int) -> dict[str, Any]:
        user = self.conn.execute(
            "SELECT id, name, preferred_name, comfort_style, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise ValueError("User not found")

        self.expire_observations(user_id)
        self.expire_person_memory_notes(user_id)
        self.expire_conversations(user_id)
        self.conn.execute("DELETE FROM room_sessions WHERE expires_at <= strftime('%s', 'now')")
        self.conn.commit()
        tables = (
            "room_sessions",
            "room_reply_claims",
            "companion_preferences",
            "observation_retention",
            "conversation_retention",
            "person_memory_retention",
            "conversation_logs",
            "memory_facts",
            "forgotten_memory_facts",
            "observations",
            "mood_logs",
            "routine_memory",
            "forgotten_memory_routines",
            "routine_reminders",
            "safety_events",
            "emergency_contacts",
            "response_feedback",
            "device_events",
            "action_logs",
            "known_people",
            "person_events",
            "escalation_plans",
            "escalation_logs",
            "confirmation_requests",
            "incidents",
            "service_heartbeats",
        )
        records: dict[str, list[dict[str, Any]]] = {}
        for table in tables:
            records[table] = [
                dict(row)
                for row in self.conn.execute(
                    f"SELECT * FROM {table} WHERE user_id = ? ORDER BY rowid",
                    (user_id,),
                ).fetchall()
            ]
        records["incident_timeline_items"] = [
            dict(row)
            for row in self.conn.execute(
                """SELECT item.* FROM incident_timeline_items AS item
                   JOIN incidents ON incidents.id = item.incident_id
                   WHERE incidents.user_id = ? ORDER BY item.rowid""",
                (user_id,),
            ).fetchall()
        ]
        return {
            "format": "aura-memory-export",
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "user": dict(user),
            "records": records,
        }

    def get_companion_preferences(self, user_id: int) -> dict[str, Any]:
        self.conn.execute(
            "INSERT OR IGNORE INTO companion_preferences (user_id) VALUES (?)",
            (user_id,),
        )
        self.conn.commit()
        row = self.conn.execute(
            """SELECT checkins_enabled, quiet_start, quiet_end,
                      checkin_interval_hours, last_checkin_at
               FROM companion_preferences WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        result = dict(row)
        result["checkins_enabled"] = bool(result["checkins_enabled"])
        return result

    def update_companion_preferences(
        self,
        user_id: int,
        checkins_enabled: bool,
        quiet_start: str,
        quiet_end: str,
        checkin_interval_hours: int,
    ) -> dict[str, Any]:
        if not isinstance(checkins_enabled, bool):
            raise ValueError("checkins_enabled must be a boolean")
        if not isinstance(quiet_start, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", quiet_start):
            raise ValueError("Invalid quiet start time")
        if not isinstance(quiet_end, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", quiet_end):
            raise ValueError("Invalid quiet end time")
        if (
            not isinstance(checkin_interval_hours, int)
            or isinstance(checkin_interval_hours, bool)
            or not 4 <= checkin_interval_hours <= 168
        ):
            raise ValueError("Check-in interval must be between 4 and 168 hours")
        self.conn.execute(
            "INSERT OR IGNORE INTO companion_preferences (user_id) VALUES (?)",
            (user_id,),
        )
        self.conn.execute(
            """UPDATE companion_preferences
               SET checkins_enabled = ?, quiet_start = ?, quiet_end = ?,
                   checkin_interval_hours = ?
               WHERE user_id = ?""",
            (int(checkins_enabled), quiet_start, quiet_end, checkin_interval_hours, user_id),
        )
        self.conn.commit()
        return self.get_companion_preferences(user_id)

    def get_routine_reminders(self, user_id: int) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT id, label, local_time, days_of_week, enabled, last_delivered_on,
                      dismissed_on, acknowledged_on, created_at
               FROM routine_reminders WHERE user_id=? ORDER BY local_time, id""",
            (user_id,),
        ).fetchall()
        reminders = [dict(row) for row in rows]
        for reminder in reminders:
            reminder["enabled"] = bool(reminder["enabled"])
        return reminders

    def add_routine_reminder(
        self, user_id: int, label: str, local_time: str,
        days_of_week: list[int] | None = None,
    ) -> int:
        label = label.strip() if isinstance(label, str) else ""
        if not 1 <= len(label) <= 120:
            raise ValueError("Reminder label must contain 1–120 characters")
        try:
            parsed_time = time.fromisoformat(local_time)
        except (TypeError, ValueError):
            raise ValueError("Reminder time must use HH:MM") from None
        if parsed_time.second or parsed_time.microsecond or parsed_time.tzinfo:
            raise ValueError("Reminder time must use HH:MM")
        days = list(range(1, 8)) if days_of_week is None else days_of_week
        if (
            not isinstance(days, list)
            or not days
            or any(type(day) is not int or day < 1 or day > 7 for day in days)
            or len(set(days)) != len(days)
        ):
            raise ValueError("Reminder days must be a non-empty list of unique weekdays")
        days_text = ",".join(str(day) for day in sorted(days))
        count = self.conn.execute(
            "SELECT COUNT(*) FROM routine_reminders WHERE user_id=? AND enabled=1",
            (user_id,),
        ).fetchone()[0]
        if count >= 20:
            raise ValueError("A maximum of 20 active reminders is allowed")
        cur = self.conn.execute(
            """INSERT INTO routine_reminders
               (user_id, label, local_time, days_of_week, enabled)
               VALUES (?, ?, ?, ?, 1)""",
            (user_id, label, parsed_time.strftime("%H:%M"), days_text),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_routine_reminder(
        self, user_id: int, reminder_id: int, label: str, local_time: str,
        days_of_week: list[int],
    ) -> bool:
        label = label.strip() if isinstance(label, str) else ""
        if not 1 <= len(label) <= 120:
            raise ValueError("Reminder label must contain 1–120 characters")
        try:
            parsed_time = time.fromisoformat(local_time)
        except (TypeError, ValueError):
            raise ValueError("Reminder time must use HH:MM") from None
        if parsed_time.second or parsed_time.microsecond or parsed_time.tzinfo:
            raise ValueError("Reminder time must use HH:MM")
        if (
            not isinstance(days_of_week, list)
            or not days_of_week
            or any(type(day) is not int or day < 1 or day > 7 for day in days_of_week)
            or len(set(days_of_week)) != len(days_of_week)
        ):
            raise ValueError("Reminder days must be a non-empty list of unique weekdays")
        days_text = ",".join(str(day) for day in sorted(days_of_week))
        cur = self.conn.execute(
            """UPDATE routine_reminders SET label=?, local_time=?, days_of_week=?
               WHERE id=? AND user_id=?""",
            (label, parsed_time.strftime("%H:%M"), days_text, reminder_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def delete_routine_reminder(self, user_id: int, reminder_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM routine_reminders WHERE id=? AND user_id=?",
            (reminder_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def set_routine_reminder_enabled(
        self, user_id: int, reminder_id: int, enabled: bool
    ) -> str | None:
        if not isinstance(enabled, bool):
            raise ValueError("Reminder enabled must be a boolean")
        row = self.conn.execute(
            "SELECT enabled FROM routine_reminders WHERE id=? AND user_id=?",
            (reminder_id, user_id),
        ).fetchone()
        if not row:
            return "not_found"
        if enabled and not bool(row["enabled"]):
            count = self.conn.execute(
                "SELECT COUNT(*) FROM routine_reminders WHERE user_id=? AND enabled=1",
                (user_id,),
            ).fetchone()[0]
            if count >= 20:
                return "limit"
        self.conn.execute(
            "UPDATE routine_reminders SET enabled=? WHERE id=? AND user_id=?",
            (int(enabled), reminder_id, user_id),
        )
        self.conn.commit()
        return None

    def dismiss_routine_reminder(
        self,
        user_id: int,
        reminder_id: int,
        now: datetime | None = None,
    ) -> bool:
        now = now or datetime.now().astimezone()
        if now.tzinfo is None:
            raise ValueError("Dismissal time must include a timezone")
        today = now.date().isoformat()
        cur = self.conn.execute(
            """UPDATE routine_reminders SET dismissed_on=?
               WHERE id=? AND user_id=? AND enabled=1 AND last_delivered_on=?
                 AND (acknowledged_on IS NULL OR acknowledged_on<>?)""",
            (today, reminder_id, user_id, today, today),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def acknowledge_routine_reminder(
        self,
        user_id: int,
        reminder_id: int,
        now: datetime | None = None,
    ) -> bool:
        """Record that the owner saw today's delivered reminder, not its completion."""
        now = now or datetime.now().astimezone()
        if now.tzinfo is None:
            raise ValueError("Acknowledgement time must include a timezone")
        today = now.date().isoformat()
        cur = self.conn.execute(
            """UPDATE routine_reminders SET acknowledged_on=?
               WHERE id=? AND user_id=? AND last_delivered_on=?
                 AND (dismissed_on IS NULL OR dismissed_on<>?)
                 AND (acknowledged_on IS NULL OR acknowledged_on<>?)""",
            (today, reminder_id, user_id, today, today, today),
        )
        changed = cur.rowcount == 1
        if not changed:
            row = self.conn.execute(
                """SELECT 1 FROM routine_reminders WHERE id=? AND user_id=?
                     AND last_delivered_on=? AND acknowledged_on=?
                     AND (dismissed_on IS NULL OR dismissed_on<>?)""",
                (reminder_id, user_id, today, today, today),
            ).fetchone()
            changed = row is not None
        self.conn.commit()
        return changed

    def create_due_routine_reminder(
        self, user_id: int, now: datetime | None = None
    ) -> dict[str, Any] | None:
        """Deliver one user-entered local reminder at most once on each local date."""
        now = now or datetime.now().astimezone()
        if now.tzinfo is None:
            raise ValueError("Reminder time must include a timezone")
        local_now = now
        today = local_now.date().isoformat()
        rows = self.conn.execute(
            """SELECT id, label FROM routine_reminders
               WHERE user_id=? AND enabled=1 AND local_time<=?
                 AND instr(',' || days_of_week || ',', ',' || ? || ',') > 0
                 AND (last_delivered_on IS NULL OR last_delivered_on<>?)
                 AND (dismissed_on IS NULL OR dismissed_on<>?)
               ORDER BY local_time, id""",
            (user_id, local_now.strftime("%H:%M"), str(local_now.isoweekday()), today, today),
        ).fetchall()
        if not rows:
            return None
        reminder = rows[0]
        profile = self.conn.execute(
            "SELECT preferred_name FROM users WHERE id=?", (user_id,)
        ).fetchone()
        name = (profile["preferred_name"] or "").strip() if profile else ""
        greeting = f"{name}, " if name else ""
        response = (
            f"{greeting}a reminder you set: {reminder['label']}. "
            "I can’t tell whether you’ve done it. In Memory, acknowledge it to record that you saw it, "
            "or dismiss it for today; neither action confirms completion or a dose."
        )
        with self.conn:
            claimed = self.conn.execute(
                """UPDATE routine_reminders SET last_delivered_on=?, dismissed_on=NULL,
                       acknowledged_on=NULL
                   WHERE id=? AND user_id=? AND enabled=1
                     AND (last_delivered_on IS NULL OR last_delivered_on<>?)
                     AND instr(',' || days_of_week || ',', ',' || ? || ',') > 0
                     AND (dismissed_on IS NULL OR dismissed_on<>?)""",
                (today, reminder["id"], user_id, today, str(local_now.isoweekday()), today),
            )
            if claimed.rowcount != 1:
                return None
            message_id = self.conn.execute(
                """INSERT INTO conversation_logs (user_id, role, message, emotion_tag)
                   VALUES (?, 'assistant', ?, 'routine_reminder')""",
                (user_id, response),
            ).lastrowid
        return {
            "id": int(message_id),
            "reminder_id": int(reminder["id"]),
            "response": response,
            "provider": "local",
            "reminder": True,
        }

    def create_checkin_if_due(
        self, user_id: int, now: datetime | None = None
    ) -> dict[str, Any] | None:
        now = now or datetime.now().astimezone()
        if now.tzinfo is None:
            raise ValueError("Check-in time must include a timezone")
        preferences = self.get_companion_preferences(user_id)
        if not preferences["checkins_enabled"]:
            return None

        current = now.timetz().replace(tzinfo=None)
        quiet_start = time.fromisoformat(preferences["quiet_start"])
        quiet_end = time.fromisoformat(preferences["quiet_end"])
        if quiet_start != quiet_end:
            is_quiet = (
                quiet_start <= current < quiet_end
                if quiet_start < quiet_end
                else current >= quiet_start or current < quiet_end
            )
            if is_quiet:
                return None

        last_user = self.conn.execute(
            """SELECT created_at FROM conversation_logs
               WHERE user_id = ? AND role = 'user' ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        if not last_user:
            return None
        last_activity = datetime.fromisoformat(last_user["created_at"]).replace(
            tzinfo=timezone.utc
        )
        if preferences["last_checkin_at"]:
            last_checkin = datetime.fromisoformat(preferences["last_checkin_at"])
            if last_checkin.tzinfo is None:
                last_checkin = last_checkin.replace(tzinfo=timezone.utc)
            last_activity = max(last_activity, last_checkin.astimezone(timezone.utc))
        interval = preferences["checkin_interval_hours"]
        if now.astimezone(timezone.utc) - last_activity < timedelta(hours=interval):
            return None

        profile = self.conn.execute(
            "SELECT name, preferred_name FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        name = (profile["preferred_name"] or "").strip()
        greeting = f"{name}, just checking in. How are you doing today? No need to reply unless you feel like it." if name else "Just checking in. How are you doing today? No need to reply unless you feel like it."
        now_utc = now.astimezone(timezone.utc).isoformat()
        with self.conn:
            cur = self.conn.execute(
                """INSERT INTO conversation_logs (user_id, role, message, emotion_tag)
                   VALUES (?, 'assistant', ?, 'check_in')""",
                (user_id, greeting),
            )
            self.conn.execute(
                "UPDATE companion_preferences SET last_checkin_at = ? WHERE user_id = ?",
                (now_utc, user_id),
            )
        return {"id": int(cur.lastrowid), "response": greeting, "provider": "local", "check_in": True}

    def add_conversation(
        self,
        user_id: int,
        role: str,
        message: str,
        emotion_tag: str | None = None,
    ) -> int:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("role must be one of: user, assistant, system")

        cur = self.conn.execute(
            """
            INSERT INTO conversation_logs (user_id, role, message, emotion_tag)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, role, message, emotion_tag),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def clear_conversation_history(self, user_id: int) -> int:
        cur = self.conn.execute(
            "DELETE FROM conversation_logs WHERE user_id = ?",
            (user_id,),
        )
        self.conn.commit()
        return cur.rowcount

    def remember_fact(
        self,
        user_id: int,
        fact_key: str,
        fact_value: str,
        confidence: float = 0.7,
        source: str = "conversation",
    ) -> None:
        suppressed = self.conn.execute(
            "SELECT 1 FROM forgotten_memory_facts WHERE user_id=? AND fact_key=?",
            (user_id, fact_key),
        ).fetchone()
        if suppressed and source == "conversation":
            return
        if source != "conversation":
            self.conn.execute(
                "DELETE FROM forgotten_memory_facts WHERE user_id=? AND fact_key=?",
                (user_id, fact_key),
            )
        self.conn.execute(
            """
            INSERT INTO memory_facts (user_id, fact_key, fact_value, confidence, source)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, fact_key)
            DO UPDATE SET
                fact_value = excluded.fact_value,
                confidence = excluded.confidence,
                source = excluded.source,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (user_id, fact_key, fact_value, confidence, source),
        )
        self.conn.commit()

    def add_observation(
        self,
        user_id: int,
        event_type: str,
        event_summary: str,
        confidence: float = 0.5,
        source: str = "system",
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO observations (user_id, event_type, event_summary, confidence, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, event_type, event_summary, confidence, source),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_ambient_scene_observation(
        self,
        user_id: int,
        labels: list[str],
        human_present: bool,
        confidence: float,
    ) -> dict[str, Any]:
        """Save a rate-limited, derived scene summary; never save camera frames."""
        if (
            not isinstance(labels, list)
            or len(labels) > 4
            or any(
                not isinstance(label, str)
                or not label.strip()
                or len(label.strip()) > 64
                or not re.fullmatch(r"[A-Za-z0-9 _-]+", label.strip())
                for label in labels
            )
        ):
            raise ValueError("Invalid scene labels")
        if not isinstance(human_present, bool):
            raise ValueError("Invalid person-presence signal")
        if (
            not isinstance(confidence, (int, float))
            or isinstance(confidence, bool)
            or not 0.0 <= confidence <= 1.0
        ):
            raise ValueError("Invalid scene confidence")
        self.expire_observations(user_id)
        clean_labels = [label.strip() for label in labels]
        if not clean_labels and not human_present:
            return {"saved": False, "reason": "no_scene_signal"}

        latest = self.conn.execute(
            """SELECT event_summary FROM observations
               WHERE user_id=? AND source='mac_local_vision'
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()
        summary = (
            "On-device scene estimate: "
            + (", ".join(clean_labels) if clean_labels else "no clear objects")
            + f". Human-shaped figure detected: {'yes' if human_present else 'no'}."
        )
        if latest and latest["event_summary"] == summary:
            return {"saved": False, "reason": "unchanged"}
        recent = self.conn.execute(
            """SELECT 1 FROM observations
               WHERE user_id=? AND source='mac_local_vision'
                 AND created_at >= datetime('now', '-60 seconds')
               LIMIT 1""",
            (user_id,),
        ).fetchone()
        if recent:
            return {"saved": False, "reason": "rate_limited"}
        observation_id = self.add_observation(
            user_id,
            event_type="ambient_visual_context",
            event_summary=summary,
            confidence=float(confidence),
            source="mac_local_vision",
        )
        return {"saved": True, "observation_id": observation_id}

    def add_mood_log(
        self,
        user_id: int,
        detected_mood: str,
        mood_reason: str,
        confidence: float = 0.5,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO mood_logs (user_id, detected_mood, mood_reason, confidence)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, detected_mood, mood_reason, confidence),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def remember_routine(
        self,
        user_id: int,
        routine_key: str,
        routine_value: str,
        confidence: float = 0.5,
        source: str = "conversation",
    ) -> None:
        suppressed = self.conn.execute(
            "SELECT 1 FROM forgotten_memory_routines WHERE user_id=? AND routine_key=?",
            (user_id, routine_key),
        ).fetchone()
        if suppressed and source == "conversation":
            return
        if source != "conversation":
            self.conn.execute(
                "DELETE FROM forgotten_memory_routines WHERE user_id=? AND routine_key=?",
                (user_id, routine_key),
            )
        self.conn.execute(
            """
            INSERT INTO routine_memory (user_id, routine_key, routine_value, confidence)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, routine_key)
            DO UPDATE SET
                routine_value = excluded.routine_value,
                confidence = excluded.confidence,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (user_id, routine_key, routine_value, confidence),
        )
        self.conn.commit()

    def get_recent_conversations(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        self.expire_conversations(user_id)
        cur = self.conn.execute(
            """
            SELECT role, message, emotion_tag, created_at
            FROM conversation_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def conversation_retention(self, user_id: int) -> dict[str, int]:
        row = self.conn.execute(
            "SELECT days FROM conversation_retention WHERE user_id=?", (user_id,)
        ).fetchone()
        return {"days": row["days"] if row else 0}

    def get_expired_conversation_ids(self, user_id: int, days: int | None = None) -> list[int]:
        effective_days = self.conversation_retention(user_id)["days"] if days is None else days
        if type(effective_days) is not int or effective_days not in (0, 1, 7, 30, 90, 365):
            raise ValueError("Invalid conversation retention")
        if not effective_days:
            return []
        rows = self.conn.execute(
            """SELECT id FROM conversation_logs
               WHERE user_id=? AND julianday(created_at) < julianday('now', ?)
               ORDER BY id""",
            (user_id, f"-{effective_days} days"),
        ).fetchall()
        return [int(row["id"]) for row in rows]

    def preview_conversation_expiry(self, user_id: int, days: int) -> dict[str, int]:
        if type(days) is not int or days not in (0, 1, 7, 30, 90, 365):
            raise ValueError("Invalid conversation retention")
        return {"days": days, "expiring": len(self.get_expired_conversation_ids(user_id, days))}

    def expire_conversations(
        self, user_id: int, *, days: int | None = None, commit: bool = True
    ) -> int:
        expired_ids = self.get_expired_conversation_ids(user_id, days)
        if not expired_ids:
            return 0
        placeholders = ",".join("?" for _ in expired_ids)
        cur = self.conn.execute(
            f"DELETE FROM conversation_logs WHERE user_id=? AND id IN ({placeholders})",
            (user_id, *expired_ids),
        )
        if commit:
            self.conn.commit()
        return cur.rowcount

    def set_conversation_retention(self, user_id: int, days: int) -> dict[str, int]:
        self.preview_conversation_expiry(user_id, days)
        with self.conn:
            self.conn.execute(
                "INSERT INTO conversation_retention(user_id, days) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET days=excluded.days", (user_id, days)
            )
            deleted = self.expire_conversations(user_id, days=days, commit=False)
        return {"days": days, "deleted": deleted}

    def update_memory_routine(self, user_id: int, routine_id: int, routine_value: str) -> bool:
        value = routine_value.strip()
        if not value or len(value) > 2000:
            raise ValueError("routine value must contain 1–2000 characters")
        cur = self.conn.execute(
            """UPDATE routine_memory SET routine_value=?, confidence=1.0,
               last_seen_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=?""",
            (value, routine_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def delete_memory_routine(self, user_id: int, routine_id: int) -> bool:
        row = self.conn.execute(
            "SELECT routine_key FROM routine_memory WHERE id=? AND user_id=?",
            (routine_id, user_id),
        ).fetchone()
        if not row:
            return False
        with self.conn:
            self.conn.execute(
                """INSERT INTO forgotten_memory_routines (user_id, routine_key)
                   VALUES (?, ?) ON CONFLICT(user_id, routine_key)
                   DO UPDATE SET forgotten_at=CURRENT_TIMESTAMP""",
                (user_id, row["routine_key"]),
            )
            self.conn.execute(
                "DELETE FROM routine_memory WHERE id=? AND user_id=?",
                (routine_id, user_id),
            )
        return True

    def get_memory_facts(self, user_id: int) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, fact_key, fact_value, confidence, source, last_seen_at
            FROM memory_facts
            WHERE user_id = ?
            ORDER BY last_seen_at DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def update_memory_fact(self, user_id: int, fact_id: int, fact_value: str) -> bool:
        value = fact_value.strip()
        if not value or len(value) > 2000:
            raise ValueError("fact value must contain 1–2000 characters")
        cur = self.conn.execute(
            """UPDATE memory_facts
               SET fact_value=?, source='user_correction', last_seen_at=CURRENT_TIMESTAMP
               WHERE id=? AND user_id=?""",
            (value, fact_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def delete_memory_fact(self, user_id: int, fact_id: int) -> bool:
        row = self.conn.execute(
            "SELECT fact_key FROM memory_facts WHERE id=? AND user_id=?",
            (fact_id, user_id),
        ).fetchone()
        if not row:
            return False
        with self.conn:
            self.conn.execute(
                "INSERT INTO forgotten_memory_facts (user_id, fact_key) VALUES (?, ?) "
                "ON CONFLICT(user_id, fact_key) DO UPDATE SET forgotten_at=CURRENT_TIMESTAMP",
                (user_id, row["fact_key"]),
            )
            self.conn.execute(
                "DELETE FROM memory_facts WHERE id=? AND user_id=?", (fact_id, user_id)
            )
        return True

    def observation_retention(self, user_id: int) -> dict[str, int]:
        row = self.conn.execute(
            "SELECT days FROM observation_retention WHERE user_id=?", (user_id,)
        ).fetchone()
        return {"days": row["days"] if row else 0}

    def preview_observation_expiry(self, user_id: int, days: int) -> dict[str, int]:
        if type(days) is not int or days not in (0, 1, 7, 30, 90, 365):
            raise ValueError("Invalid observation retention")
        co…783 tokens truncated…onn.commit()
        return cur.rowcount

    def get_latest_observations(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        self.expire_observations(user_id)
        cur = self.conn.execute(
            """
            SELECT id, event_type, event_summary, confidence, source, created_at
            FROM observations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def delete_observation(self, user_id: int, observation_id: int) -> bool:
        cur = self.conn.execute(
            "DELETE FROM observations WHERE id=? AND user_id=?",
            (observation_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def clear_observations(self, user_id: int) -> int:
        """Forget all saved observation notes for one user, preserving other memory."""
        cur = self.conn.execute(
            "DELETE FROM observations WHERE user_id=?", (user_id,)
        )
        self.conn.commit()
        return cur.rowcount

    def correct_observation(self, user_id: int, observation_id: int, value: str) -> bool:
        """Replace a saved observation with an explicit, user-authored correction."""
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
            raise ValueError("Observation correction must contain 1–500 characters")
        cur = self.conn.execute(
            """UPDATE observations
               SET event_type='user_corrected_observation', event_summary=?,
                   confidence=1.0, source='user_correction', created_at=CURRENT_TIMESTAMP
               WHERE id=? AND user_id=?""",
            ("User correction: " + value.strip(), observation_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get_routine_memory(self, user_id: int) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """SELECT id, routine_key, routine_value, confidence, last_seen_at, created_at
               FROM routine_memory WHERE user_id = ? ORDER BY last_seen_at DESC""",
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def add_response_feedback(
        self,
        user_id: int,
        response_text: str,
        rating: str,
        feedback_text: str | None = None,
        situation: str | None = None,
        tone: str | None = None,
    ) -> int:
        allowed_ratings = {"good", "bad", "neutral"}
        if rating not in allowed_ratings:
            raise ValueError(f"rating must be one of: {', '.join(sorted(allowed_ratings))}")

        cur = self.conn.execute(
            """
            INSERT INTO response_feedback (
                user_id, response_text, rating, feedback_text, situation, tone
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, response_text, rating, feedback_text, situation, tone),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_recent_response_feedback(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT rating, feedback_text, response_text, situation, tone, created_at
            FROM response_feedback
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def add_device_event(
        self,
        user_id: int,
        event_type: str,
        event_summary: str,
        source: str = "unknown",
        room: str | None = None,
        severity: str = "low",
        confidence: float = 0.5,
        requires_action: bool = False,
        metadata: dict | None = None,
    ) -> int:
        allowed_severities = {"low", "medium", "high", "critical"}
        if severity not in allowed_severities:
            raise ValueError(f"severity must be one of: {', '.join(sorted(allowed_severities))}")

        metadata_json = json.dumps(metadata) if metadata is not None else None
        cur = self.conn.execute(
            """
            INSERT INTO device_events (
                user_id, event_type, event_summary, source, room, severity,
                confidence, requires_action, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                event_type,
                event_summary,
                source,
                room,
                severity,
                confidence,
                int(requires_action),
                metadata_json,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_device_event_once(
        self,
        user_id: int,
        event_type: str,
        event_summary: str,
        source: str,
        external_event_id: str,
        room: str | None = None,
        severity: str = "low",
        confidence: float = 0.5,
        requires_action: bool = False,
        metadata: dict | None = None,
    ) -> tuple[int, bool]:
        allowed_severities = {"low", "medium", "high", "critical"}
        if severity not in allowed_severities:
            raise ValueError(f"severity must be one of: {', '.join(sorted(allowed_severities))}")
        event_key = external_event_id.strip()
        if not event_key or len(event_key) > 128:
            raise ValueError("external_event_id must contain 1–128 characters")

        metadata_json = json.dumps(metadata) if metadata is not None else None
        cur = self.conn.execute(
            """INSERT INTO device_events (
                   user_id, event_type, event_summary, source, room, severity,
                   confidence, requires_action, metadata_json, external_event_id
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id, source, external_event_id) DO NOTHING""",
            (
                user_id,
                event_type,
                event_summary,
                source,
                room,
                severity,
                confidence,
                int(requires_action),
                metadata_json,
                event_key,
            ),
        )
        inserted = cur.rowcount == 1
        if inserted:
            event_id = int(cur.lastrowid)
        else:
            row = self.conn.execute(
                """SELECT id FROM device_events
                   WHERE user_id = ? AND source = ? AND external_event_id = ?""",
                (user_id, source, event_key),
            ).fetchone()
            if row is None:
                raise RuntimeError("Idempotent event insert did not return an event")
            event_id = int(row["id"])
        self.conn.commit()
        return event_id, inserted

    def get_device_event(self, event_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """SELECT id, event_type, event_summary, source, room, severity,
                      confidence, requires_action, action_status, metadata_json, created_at
               FROM device_events WHERE id = ?""",
            (event_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_recent_device_events(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, event_type, event_summary, source, room, severity,
                   confidence, requires_action, action_status, metadata_json, created_at
            FROM device_events
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_device_event_row(row) for row in cur.fetchall()]

    @staticmethod
    def _parse_device_event_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        event = dict(row)
        if "requires_action" in event:
            event["requires_action"] = bool(event["requires_action"])
        metadata_json = event.pop("metadata_json", None)
        if metadata_json:
            try:
                event["metadata"] = json.loads(metadata_json)
            except json.JSONDecodeError:
                event["metadata"] = metadata_json
        return event

    def get_pending_device_events(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, event_type, event_summary, source, room, severity,
                   confidence, requires_action, action_status, metadata_json, created_at
            FROM device_events
            WHERE user_id = ? AND action_status = 'none'
            ORDER BY id ASC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_device_event_row(row) for row in cur.fetchall()]

    def update_device_event_action_status(self, event_id: int, action_status: str) -> None:
        self.conn.execute(
            """
            UPDATE device_events
            SET action_status = ?
            WHERE id = ?
            """,
            (action_status, event_id),
        )
        self.conn.commit()

    def get_device_event_by_id(self, event_id: int) -> dict[str, Any] | None:
        cur = self.conn.execute(
            """
            SELECT id, user_id, event_type, event_summary, source, room, severity,
                   confidence, requires_action, action_status, metadata_json, created_at
            FROM device_events
            WHERE id = ?
            """,
            (event_id,),
        )
        row = cur.fetchone()
        return self._parse_device_event_row(row) if row else None

    def add_action_log(
        self,
        user_id: int,
        action_type: str,
        action_summary: str,
        target: str | None = None,
        status: str = "planned",
        source_event_id: int | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO action_logs (
                user_id, action_type, action_summary, target, status, source_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, action_type, action_summary, target, status, source_event_id),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_recent_action_logs(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, action_type, action_summary, target, status, source_event_id, created_at
            FROM action_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def add_known_person(
        self,
        user_id: int,
        display_name: str,
        relation: str | None = None,
        notes: str | None = None,
        trust_level: str = "known",
        consent_to_remember: bool = False,
        face_profile_status: str = "not_enrolled",
        allowed_rooms: str | None = None,
        emergency_contact: bool = False,
    ) -> int:
        allowed_trust_levels = {
            "family", "friend", "caretaker", "known", "guest", "unknown", "blocked",
        }
        if trust_level not in allowed_trust_levels:
            raise ValueError(
                f"trust_level must be one of: {', '.join(sorted(allowed_trust_levels))}"
            )

        cur = self.conn.execute(
            """
            INSERT INTO known_people (
                user_id, display_name, relation, notes, trust_level,
                consent_to_remember, face_profile_status, allowed_rooms, emergency_contact
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                display_name,
                relation,
                notes,
                trust_level,
                int(consent_to_remember),
                face_profile_status,
                allowed_rooms,
                int(emergency_contact),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_known_people(self, user_id: int) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, display_name, relation, notes, trust_level, consent_to_remember,
                   face_profile_status, allowed_rooms, emergency_contact, created_at, last_seen_at
            FROM known_people
            WHERE user_id = ?
            ORDER BY display_name COLLATE NOCASE ASC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def forget_known_person(self, user_id: int, person_id: int) -> bool:
        """Forget one person's profile and its related timeline, scoped to its owner."""
        person = self.conn.execute(
            "SELECT id FROM known_people WHERE id=? AND user_id=?",
            (person_id, user_id),
        ).fetchone()
        if not person:
            return False
        with self.conn:
            self.conn.execute(
                "DELETE FROM person_events WHERE person_id=? AND user_id=?",
                (person_id, user_id),
            )
            self.conn.execute(
                "DELETE FROM known_people WHERE id=? AND user_id=?",
                (person_id, user_id),
            )
        return True

    def find_known_person(self, user_id: int, display_name: str) -> dict[str, Any] | None:
        cur = self.conn.execute(
            """
            SELECT id, display_name, relation, notes, trust_level, consent_to_remember,
                   face_profile_status, allowed_rooms, emergency_contact, created_at, last_seen_at
            FROM known_people
            WHERE user_id = ? AND LOWER(display_name) = LOWER(?)
            ORDER BY id LIMIT 1
            """,
            (user_id, display_name),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def update_person_last_seen(self, user_id: int, person_id: int) -> None:
        self.conn.execute(
            """
            UPDATE known_people
            SET last_seen_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND id = ?
            """,
            (user_id, person_id),
        )
        self.conn.commit()

    def add_person_event(
        self,
        user_id: int,
        person_id: int | None,
        event_type: str,
        event_summary: str,
        source: str = "manual",
        room: str | None = None,
        confidence: float = 0.5,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO person_events (
                user_id, person_id, event_type, event_summary, source, room, confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, person_id, event_type, event_summary, source, room, confidence),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_person_memory_note(
        self,
        user_id: int,
        person_id: int,
        note: str,
        consent_confirmed: bool,
    ) -> int:
        """Save an explicitly consented user note for an enrolled person."""
        if type(person_id) is not int or person_id <= 0:
            raise ValueError("Invalid person")
        if type(consent_confirmed) is not bool or not consent_confirmed:
            raise ValueError("Consent confirmation is required")
        if not isinstance(note, str) or not 1 <= len(note.strip()) <= 500:
            raise ValueError("Person memory note must contain 1–500 characters")
        person = self.conn.execute(
            "SELECT id FROM known_people WHERE id=? AND user_id=? AND consent_to_remember=1",
            (person_id, user_id),
        ).fetchone()
        if not person:
            raise ValueError("Consented person not found")
        cur = self.conn.execute(
            """INSERT INTO person_events (
                   user_id, person_id, event_type, event_summary, source, confidence
               ) VALUES (?, ?, 'user_memory_note', ?, 'user_explicit', 1.0)""",
            (user_id, person_id, note.strip()),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def delete_person_memory_note(self, user_id: int, event_id: int) -> bool:
        if type(event_id) is not int or event_id <= 0:
            return False
        cur = self.conn.execute(
            """DELETE FROM person_events
               WHERE id=? AND user_id=? AND event_type='user_memory_note'
                 AND source='user_explicit'""",
            (event_id, user_id),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def get_recent_person_events(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        self.expire_person_memory_notes(user_id)
        cur = self.conn.execute(
            """
            SELECT event.id, event.person_id, person.display_name,
                   person.consent_to_remember, event.event_type, event.event_summary,
                   event.source, event.room, event.confidence, event.created_at
            FROM person_events AS event
            LEFT JOIN known_people AS person
              ON person.id=event.person_id AND person.user_id=event.user_id
            WHERE event.user_id = ?
            ORDER BY event.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    def add_emergency_contact(
        self,
        user_id: int,
        name: str,
        phone: str | None = None,
        email: str | None = None,
        relation: str | None = None,
        priority: int = 1,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO emergency_contacts (user_id, name, phone, email, relation, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, name, phone, email, relation, priority),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_emergency_contacts(self, user_id: int) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, name, phone, email, relation, priority, created_at
            FROM emergency_contacts
            WHERE user_id = ?
            ORDER BY priority ASC, id ASC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def add_escalation_plan(
        self,
        user_id: int,
        event_type: str,
        severity: str,
        first_action: str,
        second_action: str | None = None,
        final_action: str | None = None,
        wait_seconds_before_escalation: int = 30,
        requires_user_confirmation: bool = True,
        enabled: bool = True,
    ) -> int:
        allowed_severities = {"low", "medium", "high", "critical"}
        if severity not in allowed_severities:
            raise ValueError(f"severity must be one of: {', '.join(sorted(allowed_severities))}")

        cur = self.conn.execute(
            """
            INSERT INTO escalation_plans (
                user_id, event_type, severity, first_action, second_action, final_action,
                wait_seconds_before_escalation, requires_user_confirmation, enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                event_type,
                severity,
                first_action,
                second_action,
                final_action,
                wait_seconds_before_escalation,
                int(requires_user_confirmation),
                int(enabled),
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_escalation_plan(self, user_id: int, event_type: str) -> dict[str, Any] | None:
        cur = self.conn.execute(
            """
            SELECT id, event_type, severity, first_action, second_action, final_action,
                   wait_seconds_before_escalation, requires_user_confirmation, enabled, created_at
            FROM escalation_plans
            WHERE user_id = ? AND event_type = ? AND enabled = 1
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id, event_type),
        )
        row = cur.fetchone()
        return dict(row) if row else None

    def add_escalation_log(
        self,
        user_id: int,
        event_type: str,
        escalation_stage: str,
        action_summary: str,
        severity: str = "medium",
        status: str = "planned",
        source_event_id: int | None = None,
    ) -> int:
        allowed_severities = {"low", "medium", "high", "critical"}
        if severity not in allowed_severities:
            raise ValueError(f"severity must be one of: {', '.join(sorted(allowed_severities))}")

        cur = self.conn.execute(
            """
            INSERT INTO escalation_logs (
                user_id, source_event_id, event_type, severity,
                escalation_stage, action_summary, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                source_event_id,
                event_type,
                severity,
                escalation_stage,
                action_summary,
                status,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_recent_escalation_logs(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, source_event_id, event_type, severity, escalation_stage,
                   action_summary, status, created_at
            FROM escalation_logs
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]

    @staticmethod
    def _parse_confirmation_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        metadata_json = item.pop("metadata_json", None)
        if metadata_json:
            try:
                item["metadata"] = json.loads(metadata_json)
            except json.JSONDecodeError:
                item["metadata"] = metadata_json
        else:
            item["metadata"] = None
        return item

    def add_confirmation_request(
        self,
        user_id: int,
        source_event_id: int | None,
        confirmation_type: str,
        prompt: str,
        expires_at: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        metadata_json = json.dumps(metadata) if metadata is not None else None
        cur = self.conn.execute(
            """
            INSERT INTO confirmation_requests (
                user_id, source_event_id, confirmation_type, prompt,
                status, expires_at, metadata_json
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (user_id, source_event_id, confirmation_type, prompt, expires_at, metadata_json),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_pending_confirmation_requests(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, confirmation_type, prompt, status,
                   response_text, created_at, responded_at, expires_at, metadata_json
            FROM confirmation_requests
            WHERE user_id = ? AND status = 'pending'
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_confirmation_row(row) for row in cur.fetchall()]

    def get_recent_confirmation_requests(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, confirmation_type, prompt, status,
                   response_text, created_at, responded_at, expires_at, metadata_json
            FROM confirmation_requests
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_confirmation_row(row) for row in cur.fetchall()]

    def get_expired_pending_confirmation_requests(
        self,
        user_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, confirmation_type, prompt, status,
                   response_text, created_at, responded_at, expires_at, metadata_json
            FROM confirmation_requests
            WHERE user_id = ?
              AND status = 'pending'
              AND expires_at IS NOT NULL
              AND expires_at <= CURRENT_TIMESTAMP
            ORDER BY expires_at ASC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_confirmation_row(row) for row in cur.fetchall()]

    def update_confirmation_request_status(
        self,
        confirmation_id: int,
        status: str,
        response_text: str | None = None,
    ) -> None:
        allowed_statuses = {
            "pending",
            "confirmed_ok",
            "confirmed_escalate",
            "cancelled",
            "expired",
        }
        if status not in allowed_statuses:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed_statuses))}")

        if status == "pending":
            self.conn.execute(
                """
                UPDATE confirmation_requests
                SET status = ?, response_text = ?, responded_at = NULL
                WHERE id = ?
                """,
                (status, response_text, confirmation_id),
            )
        else:
            self.conn.execute(
                """
                UPDATE confirmation_requests
                SET status = ?, response_text = ?, responded_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, response_text, confirmation_id),
            )
        self.conn.commit()

    def get_confirmation_request_by_id(self, confirmation_id: int) -> dict[str, Any] | None:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, confirmation_type, prompt, status,
                   response_text, created_at, responded_at, expires_at, metadata_json
            FROM confirmation_requests
            WHERE id = ?
            """,
            (confirmation_id,),
        )
        row = cur.fetchone()
        return self._parse_confirmation_row(row) if row else None

    @staticmethod
    def _parse_incident_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        metadata_json = item.pop("metadata_json", None)
        if metadata_json:
            try:
                item["metadata"] = json.loads(metadata_json)
            except json.JSONDecodeError:
                item["metadata"] = metadata_json
        else:
            item["metadata"] = None
        return item

    @staticmethod
    def _parse_timeline_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        metadata_json = item.pop("metadata_json", None)
        if metadata_json:
            try:
                item["metadata"] = json.loads(metadata_json)
            except json.JSONDecodeError:
                item["metadata"] = metadata_json
        else:
            item["metadata"] = None
        return item

    def add_incident(
        self,
        user_id: int,
        incident_type: str,
        title: str,
        source_event_id: int | None = None,
        room: str | None = None,
        severity: str | None = None,
        status: str = "open",
        summary: str | None = None,
        metadata: dict | None = None,
    ) -> int:
        allowed_statuses = {"open", "resolved", "expired", "cancelled", "simulated_escalated"}
        if status not in allowed_statuses:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed_statuses))}")

        metadata_json = json.dumps(metadata) if metadata is not None else None
        cur = self.conn.execute(
            """
            INSERT INTO incidents (
                user_id, source_event_id, incident_type, title, room, severity,
                status, summary, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                source_event_id,
                incident_type,
                title,
                room,
                severity,
                status,
                summary,
                metadata_json,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_incident_by_id(self, incident_id: int) -> dict[str, Any] | None:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, incident_type, title, room, severity,
                   status, summary, started_at, updated_at, closed_at, metadata_json
            FROM incidents
            WHERE id = ?
            """,
            (incident_id,),
        )
        row = cur.fetchone()
        return self._parse_incident_row(row) if row else None

    def get_incident_by_source_event_id(self, source_event_id: int) -> dict[str, Any] | None:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, incident_type, title, room, severity,
                   status, summary, started_at, updated_at, closed_at, metadata_json
            FROM incidents
            WHERE source_event_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source_event_id,),
        )
        row = cur.fetchone()
        return self._parse_incident_row(row) if row else None

    def get_recent_incidents(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, incident_type, title, room, severity,
                   status, summary, started_at, updated_at, closed_at, metadata_json
            FROM incidents
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_incident_row(row) for row in cur.fetchall()]

    def get_open_incidents(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, user_id, source_event_id, incident_type, title, room, severity,
                   status, summary, started_at, updated_at, closed_at, metadata_json
            FROM incidents
            WHERE user_id = ? AND status = 'open'
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        return [self._parse_incident_row(row) for row in cur.fetchall()]

    def update_incident_status(
        self,
        incident_id: int,
        status: str,
        summary: str | None = None,
        close: bool = False,
    ) -> None:
        allowed_statuses = {"open", "resolved", "expired", "cancelled", "simulated_escalated"}
        if status not in allowed_statuses:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed_statuses))}")

        if close:
            self.conn.execute(
                """
                UPDATE incidents
                SET status = ?,
                    summary = COALESCE(?, summary),
                    updated_at = CURRENT_TIMESTAMP,
                    closed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, summary, incident_id),
            )
        else:
            self.conn.execute(
                """
                UPDATE incidents
                SET status = ?,
                    summary = COALESCE(?, summary),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (status, summary, incident_id),
            )
        self.conn.commit()

    def add_incident_timeline_item(
        self,
        incident_id: int,
        item_type: str,
        title: str,
        summary: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
        source_id: int | None = None,
        metadata: dict | None = None,
    ) -> int:
        metadata_json = json.dumps(metadata) if metadata is not None else None
        cur = self.conn.execute(
            """
            INSERT INTO incident_timeline_items (
                incident_id, item_type, source_type, source_id, title, summary, status, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                item_type,
                source_type,
                source_id,
                title,
                summary,
                status,
                metadata_json,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def get_incident_timeline_items(
        self,
        incident_id: int,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, incident_id, item_type, source_type, source_id, title, summary,
                   status, created_at, metadata_json
            FROM incident_timeline_items
            WHERE incident_id = ?
            ORDER BY id ASC
            LIMIT ?
            """,
            (incident_id, limit),
        )
        return [self._parse_timeline_row(row) for row in cur.fetchall()]

    @staticmethod
    def _parse_heartbeat_row(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
        item = dict(row)
        metadata_json = item.pop("metadata_json", None)
        if metadata_json:
            try:
                item["metadata"] = json.loads(metadata_json)
            except json.JSONDecodeError:
                item["metadata"] = metadata_json
        else:
            item["metadata"] = None
        return item

    def upsert_service_heartbeat(
        self,
        user_id: int,
        service_name: str,
        status: str = "online",
        pid: int | None = None,
        metadata: dict | None = None,
    ) -> None:
        metadata_json = json.dumps(metadata) if metadata is not None else None
        self.conn.execute(
            """
            INSERT INTO service_heartbeats (
                user_id, service_name, status, pid, metadata_json
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, service_name) DO UPDATE SET
                status = excluded.status,
                pid = excluded.pid,
                metadata_json = excluded.metadata_json,
                last_seen_at = CURRENT_TIMESTAMP
            """,
            (user_id, service_name, status, pid, metadata_json),
        )
        self.conn.commit()

    def get_service_heartbeats(self, user_id: int) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, user_id, service_name, status, pid, last_seen_at, started_at, metadata_json
            FROM service_heartbeats
            WHERE user_id = ?
            ORDER BY service_name COLLATE NOCASE ASC
            """,
            (user_id,),
        )
        return [self._parse_heartbeat_row(row) for row in cur.fetchall()]

    def close(self) -> None:
        self.conn.close()
