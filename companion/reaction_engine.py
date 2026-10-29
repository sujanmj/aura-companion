from __future__ import annotations

import re
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from brain.llm_provider import LLMProvider
from brain.prompt_builder import PromptBuilder
from companion.context_relevance import ContextRelevanceFilter
from companion.style_policy import StylePolicy
from companion.text_signals import contains_signal, negates_signal, uncertain_signal
from memory.sqlite_store import AuraMemoryStore


class CompanionReactionEngine:
    def __init__(self, store: AuraMemoryStore, use_llm: bool = False) -> None:
        self.store = store
        self.use_llm = use_llm
        self.style_policy = StylePolicy(store)
        self.prompt_builder = PromptBuilder(store)
        self.llm_provider = LLMProvider()
        self.relevance_filter = ContextRelevanceFilter()

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

        latest_user_message = self._latest_user_message(conversations)
        anxiety_terms = ("nervous", "anxious", "anxiety", "stress", "stressed", "worried", "worry", "tension")
        low_mood_terms = ("sad", "lonely", "alone", "low", "heavy", "down")
        denies_anxiety = (
            negates_signal(latest_user_message, anxiety_terms)
            and not contains_signal(latest_user_message, anxiety_terms)
        ) or uncertain_signal(latest_user_message, anxiety_terms)
        denies_low_mood = (
            negates_signal(latest_user_message, low_mood_terms)
            and not contains_signal(latest_user_message, low_mood_terms)
        ) or uncertain_signal(latest_user_message, low_mood_terms)
        latest_observation = observations[0].get("event_summary") if observations else None
        preferred_name = self._preferred_name(facts)

        if self.relevance_filter.is_generic_greeting(latest_user_message):
            return {
                "situation": "User is casually checking in.",
                "emotional_need": "presence",
                "tone": "friendly_warm",
                "confidence": 0.7,
                "reasons": ["Generic greeting; old memories not forced."],
                "preferred_name": preferred_name,
                "has_anxiety_signal": False,
                "has_presentation_signal": False,
                "has_work_mode_signal": False,
                "has_low_mood_signal": False,
                "has_work_event_signal": False,
            }

        filtered_facts = self.relevance_filter.filter_facts(
            latest_user_message,
            latest_observation,
            facts,
        )

        reasons: list[str] = []
        confidence_scores: list[float] = []
        seen_reasons: set[str] = set()

        has_anxiety_signal = False
        has_presentation_signal = False
        has_stress_signal = False
        has_work_mode_signal = False
        has_low_mood_signal = False
        has_work_event_signal = False

        presentation_terms = ("presentation", "present", "speak", "talk", "meeting", "interview")
        work_mode_terms = ("office", "work", "formal", "dressed", "professional")

        anxiety_fact_keys = {"recent_anxiety", "presentation_anxiety"}
        work_event_fact_keys = {"important_work_event", "presentation_anxiety"}
        low_mood_fact_keys = {"recent_low_mood"}

        def add_reason(text: str, score: float) -> None:
            if text not in seen_reasons:
                seen_reasons.add(text)
                reasons.append(text)
                confidence_scores.append(score)

        for fact in filtered_facts:
            fact_key = fact.get("fact_key", "")
            blob = f"{fact_key} {fact.get('fact_value', '')}".lower()
            score = float(fact.get("confidence", 0.7))

            if not denies_anxiety and (
                fact_key in anxiety_fact_keys
                or contains_signal(blob, anxiety_terms)
            ):
                has_anxiety_signal = True
                add_reason(f"Memory notes anxiety: {fact_key}", score)

            if fact_key in work_event_fact_keys or any(term in blob for term in presentation_terms):
                has_presentation_signal = True
                has_work_event_signal = True
                add_reason(f"Memory mentions work event: {fact_key}", score)

            if not denies_low_mood and (
                fact_key in low_mood_fact_keys
                or contains_signal(blob, low_mood_terms)
            ):
                has_low_mood_signal = True
                add_reason(f"Memory notes low mood: {fact_key}", score)

            if not denies_anxiety and contains_signal(blob, ("stress", "stressed")):
                has_stress_signal = True

        # Emotional cues describe the current turn. Older user messages remain
        # available as relevant memory, but must not make unrelated requests
        # sound anxious or sad.
        current_turn = next(
            (conv for conv in conversations if conv.get("role") == "user"),
            None,
        )
        if current_turn:
            message = str(current_turn.get('message', '')).lower()
            emotion_tag = str(current_turn.get('emotion_tag') or '').lower()
            if not denies_anxiety and (
                contains_signal(message, anxiety_terms)
                or contains_signal(emotion_tag, anxiety_terms)
            ):
                has_anxiety_signal = True
                add_reason("Recent conversation suggests some nervousness.", 0.8)
            if contains_signal(message, presentation_terms):
                has_presentation_signal = True
                has_work_event_signal = True
                add_reason("Recent conversation mentions a work-related event.", 0.85)
            if not denies_low_mood and (
                contains_signal(message, low_mood_terms)
                or contains_signal(emotion_tag, low_mood_terms)
            ):
                has_low_mood_signal = True
                add_reason("Recent conversation suggests feeling low or alone.", 0.8)
            if not denies_anxiety and contains_signal(message, ("stress", "stressed")):
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
        elif has_anxiety_signal or has_stress_signal:
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
        latest_user_message = self._latest_user_message(context.get("conversations", []))
        inference = self.infer_situation(context)
        style_context = self.style_policy.build_style_context(user_id)

        remembered_location = self._remembered_location_reply(
            latest_user_message,
            context.get("observations", []),
        )
        if remembered_location:
            response, source = remembered_location
            return {
                "situation": "The user asked about a previously noted or estimated item's location.",
                "emotional_need": "practical_help",
                "tone": "warm_practical",
                "response": response,
                "confidence": 0.95 if source == "user note" else 0.85,
                "reasons": [f"Recalled a matching {source} locally."],
            }

        remembered_routine = self._remembered_routine_reply(user_id, latest_user_message)
        if remembered_routine:
            return {
                "situation": "The user asked about a saved routine memory.",
                "emotional_need": "practical_help",
                "tone": "warm_practical",
                "response": remembered_routine,
                "confidence": 0.85,
                "reasons": ["Recalled a relevant routine memory locally."],
            }

        raw_response = self._compose_response(inference, context, style_context)
        fallback_response = self.style_policy.polish_response(raw_response, style_context)

        if self.relevance_filter.is_generic_greeting(latest_user_message):
            return {
                "situation": "User is casually checking in.",
                "emotional_need": "presence",
                "tone": "friendly_warm",
                "response": fallback_response,
                "confidence": 0.7,
                "reasons": ["Generic greeting; skipped LLM to avoid stale memory overuse."],
            }

        reasons = list(inference["reasons"])
        response = fallback_response
        if self.use_llm:
            prompt = self.prompt_builder.build_companion_prompt(user_id, inference)
            llm_response = self.llm_provider.generate(prompt)
            if llm_response:
                response = self.style_policy.polish_response(llm_response, style_context)
                reasons.append("LLM provider generated response")
            else:
                reasons.append("LLM unavailable, used local reaction fallback")

        return {
            "situation": inference["situation"],
            "emotional_need": inference["emotional_need"],
            "tone": inference["tone"],
            "response": response,
            "confidence": inference["confidence"],
            "reasons": reasons,
        }

    def _remembered_routine_reply(self, user_id: int, message: str) -> str | None:
        if not re.search(
            r"\b(routine|habit|usually|exercise|workout|gym|meal|bedtime|sleep)\b",
            message,
            re.IGNORECASE,
        ):
            return None

        routines = [
            {
                "fact_key": item.get("routine_key", ""),
                "fact_value": item.get("routine_value", ""),
                "confidence": item.get("confidence", 0.5),
            }
            for item in self.store.get_routine_memory(user_id)
        ]
        relevant = self.relevance_filter.filter_facts(message, None, routines)
        if not relevant:
            return None

        selected = max(relevant, key=lambda item: item.get("relevance_score", 0.0))
        routine_value = str(selected.get("fact_value", "")).strip().rstrip(".!? ")
        if not routine_value:
            return None
        return f"The routine memory I have says: {routine_value}. It may be incomplete or out of date."

    def _remembered_location_reply(
        self,
        message: str,
        observations: list[dict[str, Any]],
        now: datetime | None = None,
    ) -> tuple[str, str] | None:
        normalized = message.lower().replace("’", "'")
        location_question = re.search(
            r"\b(where|where's|wheres|where is|where are|where did|where have|where can)\b",
            normalized,
        )
        if not location_question:
            return None

        message_keywords = self.relevance_filter.extract_keywords(message)
        if not message_keywords:
            return None

        for item in observations:
            if item.get("source") not in {"user_explicit", "user_correction"}:
                continue
            note = str(item.get("event_summary", "")).strip().rstrip(".!? ")
            note_keywords = self.relevance_filter.extract_keywords(note)
            if not (message_keywords & note_keywords):
                continue

            created_at = item.get("created_at")
            if created_at:
                age_context = f" It was saved {created_at} and may be out of date."
            else:
                age_context = " I don't know when it was saved, so it may be out of date."
            return f"The last note I have says: {note}.{age_context}", "user note"

        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            return None
        for item in observations:
            if item.get("source") != "mac_local_vision":
                continue
            confidence = item.get("confidence")
            if (
                not isinstance(confidence, (int, float))
                or isinstance(confidence, bool)
                or not math.isfinite(confidence)
                or confidence < 0.85
                or confidence > 1.0
            ):
                continue
            created_at = item.get("created_at")
            if not isinstance(created_at, str):
                continue
            try:
                observed_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            age = now.astimezone(timezone.utc) - observed_at.astimezone(timezone.utc)
            if age < timedelta(0) or age > timedelta(minutes=30):
                continue
            summary = str(item.get("event_summary", ""))
            prefix = "On-device scene estimate: "
            if not summary.startswith(prefix):
                continue
            labels = summary[len(prefix):].split(". Human-shaped figure detected:", 1)[0]
            # The confidence value belongs to Vision's top classification only.
            top_label = labels.split(",", 1)[0].strip()
            matched = self.relevance_filter.extract_keywords(top_label) & message_keywords
            if not matched:
                continue
            matched_label = top_label or "an object"
            timestamp = observed_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            response = (
                f"A recent on-device scene estimate mentioned ‘{matched_label}’ "
                f"({confidence:.0%} confidence, saved {timestamp}). It may be a "
                "misidentification or outdated; I can’t tell which room or exact spot."
            )
            return response, "uncertain camera estimate"

        return None

    def _latest_user_message(self, conversations: list[dict[str, Any]]) -> str:
        for conv in conversations:
            if conv.get("role") == "user":
                return str(conv.get("message", ""))
        return ""

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

        if tone == "friendly_warm" and emotional_need == "presence":
            name = inference.get("preferred_name") or "Sujan"
            return (
                f"I'm here, {name}. I'm doing okay — more importantly, how are you feeling right now?"
            )

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
