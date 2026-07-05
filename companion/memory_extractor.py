from __future__ import annotations

from memory.sqlite_store import AuraMemoryStore


class MemoryExtractor:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def process_user_message(self, user_id: int, message: str) -> list[str]:
        actions: list[str] = []
        lowered = message.lower()
        emotion_tag: str | None = None

        if any(term in lowered for term in ("nervous", "anxious", "stress", "tension", "worried")):
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

        if any(term in lowered for term in ("sad", "lonely", "alone", "low")):
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
