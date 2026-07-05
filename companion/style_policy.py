from __future__ import annotations

from typing import Any

from memory.sqlite_store import AuraMemoryStore

DEFAULT_RULES = [
    'Never say "I detected..."',
    'Never say "According to my database..."',
    "Never expose confidence to user.",
    "Never sound like a sensor log.",
    "Prefer warm, specific, context-aware language.",
    "Use the user's name sometimes, not every time.",
    "If the user is low/sad, comfort first, advice second.",
    "If the user is anxious before work, encourage calmly and practically.",
]

ROBOTIC_REPLACEMENTS = {
    "I detected": "It seems like",
    "Formal clothes detected": "You look ready today",
    "According to my database": "I remember",
}


class StylePolicy:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def build_style_context(self, user_id: int) -> dict[str, Any]:
        facts = self.store.get_memory_facts(user_id)
        feedback = self.store.get_recent_response_feedback(user_id)

        preferred_style = ""
        disliked_style = ""
        for fact in facts:
            key = fact.get("fact_key", "")
            if key == "preferred_response_style":
                preferred_style = str(fact.get("fact_value", ""))
            elif key == "disliked_response_style":
                disliked_style = str(fact.get("fact_value", ""))

        recent_good_feedback = [
            item for item in feedback if item.get("rating") == "good"
        ]
        recent_bad_feedback = [
            item for item in feedback if item.get("rating") == "bad"
        ]

        rules = list(DEFAULT_RULES)
        if any(fact.get("fact_key") == "avoid_robotic_replies" for fact in facts):
            rules.append("Avoid robotic or fake-sounding phrasing learned from user feedback.")

        return {
            "preferred_style": preferred_style,
            "disliked_style": disliked_style,
            "recent_good_feedback": recent_good_feedback,
            "recent_bad_feedback": recent_bad_feedback,
            "rules": rules,
        }

    def polish_response(self, response: str, style_context: dict[str, Any]) -> str:
        polished = response.strip()

        for robotic, natural in ROBOTIC_REPLACEMENTS.items():
            polished = polished.replace(robotic, natural)

        for item in style_context.get("recent_bad_feedback", []):
            bad_text = str(item.get("response_text", "")).strip()
            if bad_text and bad_text.lower() in polished.lower():
                polished = polished.replace(bad_text, "You look ready today.")

        if len(polished) > 500:
            polished = polished[:497].rstrip() + "..."

        return polished
