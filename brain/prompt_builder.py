from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from companion.context_relevance import ContextRelevanceFilter
from memory.sqlite_store import AuraMemoryStore

AURA_IDENTITY = (
    "You are AURA, a loyal virtual human companion. "
    "You are emotionally present, warm, natural, practical, and not robotic."
)

STYLE_RULES = [
    'Never say "I detected"',
    'Never say "According to my database"',
    "Never sound like a sensor log",
    "Do not overclaim emotions",
    "Be concise",
    "Be specific to the user's context",
    "If user is low/sad, comfort first, advice second",
    "If user is anxious before work/presentation, give calm confidence",
    "Do not mention older memories, old conversations, or old observations unless they are clearly relevant to the CURRENT USER MESSAGE or latest observation.",
    "Treat on-device scene estimates as uncertain clues, never proof of a person's identity, an activity, or an exact object's location.",
]


class PromptBuilder:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store
        self.relevance_filter = ContextRelevanceFilter()

    def build_companion_prompt(self, user_id: int, situation_result: dict[str, Any]) -> str:
        facts = self.store.get_memory_facts(user_id)
        conversations = self.store.get_recent_conversations(user_id, limit=8)
        observations = self.store.get_latest_observations(user_id, limit=20)
        feedback = self._load_feedback(user_id)

        current_message = self._latest_user_message(conversations)
        latest_record = next(
            (item for item in observations if item.get("source") != "mac_local_vision"),
            None,
        )
        recent_visual = self._select_recent_visual_observations(current_message, observations)
        latest_observation = (
            latest_record.get("event_summary") if latest_record else
            (recent_visual[0].get("event_summary") if recent_visual else None)
        )
        relevant_facts = self.relevance_filter.filter_facts(current_message, latest_observation, facts)
        previous_assistant = self._previous_assistant_message(conversations)
        relevant_device_events = self._load_relevant_device_events(user_id, current_message)

        sections = [
            AURA_IDENTITY,
            "",
            "Style rules:",
            *[f"- {rule}" for rule in STYLE_RULES],
        ]

        sections.extend(["", "CURRENT USER MESSAGE:", current_message or "(none)"])

        if latest_observation and latest_record:
            sections.extend(["", "Latest observation:", f"- {latest_observation}"])

        if recent_visual:
            sections.extend(
                [
                    "",
                    "Fresh on-device visual estimates (clues only; they cannot identify a person or confirm an exact object or activity):",
                ]
            )
            for item in recent_visual:
                confidence = float(item.get("confidence", 0.0))
                recorded = item.get("created_at", "unknown time")
                sections.append(
                    f"- {item.get('event_summary', '')} "
                    f"(confidence={confidence:.2f}, recorded={recorded})"
                )

        if relevant_device_events:
            sections.extend(["", "Relevant device events:"])
            for event in relevant_device_events:
                room = event.get("room")
                room_suffix = f" [{room}]" if room else ""
                sections.append(
                    f"- {event.get('event_type')}: {event.get('event_summary')} "
                    f"(severity={event.get('severity')}){room_suffix}"
                )

        if relevant_facts:
            sections.extend(["", "Relevant memory facts:"])
            for fact in relevant_facts:
                sections.append(f"- {fact.get('fact_key')}: {fact.get('fact_value')}")

        if previous_assistant:
            sections.extend(
                [
                    "",
                    "Previous assistant message:",
                    f"- {previous_assistant.get('message', '')}",
                ]
            )

        if feedback:
            sections.extend(["", "Recent response feedback:"])
            for item in feedback[:3]:
                rating = item.get("rating", "unknown")
                note = item.get("feedback_text") or ""
                response_text = item.get("response_text", "")
                sections.append(f"- {rating}: {response_text} ({note})".rstrip())

        sections.extend(
            [
                "",
                "Current inferred situation:",
                situation_result.get("situation", ""),
                "",
                "Emotional need:",
                situation_result.get("emotional_need", ""),
                "",
                "Tone:",
                situation_result.get("tone", ""),
                "",
                "Write only the final spoken response for the user.",
                "Return plain text only. No JSON. No explanation. No labels.",
            ]
        )

        return "\n".join(sections)

    def _select_recent_visual_observations(
        self,
        current_message: str,
        observations: list[dict[str, Any]],
        *,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return only fresh and relevant derived scene summaries, never raw media."""
        now = now or datetime.now(timezone.utc)
        message_words = self.relevance_filter.extract_keywords(current_message)
        visual_intent = bool(
            message_words
            & {"see", "seeing", "look", "looking", "room", "around", "find", "where", "search", "searching"}
        )
        selected: list[dict[str, Any]] = []
        for item in observations:
            if item.get("source") != "mac_local_vision":
                continue
            recorded = item.get("created_at")
            if not isinstance(recorded, str):
                continue
            try:
                timestamp = datetime.fromisoformat(recorded.replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            age = now - timestamp.astimezone(timezone.utc)
            if age < timedelta(minutes=-1) or age > timedelta(minutes=10):
                continue
            summary = str(item.get("event_summary", ""))
            summary_words = self.relevance_filter.extract_keywords(summary)
            if not visual_intent and not (message_words & summary_words):
                continue
            selected.append(item)
            if len(selected) == 3:
                break
        return selected

    def _latest_user_message(self, conversations: list[dict[str, Any]]) -> str:
        for conv in conversations:
            if conv.get("role") == "user":
                return str(conv.get("message", ""))
        return ""

    def _previous_assistant_message(self, conversations: list[dict[str, Any]]) -> dict[str, Any] | None:
        latest_user_idx: int | None = None
        for index, conv in enumerate(conversations):
            if conv.get("role") == "user":
                latest_user_idx = index
                break

        if latest_user_idx is None:
            return None

        for conv in conversations[latest_user_idx + 1 :]:
            if conv.get("role") == "assistant":
                return conv
        return None

    def _load_feedback(self, user_id: int) -> list[dict[str, Any]]:
        if hasattr(self.store, "get_recent_response_feedback"):
            return self.store.get_recent_response_feedback(user_id, limit=5)
        return []

    def _load_relevant_device_events(
        self,
        user_id: int,
        current_message: str,
    ) -> list[dict[str, Any]]:
        if not hasattr(self.store, "get_recent_device_events"):
            return []

        events = self.store.get_recent_device_events(user_id, limit=10)
        return self.relevance_filter.filter_device_events(current_message, events)
