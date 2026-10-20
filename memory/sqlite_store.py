from __future__ import annotations

import json
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

    def export_user_memory(self, user_id: int) -> dict[str, Any]:
        user = self.conn.execute(
            "SELECT id, name, preferred_name, comfort_style, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not user:
            raise ValueError("User not found")

        tables = (
            "companion_preferences",
            "conversation_logs",
            "memory_facts",
            "forgotten_memory_facts",
            "observations",
            "mood_logs",
            "routine_memory",
            "forgotten_memory_routines",
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

    def get_latest_observations(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
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

    def get_recent_person_events(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT id, person_id, event_type, event_summary, source, room, confidence, created_at
            FROM person_events
            WHERE user_id = ?
            ORDER BY id DESC
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
