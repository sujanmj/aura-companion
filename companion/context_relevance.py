from __future__ import annotations

import re
import string

STOPWORDS = {
    "the", "a", "an", "i", "you", "are", "is", "am", "how", "hello", "hi", "hey",
    "today", "now", "me", "my", "to", "for", "of", "in", "on", "and",
}

GREETING_PHRASES = (
    "hello",
    "hi",
    "hey",
    "how are you",
    "good morning",
    "good evening",
    "good afternoon",
)

EMOTIONAL_KEYWORDS = {
    "sad", "lonely", "alone", "low", "anxious", "anxiety", "stress", "stressed",
    "nervous", "worried", "worry", "tension", "heavy", "down", "scared", "afraid",
}

WORK_KEYWORDS = {
    "work", "presentation", "present", "meeting", "interview", "office", "speak", "talk",
}

ALWAYS_KEEP_FACT_KEYS = {
    "preferred_name",
    "preferred_response_style",
    "disliked_response_style",
    "companion_personality",
}

PREFERENCE_MARKERS = (
    "preferred",
    "personality",
    "disliked",
    "companion_personality",
    "preferred_response_style",
    "disliked_response_style",
)


class ContextRelevanceFilter:
    def normalize_text(self, text: str) -> str:
        lowered = text.lower()
        cleaned = lowered.translate(str.maketrans("", "", string.punctuation))
        return " ".join(cleaned.split())

    def extract_keywords(self, text: str) -> set[str]:
        normalized = self.normalize_text(text)
        return {word for word in normalized.split() if word and word not in STOPWORDS}

    def is_generic_greeting(self, text: str) -> bool:
        normalized = self.normalize_text(text)
        if not normalized:
            return False

        if any(keyword in normalized for keyword in EMOTIONAL_KEYWORDS | WORK_KEYWORDS):
            return False

        if any(phrase in normalized for phrase in GREETING_PHRASES):
            return True

        words = set(normalized.split())
        greeting_words = {"hello", "hi", "hey", "aura", "morning", "evening", "afternoon"}
        return bool(words) and words.issubset(greeting_words | STOPWORDS | {"you", "are", "doing", "well"})

    def score_memory_relevance(
        self,
        current_message: str,
        observation: str | None,
        memory_text: str,
    ) -> float:
        message_norm = self.normalize_text(current_message)
        memory_norm = self.normalize_text(memory_text)
        observation_norm = self.normalize_text(observation or "")

        if self.is_generic_greeting(current_message):
            if any(marker in memory_norm for marker in PREFERENCE_MARKERS):
                return 1.0
            return 0.0

        score = 0.0
        message_keywords = self.extract_keywords(message_norm)
        memory_keywords = self.extract_keywords(memory_norm)
        observation_keywords = self.extract_keywords(observation_norm)

        overlap = message_keywords & memory_keywords
        if overlap:
            score += 0.4

        message_blob = f"{message_norm} {observation_norm}"
        if any(term in message_blob for term in WORK_KEYWORDS) and any(
            term in memory_norm for term in WORK_KEYWORDS
        ):
            score += 0.3

        if any(term in message_blob for term in EMOTIONAL_KEYWORDS) and any(
            term in memory_norm for term in EMOTIONAL_KEYWORDS
        ):
            score += 0.3

        if observation_keywords and (observation_keywords & memory_keywords):
            score += 0.2

        return min(max(score, 0.0), 1.0)

    def filter_facts(
        self,
        current_message: str,
        observation: str | None,
        facts: list[dict],
        min_score: float = 0.25,
    ) -> list[dict]:
        filtered: list[dict] = []

        for fact in facts:
            fact_key = str(fact.get("fact_key", ""))
            memory_text = f"{fact_key} {fact.get('fact_value', '')}"
            relevance_score = self.score_memory_relevance(current_message, observation, memory_text)

            if fact_key in ALWAYS_KEEP_FACT_KEYS:
                relevance_score = max(relevance_score, 1.0)

            if fact_key in ALWAYS_KEEP_FACT_KEYS or relevance_score >= min_score:
                item = dict(fact)
                item["relevance_score"] = round(relevance_score, 2)
                filtered.append(item)

        return filtered
