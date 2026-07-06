from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


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
    ) -> None:
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

    def get_memory_facts(self, user_id: int) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT fact_key, fact_value, confidence, source, last_seen_at
            FROM memory_facts
            WHERE user_id = ?
            ORDER BY last_seen_at DESC
            """,
            (user_id,),
        )
        return [dict(row) for row in cur.fetchall()]

    def get_latest_observations(self, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
        cur = self.conn.execute(
            """
            SELECT event_type, event_summary, confidence, source, created_at
            FROM observations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
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
        return [dict(row) for row in cur.fetchall()]

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

    def close(self) -> None:
        self.conn.close()