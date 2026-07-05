from __future__ import annotations

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

    def close(self) -> None:
        self.conn.close()