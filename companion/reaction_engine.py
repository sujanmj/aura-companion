from __future__ import annotations

from typing import Any

from memory.sqlite_store import AuraMemoryStore


class CompanionReactionEngine:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store

    def build_context(self, user_id: int) -> dict[str, Any]:
        return {
            "facts": self.store.get_memory_facts(user_id),
            "observations": self.store.get_latest_observations(user_id),
            "conversations": self.store.get_recent_conversations(user_id),
        }

    def infer_situation(self, context: dict[str, Any]) -> dict[str, Any]:
        facts = context.get("facts", [])
        observations = context.get("observations", [])
        conversations = context.get("conversations", [])

        reasons: list[str] = []
        confidence_scores: list[float] = []
        seen_reasons: set[str] = set()

        has_anxiety_signal = False
        has_presentation_signal = False
        has_stress_signal = False
        has_work_mode_signal = False

        anxiety_terms = ("nervous", "anxious", "anxiety", "stress", "stressed", "worried", "worry")
        presentation_terms = ("presentation", "present", "speak", "talk", "meeting")
        work_mode_terms = ("office", "work", "formal", "dressed", "professional")

        def add_reason(text: str, score: float) -> None:
            if text not in seen_reasons:
                seen_reasons.add(text)
                reasons.append(text)
                confidence_scores.append(score)

        for fact in facts:
            blob = f"{fact.get('fact_key', '')} {fact.get('fact_value', '')}".lower()
            score = float(fact.get("confidence", 0.7))
            if any(term in blob for term in anxiety_terms):
                has_anxiety_signal = True
                add_reason(f"Memory notes anxiety: {fact.get('fact_key')}", score)
            if any(term in blob for term in presentation_terms):
                has_presentation_signal = True
                add_reason(f"Memory mentions presentation context: {fact.get('fact_key')}", score)
            if any(term in blob for term in ("stress", "stressed")):
                has_stress_signal = True

        for conv in conversations:
            blob = f"{conv.get('message', '')} {conv.get('emotion_tag') or ''}".lower()
            if any(term in blob for term in anxiety_terms):
                has_anxiety_signal = True
                add_reason("Recent conversation suggests some nervousness.", 0.8)
            if any(term in blob for term in presentation_terms):
                has_presentation_signal = True
                add_reason("Recent conversation mentions a presentation.", 0.85)
            if any(term in blob for term in ("stress", "stressed")):
                has_stress_signal = True

        for obs in observations:
            blob = f"{obs.get('event_type', '')} {obs.get('event_summary', '')}".lower()
            if any(term in blob for term in work_mode_terms):
                has_work_mode_signal = True
                add_reason(
                    f"Observation suggests work/office mode: {obs.get('event_summary')}",
                    float(obs.get("confidence", 0.5)),
                )

        preferred_name = self._preferred_name(facts)

        if (has_anxiety_signal or has_presentation_signal or has_stress_signal) and has_work_mode_signal:
            situation = "User may be heading into work or a presentation while carrying some nerves."
            emotional_need = "encouragement"
            tone = "warm_confident"
            if not reasons:
                reasons.append("Anxiety or presentation cues combined with work-mode context.")
        elif has_anxiety_signal or has_presentation_signal or has_stress_signal:
            situation = "User seems to have something weighing on them, possibly a presentation or stressful moment."
            emotional_need = "encouragement"
            tone = "warm_confident"
            if not reasons:
                reasons.append("Conversation or memory suggests nervousness or presentation stress.")
        elif has_work_mode_signal:
            situation = "User appears to be in work or office mode."
            emotional_need = "presence"
            tone = "calm_warm"
            if not reasons:
                reasons.append("Visual context suggests a work-ready setting.")
        else:
            situation = "No strong signals — a gentle check-in feels right."
            emotional_need = "presence"
            tone = "calm_warm"
            reasons.append("No strong anxiety or work-mode cues in recent memory.")
            confidence_scores.append(0.5)

        confidence = min(sum(confidence_scores) / len(confidence_scores), 1.0) if confidence_scores else 0.5

        return {
            "situation": situation,
            "emotional_need": emotional_need,
            "tone": tone,
            "confidence": round(confidence, 2),
            "reasons": reasons,
            "preferred_name": preferred_name,
            "has_anxiety_signal": has_anxiety_signal,
            "has_presentation_signal": has_presentation_signal,
            "has_work_mode_signal": has_work_mode_signal,
        }

    def generate_reaction(self, user_id: int) -> dict[str, Any]:
        context = self.build_context(user_id)
        inference = self.infer_situation(context)

        response = self._compose_response(inference, context)

        return {
            "situation": inference["situation"],
            "emotional_need": inference["emotional_need"],
            "tone": inference["tone"],
            "response": response,
            "confidence": inference["confidence"],
            "reasons": inference["reasons"],
        }

    def _preferred_name(self, facts: list[dict[str, Any]]) -> str | None:
        for fact in facts:
            if fact.get("fact_key") == "preferred_name":
                return str(fact.get("fact_value"))
        return None

    def _compose_response(self, inference: dict[str, Any], context: dict[str, Any]) -> str:
        tone = inference["tone"]
        emotional_need = inference["emotional_need"]
        name = inference.get("preferred_name")
        has_anxiety = inference.get("has_anxiety_signal", False)
        has_presentation = inference.get("has_presentation_signal", False)
        has_work_mode = inference.get("has_work_mode_signal", False)

        if tone == "warm_confident" and emotional_need == "encouragement":
            if has_work_mode and (has_anxiety or has_presentation):
                opening = "You look ready today."
                if has_presentation:
                    middle = (
                        "I remember that presentation was on your mind, "
                        "but you've handled bigger things than this."
                    )
                else:
                    middle = (
                        "I know today might feel like a lot, "
                        "but you've handled bigger things than this."
                    )
                closing = "Take one deep breath and keep it calm."
                return f"{opening} {middle} {closing}"

            if has_presentation:
                return (
                    "That presentation has been sitting with you, and it makes sense to feel a little on edge. "
                    "You've prepared more than you think. One steady breath, then take it one step at a time."
                )

            return (
                "Something seems to be weighing on you, and that's okay. "
                "You don't have to carry it all at once. Just the next small step."
            )

        if has_work_mode:
            if name:
                return f"Hey {name} — you seem set for the day. I'm here if you want a quiet moment before diving in."
            return "You seem set for the day. I'm here if you want a quiet moment before diving in."

        if name:
            return f"Hey {name} — just checking in. No rush. I'm here whenever you want to talk."
        return "Just checking in. No rush. I'm here whenever you want to talk."
