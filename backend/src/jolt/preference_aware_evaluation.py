from __future__ import annotations

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


def preference_blockers(text: str) -> list[str]:
    """Return only blockers explicitly configured in the current saved preferences."""
    preferences = load_job_search_preferences()
    lowered = text.casefold()
    blockers = [
        f"excluded keyword: {phrase}"
        for phrase in preferences.excluded_keywords
        if phrase.strip() and phrase.casefold() in lowered
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
    recommendation, confidence, score, reasons = _ORIGINAL_EVALUATE_TEXT(text)
    blockers = preference_blockers(text)
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
