from __future__ import annotations

from typing import Any

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
]


class PromptBuilder:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def build_companion_prompt(self, user_id: int, situation_result: dict[str, Any]) -> str:
        facts = self.store.get_memory_facts(user_id)
        conversations = self.store.get_recent_conversations(user_id, limit=8)
        observations = self.store.get_latest_observations(user_id, limit=5)
        feedback = self._load_feedback(user_id)

        sections = [
            AURA_IDENTITY,
            "",
            "Style rules:",
            *[f"- {rule}" for rule in STYLE_RULES],
        ]

        if facts:
            sections.extend(["", "User memory facts:"])
            for fact in facts:
                sections.append(f"- {fact.get('fact_key')}: {fact.get('fact_value')}")

        if conversations:
            sections.extend(["", "Recent conversation:"])
            for conv in reversed(conversations):
                role = conv.get("role", "unknown")
                message = conv.get("message", "")
                emotion = conv.get("emotion_tag")
                suffix = f" [{emotion}]" if emotion else ""
                sections.append(f"- {role}: {message}{suffix}")

        if observations:
            sections.extend(["", "Latest observations:"])
            for obs in observations:
                sections.append(f"- {obs.get('event_summary')}")

        if feedback:
            sections.extend(["", "Recent response feedback:"])
            for item in feedback[:5]:
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

    def _load_feedback(self, user_id: int) -> list[dict[str, Any]]:
        if hasattr(self.store, "get_recent_response_feedback"):
            return self.store.get_recent_response_feedback(user_id, limit=5)
        return []
