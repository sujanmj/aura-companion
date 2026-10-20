"""Small, conservative text checks for explicit emotional language."""

from __future__ import annotations

import re

NEGATION_SUFFIX = re.compile(
    r"(?:^|\s)(?:not|never|no longer|no|don't|dont|do not|isn't|isnt|is not|aren't|arent|are not|without)(?:\s+\w+){0,2}$"
)


def negates_signal(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower().replace("’", "'")
    for term in terms:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
        for match in pattern.finditer(normalized):
            preceding_words = re.sub(r"[^\w']+", " ", normalized[: match.start()]).split()
            if NEGATION_SUFFIX.search(" ".join(preceding_words[-3:])):
                return True
    return False


def contains_signal(text: str, terms: tuple[str, ...]) -> bool:
    normalized = text.lower().replace("’", "'")
    for term in terms:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
        if any(not negates_signal(normalized[: match.end()], (term,)) for match in pattern.finditer(normalized)):
            return True
    return False
