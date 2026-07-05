from __future__ import annotations

from typing import Any

from companion.style_policy import StylePolicy
from memory.sqlite_store import AuraMemoryStore


class CompanionReactionEngine:
    def __init__(self, store: AuraMemoryStore) -> None:
        self.store = store
        self.style_policy = StylePolicy(store)

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
        has_low_mood_signal = False
        has_work_event_signal = False

        anxiety_terms = ("nervous", "anxious", "anxiety", "stress", "stressed", "worried", "worry", "tension")
        presentation_terms = ("presentation", "present", "speak", "talk", "meeting", "interview")
        work_mode_terms = ("office", "work", "formal", "dressed", "professional")
        low_mood_terms = ("sad", "lonely", "alone", "low", "heavy", "down")
        quiet_observation_terms = ("quiet", "still", "sitting", "silent")

        anxiety_fact_keys = {"recent_anxiety", "presentation_anxiety"}
        work_event_fact_keys = {"important_work_event", "presentation_anxiety"}
        low_mood_fact_keys = {"recent_low_mood"}

        def add_reason(text: str, score: float) -> None:
            if text not in seen_reasons:
                seen_reasons.add(text)
                reasons.append(text)
                confidence_scores.append(score)

        for fact in facts:
            fact_key = fact.get("fact_key", "")
            blob = f"{fact_key} {fact.get('fact_value', '')}".lower()
            score = float(fact.get("confidence", 0.7))

            if fact_key in anxiety_fact_keys or any(term in blob for term in anxiety_terms):
                has_anxiety_signal = True
                add_reason(f"Memory notes anxiety: {fact_key}", score)

            if fact_key in work_event_fact_keys or any(term in blob for term in presentation_terms):
                has_presentation_signal = True
                has_work_event_signal = True
                add_reason(f"Memory mentions work event: {fact_key}", score)

            if fact_key in low_mood_fact_keys or any(term in blob for term in low_mood_terms):
                has_low_mood_signal = True
                add_reason(f"Memory notes low mood: {fact_key}", score)

            if any(term in blob for term in ("stress", "stressed")):
                has_stress_signal = True

        for conv in conversations:
            if conv.get("role") != "user":
                continue
            blob = f"{conv.get('message', '')} {conv.get('emotion_tag') or ''}".lower()
            if any(term in blob for term in anxiety_terms):
                has_anxiety_signal = True
                add_reason("Recent conversation suggests some nervousness.", 0.8)
            if any(term in blob for term in presentation_terms):
                has_presentation_signal = True
                has_work_event_signal = True
                add_reason("Recent conversation mentions a work-related event.", 0.85)
            if any(term in blob for term in low_mood_terms):
                has_low_mood_signal = True
                add_reason("Recent conversation suggests feeling low or alone.", 0.8)
            if any(term in blob for term in ("stress", "stressed")):
                has_stress_signal = True

        for obs in observations:
            blob = f"{obs.get('event_type', '')} {obs.get('event_summary', '')}".lower()
            score = float(obs.get("confidence", 0.5))
            if any(term in blob for term in work_mode_terms):
                has_work_mode_signal = True
                add_reason(
                    f"Observation suggests work/office mode: {obs.get('event_summary')}",
                    score,
                )
            if any(term in blob for term in quiet_observation_terms):
                has_low_mood_signal = True
                add_reason(
                    f"Observation suggests quiet or stillness: {obs.get('event_summary')}",
                    score,
                )

        preferred_name = self._preferred_name(facts)

        if has_low_mood_signal:
            situation = "User may need quiet emotional support."
            emotional_need = "comfort"
            tone = "soft_present"
        elif (has_anxiety_signal or has_stress_signal) and (
            has_work_event_signal or has_presentation_signal
        ) and has_work_mode_signal:
            situation = "User may be heading into work or a presentation while carrying some nerves."
            emotional_need = "encouragement"
            tone = "warm_confident"
        elif (has_anxiety_signal or has_stress_signal) and (
            has_work_event_signal or has_presentation_signal
        ):
            situation = "User has an important work event coming up and seems to be carrying some nerves."
            emotional_need = "encouragement"
            tone = "warm_confident"
        elif has_anxiety_signal or has_presentation_signal or has_stress_signal:
            situation = "User seems to have something weighing on them, possibly a presentation or stressful moment."
            emotional_need = "encouragement"
            tone = "warm_confident"
        elif has_work_mode_signal:
            situation = "User appears to be in work or office mode."
            emotional_need = "presence"
            tone = "calm_warm"
        else:
            situation = "No strong signals — a gentle check-in feels right."
            emotional_need = "presence"
            tone = "calm_warm"
            add_reason("No strong emotional cues in recent memory.", 0.5)

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
            "has_low_mood_signal": has_low_mood_signal,
            "has_work_event_signal": has_work_event_signal,
        }

    def generate_reaction(self, user_id: int) -> dict[str, Any]:
        context = self.build_context(user_id)
        inference = self.infer_situation(context)
        style_context = self.style_policy.build_style_context(user_id)
        raw_response = self._compose_response(inference, context, style_context)
        response = self.style_policy.polish_response(raw_response, style_context)

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

    def _compose_response(
        self,
        inference: dict[str, Any],
        context: dict[str, Any],
        style_context: dict[str, Any],
    ) -> str:
        tone = inference["tone"]
        emotional_need = inference["emotional_need"]
        has_anxiety = inference.get("has_anxiety_signal", False)
        has_presentation = inference.get("has_presentation_signal", False)
        has_work_mode = inference.get("has_work_mode_signal", False)
        has_work_event = inference.get("has_work_event_signal", False)

        if tone == "soft_present" and emotional_need == "comfort":
            return (
                "I'm here with you. We don't have to fix everything right now. "
                "Tell me one thing that felt heavy today, or I can just stay quiet with you for a bit."
            )

        if tone == "warm_confident" and emotional_need == "encouragement":
            if has_work_mode and (has_anxiety or has_presentation or has_work_event):
                opening = "You look ready today."
                if has_presentation or has_work_event:
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

            if has_presentation or has_work_event:
                return (
                    "That important event has been sitting with you, and it makes sense to feel a little on edge. "
                    "You've prepared more than you think. One steady breath, then take it one step at a time."
                )

            return (
                "Something seems to be weighing on you, and that's okay. "
                "You don't have to carry it all at once. Just the next small step."
            )

        name = inference.get("preferred_name")
        if has_work_mode:
            if name:
                return f"Hey {name} — you seem set for the day. I'm here if you want a quiet moment before diving in."
            return "You seem set for the day. I'm here if you want a quiet moment before diving in."

        if name:
            return f"Hey {name} — just checking in. No rush. I'm here whenever you want to talk."
        return "Just checking in. No rush. I'm here whenever you want to talk."
