from __future__ import annotations

import re
from collections.abc import Callable

from jolt import workflow
from jolt.job_search_preferences import load_job_search_preferences

EvaluationResult = tuple[str, str, int, list[str]]
_ORIGINAL_EVALUATE_TEXT: Callable[[str], EvaluationResult] = workflow.evaluate_text
_INSTALLED = False

_LANGUAGE_TERMS: dict[str, tuple[str, ...]] = {
    "french": (
        "french speaking",
        "french-speaking",
        "must speak french",
        "french required",
        "mandatory french",
    ),
    "german": (
        "german speaking",
        "german-speaking",
        "must speak german",
        "german required",
        "mandatory german",
    ),
    "italian": (
        "italian speaking",
        "italian-speaking",
        "must speak italian",
        "italian required",
        "mandatory italian",
    ),
    "dutch": (
        "dutch speaking",
        "dutch-speaking",
        "must speak dutch",
        "dutch required",
        "mandatory dutch",
    ),
    "portuguese": (
        "portuguese speaking",
        "portuguese-speaking",
        "must speak portuguese",
        "portuguese required",
        "mandatory portuguese",
    ),
}
_SHIFT_TERMS: dict[str, tuple[str, ...]] = {
    "night": ("night shift", "night shifts", "overnight shift"),
    "rotating": ("rotating shift", "rotating shifts", "rotational shift"),
    "weekend": ("weekend coverage", "weekend shift", "weekend shifts"),
    "evening": ("evening shift", "evening shifts"),
}
_DISPATCH_REQUIREMENT_PATTERNS = (
    r"\bdispatch(?:er|ing)?\s+(?:activities|operations|coordination|support|role|team|work)\b",
    r"\b(?:field|service|logistics|transport|delivery)\s+dispatch\b",
    r"\bresponsible\s+for\s+(?:the\s+)?dispatch\b",
    r"\bcoordinate\s+(?:the\s+)?dispatch\b",
    r"\bsupport\s+(?:for\s+)?dispatch\s+activities\b",
)


def sanitize_capture_text(text: str) -> str:
    """Remove known platform chrome that must not influence vacancy assessment."""
    start = text.casefold().find("job search faster with premium")
    if start >= 0:
        end = text.casefold().find("about the company", start)
        if end >= 0:
            text = text[:start] + text[end:]
    return text


def _contains_phrase(text: str, phrase: str) -> bool:
    normalized = " ".join(phrase.casefold().split())
    if not normalized:
        return False
    pattern = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){pattern}(?!\w)", text) is not None


def _excluded_keyword_matches(text: str, phrase: str) -> bool:
    normalized = " ".join(phrase.casefold().split())
    if normalized == "dispatch":
        return any(re.search(pattern, text) for pattern in _DISPATCH_REQUIREMENT_PATTERNS)
    return _contains_phrase(text, normalized)


def preference_blockers(text: str) -> list[str]:
    """Return only blockers explicitly configured in the current saved preferences."""
    preferences = load_job_search_preferences()
    lowered = " ".join(sanitize_capture_text(text).casefold().split())
    blockers = [
        f"excluded keyword: {phrase}"
        for phrase in preferences.excluded_keywords
        if phrase.strip() and _excluded_keyword_matches(lowered, phrase)
    ]

    allowed_languages = {language.casefold() for language in preferences.languages}
    for language, phrases in _LANGUAGE_TERMS.items():
        if language not in allowed_languages and any(phrase in lowered for phrase in phrases):
            blockers.append(f"required language outside current preferences: {language}")

    for shift in preferences.excluded_shifts:
        phrases = _SHIFT_TERMS.get(shift, ())
        if phrases and any(phrase in lowered for phrase in phrases):
            blockers.append(f"shift excluded by current preferences: {shift}")
    return blockers


def evaluate_text_with_preferences(text: str) -> EvaluationResult:
    sanitized = sanitize_capture_text(text)
    recommendation, confidence, score, reasons = _ORIGINAL_EVALUATE_TEXT(sanitized)
    blockers = preference_blockers(sanitized)
    if blockers:
        return (
            "reject",
            "high",
            0,
            [
                "Applied the current saved JOLT job-search preferences.",
                f"Verified preference blocker(s): {', '.join(blockers)}.",
            ],
        )
    return (
        recommendation,
        confidence,
        score,
        ["Applied the current saved JOLT job-search preferences.", *reasons],
    )


def install_preference_aware_evaluation() -> None:
    """Install saved-preference checks at the canonical intake evaluator boundary."""
    global _INSTALLED
    if _INSTALLED:
        return
    workflow.evaluate_text = evaluate_text_with_preferences
    _INSTALLED = True
