from __future__ import annotations

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
]


class PromptBuilder:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store
        self.relevance_filter = ContextRelevanceFilter()

    def build_companion_prompt(self, user_id: int, situation_result: dict[str, Any]) -> str:
        facts = self.store.get_memory_facts(user_id)
        conversations = self.store.get_recent_conversations(user_id, limit=8)
        observations = self.store.get_latest_observations(user_id, limit=5)
        feedback = self._load_feedback(user_id)

        current_message = self._latest_user_message(conversations)
        latest_observation = observations[0].get("event_summary") if observations else None
        relevant_facts = self.relevance_filter.filter_facts(current_message, latest_observation, facts)
        previous_assistant = self._previous_assistant_message(conversations)

        sections = [
            AURA_IDENTITY,
            "",
            "Style rules:",
            *[f"- {rule}" for rule in STYLE_RULES],
        ]

        sections.extend(["", "CURRENT USER MESSAGE:", current_message or "(none)"])

        if latest_observation:
            sections.extend(["", "Latest observation:", f"- {latest_observation}"])

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
