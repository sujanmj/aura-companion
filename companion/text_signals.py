"""Small, conservative text checks for explicit emotional language."""

from __future__ import annotations

import re

NEGATION_SUFFIX = re.compile(
    r"(?:^|\s)(?:not|never|no longer|no|don't|dont|do not|isn't|isnt|is not|aren't|arent|are not|without)(?:\s+\w+){0,2}$"
)
UNCERTAINTY_SUFFIX = re.compile(
    r"(?:^|\s)(?:maybe|perhaps|possibly|might|may|could(?: be)?|not sure|unsure|uncertain|not necessarily|don't know|dont know|do not know|can't tell|cant tell|cannot tell|hard to tell|wonder(?: if| whether))(?:(?:[\s,]+[\w']+)){0,4}$"
)


def _uncertainty_before(text: str, start: int) -> bool:
    # A short window avoids carrying a hedge from an unrelated earlier clause.
    prefix = re.split(r"[.!?;\n]", text[:start])[-1]
    return bool(UNCERTAINTY_SUFFIX.search(" ".join(prefix.split()[-8:])))


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
        for match in pattern.finditer(normalized):
            if (
                not negates_signal(normalized[: match.end()], (term,))
                and not _uncertainty_before(normalized, match.start())
            ):
                return True
    return False


def uncertain_signal(text: str, terms: tuple[str, ...]) -> bool:
    """Return whether a signal appears only under an explicit uncertainty cue."""
    normalized = text.lower().replace("’", "'")
    found = False
    for term in terms:
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)")
        for match in pattern.finditer(normalized):
            if negates_signal(normalized[: match.end()], (term,)):
                continue
            found = True
            if not _uncertainty_before(normalized, match.start()):
                return False
    return found
