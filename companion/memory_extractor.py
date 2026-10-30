from __future__ import annotations

import re

from memory.sqlite_store import AuraMemoryStore
from companion.text_signals import contains_signal


class MemoryExtractor:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def process_user_message(self, user_id: int, message: str) -> list[str]:
        actions: list[str] = []
        lowered = message.lower()
        emotion_tag: str | None = None

        explicit_note = self._explicit_remembered_note(message)
        if explicit_note:
            if self._contains_secret_request(explicit_note):
                actions.append("not stored: sensitive credential or financial detail")
            else:
                self.store.add_observation(
                    user_id,
                    event_type="user_remembered_event",
                    event_summary=explicit_note,
                    confidence=1.0,
                    source="user_explicit",
                )
                actions.append("remembered explicit event note")

        if contains_signal(lowered, ("nervous", "anxious", "stress", "tension", "worried")):
            emotion_tag = "anxious"
            self.store.remember_fact(
                user_id,
                fact_key="recent_anxiety",
                fact_value="User recently expressed anxiety or stress and may need calm encouragement.",
                confidence=0.75,
                source="conversation",
            )
            actions.append("remembered fact: recent_anxiety")

        if any(term in lowered for term in ("presentation", "meeting", "interview")):
            self.store.remember_fact(
                user_id,
                fact_key="important_work_event",
                fact_value="User mentioned an important work-related event and may appreciate encouragement before it.",
                confidence=0.8,
                source="conversation",
            )
            actions.append("remembered fact: important_work_event")

        if contains_signal(lowered, ("sad", "lonely", "alone", "low")):
            emotion_tag = "low"
            self.store.remember_fact(
                user_id,
                fact_key="recent_low_mood",
                fact_value="User recently expressed feeling low or lonely and may need gentle presence.",
                confidence=0.75,
                source="conversation",
            )
            actions.append("remembered fact: recent_low_mood")

        if any(term in lowered for term in ("gym", "workout")):
            self.store.remember_routine(
                user_id,
                routine_key="fitness_interest",
                routine_value="User cares about gym and fitness.",
                confidence=0.8,
                source="conversation",
            )
            actions.append("remembered routine: fitness_interest")

        self.store.add_conversation(
            user_id,
            role="user",
            message=message,
            emotion_tag=emotion_tag,
        )
        actions.insert(0, "stored user conversation")

        return actions

    @staticmethod
    def _explicit_remembered_note(message: str) -> str | None:
        addressed_message = re.sub(
            r"^\s*(?:hey\s+)?aura\b\s*[,.:]?\s*",
            "",
            message,
            count=1,
            flags=re.IGNORECASE,
        )
        match = re.match(
            r"^\s*(?:please\s+)?remember(?:\s+(?:that|this))?\s*[:,-]?\s*(.+?)\s*[.!?]*\s*$",
            addressed_message,
            re.IGNORECASE,
        )
        if not match:
            return None
        note = match.group(1).strip().strip('"“”\'')
        return note[:500] if note else None

    @staticmethod
    def _contains_secret_request(note: str) -> bool:
        return bool(
            re.search(
                r"\b(password|passcode|pin|api key|access token|secret key|"
                r"social security|credit card|bank account|cvv)\b",
                note,
                re.IGNORECASE,
            )
        )
