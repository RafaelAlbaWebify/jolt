from __future__ import annotations

import re
from collections.abc import Callable

from jolt import workflow
from jolt.job_search_preferences import load_job_search_preferences

EvaluationResult = tuple[str, str, int, list[str]]
_ORIGINAL_EVALUATE_TEXT: Callable[[str], EvaluationResult] = workflow.evaluate_text
_INSTALLED = False

_LANGUAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "french": ("french", "français", "francais", "französisch", "franzoesisch"),
    "german": ("german", "deutsch", "deutschkenntnisse"),
    "italian": ("italian", "italiano", "italienisch"),
    "dutch": ("dutch", "nederlands", "niederländisch", "niederlaendisch"),
    "portuguese": ("portuguese", "português", "portugues"),
}

_LANGUAGE_REQUIREMENT_MARKERS = (
    "required",
    "mandatory",
    "must speak",
    "must have",
    "fluency",
    "fluent",
    "excellent",
    "very good",
    "good command",
    "minimum b1",
    "minimum b2",
    "b1 level",
    "b2 level",
    "c1 level",
    "c2 level",
    "b1-niveau",
    "b2-niveau",
    "c1-niveau",
    "c2-niveau",
    "sehr gute",
    "gute deutsch",
    "gute kenntnisse",
    "kenntnisse auf",
    "verhandlungssicher",
    "fließend",
    "fliessend",
    "courant",
    "obligatoire",
)

_LANGUAGE_PREFERENCE_MARKERS = (
    "preferred",
    "advantage",
    "a plus",
    "plus",
    "nice to have",
    "desirable",
    "optional",
    "valorable",
    "valorable",
)

_SHIFT_PATTERNS: dict[str, tuple[str, ...]] = {
    "night": (
        r"\bnight shifts?\b",
        r"\bovernight shifts?\b",
        r"\bnachtschicht\b",
        r"\bturno nocturno\b",
    ),
    "rotating": (
        r"\brotating shifts?\b",
        r"\brotational shifts?\b",
        r"\bschichtsystem\b",
        r"\bwechselschicht\b",
        r"\bturnos rotativos\b",
    ),
    "weekend": (
        r"\bweekend coverage\b",
        r"\bweekend shifts?\b",
        r"\bone weekend day\b",
        r"\btuesday\s*[–-]\s*saturday\b",
        r"\bsunday\s*[–-]\s*thursday\b",
        r"\bwochenendarbeit\b",
        r"\bturnos?(?:\s+de)?\s+fin\s+de\s+semana\b",
        r"\btrabaj(?:ar|o)\b.{0,35}\bfin\s+de\s+semana\b",
        r"\bdisponibilidad\b.{0,35}\bfin\s+de\s+semana\b",
    ),
    "evening": (
        r"\bevening shifts?\b",
        r"\bspätschicht\b",
        r"\bspaetschicht\b",
    ),
}

_DISPATCH_REQUIREMENT_PATTERNS = (
    r"\bdispatch(?:er|ing)?\s+(?:activities|operations|coordination|support|role|team|work)\b",
    r"\b(?:field|service|logistics|transport|delivery)\s+dispatch\b",
    r"\bresponsible\s+for\s+(?:the\s+)?dispatch\b",
    r"\bcoordinate\s+(?:the\s+)?dispatch\b",
    r"\bsupport\s+(?:for\s+)?dispatch\s+activities\b",
)

_FOREIGN_RESIDENCE_LOCATIONS = (
    "germany",
    "portugal",
    "italy",
    "france",
    "romania",
    "lithuania",
    "austria",
    "cyprus",
)

_FOREIGN_RESIDENCE_PATTERN = (
    "(?:" + "|".join(re.escape(location) for location in _FOREIGN_RESIDENCE_LOCATIONS) + ")"
)

_COUNTRY_RESTRICTION_PATTERNS = (
    rf"\bonly\s+for\s+candidates\s+(?:already\s+)?based\s+in\s+"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bmust\s+(?:already\s+)?be\s+based\s+in\s+"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bremote\s+(?:only\s+)?within\s+{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bremote\s+from\s+{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\b{_FOREIGN_RESIDENCE_PATTERN}[-\s]+based\b",
    r"\bdeutschlandweite\s+home[-\s]?working\b",
    rf"\bremote\s*\((?:within\s+)?{_FOREIGN_RESIDENCE_PATTERN}\)\b",
)

_RELOCATION_PATTERNS = (
    r"\brelocation\s+(?:to|required)\b",
    r"\bmust\s+relocate\b",
    r"\brelocate\s+to\b",
    r"\bumzug\s+nach\b",
    r"\breubicaci[oó]n\s+(?:a|en)\b",
)

_EXCLUDED_EMPLOYMENT_PATTERNS = (
    (r"\binternship\b|\bintern\b|\bpraktikum\b|\btrainee internship\b", "internship"),
    (
        r"\btemporary\s+(?:role|position|contract|employment|assignment|job)\b|"
        r"\bfixed[-\s]term\b|\bbefristet\b|"
        r"\barbeitnehmerüberlassung\b|\barbeitnehmerueberlassung\b",
        "temporary or fixed-term employment",
    ),
    (r"\bcategorie protette\b|\bprotected categor(?:y|ies)\b", "protected-category restriction"),
)

_FOREIGN_LOCATION_TERMS = (
    "germany",
    "austria",
    "portugal",
    "italy",
    "france",
    "romania",
    "lithuania",
    "cyprus",
    "munich",
    "berlin",
    "limassol",
    "vilnius",
    "cascais",
    "timisoara",
)

_EXPLICIT_ONSITE_DUTIES = (
    r"\bon[-\s]?site requirement\b",
    r"\bon[-\s]?site role\b",
    r"\bvor ort installationen\b",
    r"\bhardwaretausch\b",
    r"\bon[-\s]?site installations?\b",
    r"\bon[-\s]?site hardware support\b",
)


def sanitize_capture_text(text: str) -> str:
    """Remove known platform promotional chrome without deleting vacancy evidence."""
    lowered = text.casefold()
    premium = lowered.find("job search faster with premium")

    if premium >= 0:
        company = lowered.find("about the company", premium)
        text = text[:premium] + text[company:] if company >= 0 else text[:premium]

    return text.strip()


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


def _language_is_explicitly_preferred(window: str, alias: str) -> bool:
    marker_pattern = "|".join(re.escape(marker) for marker in _LANGUAGE_PREFERENCE_MARKERS)
    alias_pattern = re.escape(alias)
    return bool(
        re.search(
            rf"\b{alias_pattern}\b.{{0,55}}\b(?:{marker_pattern})\b|"
            rf"\b(?:{marker_pattern})\b.{{0,35}}\b{alias_pattern}\b",
            window,
        )
    )


def _required_languages(text: str, allowed_languages: set[str]) -> list[str]:
    required: list[str] = []

    for language, aliases in _LANGUAGE_ALIASES.items():
        if language in allowed_languages:
            continue

        language_found = False
        for alias in aliases:
            for match in re.finditer(re.escape(alias), text):
                start = max(0, match.start() - 100)
                end = min(len(text), match.end() + 100)
                window = text[start:end]

                if _language_is_explicitly_preferred(window, alias):
                    continue

                if any(marker in window for marker in _LANGUAGE_REQUIREMENT_MARKERS):
                    language_found = True
                    break

                if re.search(
                    rf"\b{re.escape(alias)}[-\s]+speaking\b|"
                    rf"\b(?:b1|b2|c1|c2)\b.{{0,35}}\b{re.escape(alias)}\b|"
                    rf"\b{re.escape(alias)}\b.{{0,35}}\b(?:b1|b2|c1|c2)\b",
                    window,
                ):
                    language_found = True
                    break

            if language_found:
                break

        if language_found:
            required.append(language)

    return required


def _country_restriction(text: str) -> bool:
    return any(re.search(pattern, text) for pattern in _COUNTRY_RESTRICTION_PATTERNS)


def _foreign_onsite_requirement(text: str) -> bool:
    foreign_location = any(term in text for term in _FOREIGN_LOCATION_TERMS)
    explicit_onsite = any(re.search(pattern, text) for pattern in _EXPLICIT_ONSITE_DUTIES)
    return foreign_location and explicit_onsite


def preference_blockers(text: str) -> list[str]:
    """Return deterministic blockers from the saved job-search preferences."""
    preferences = load_job_search_preferences()
    lowered = " ".join(sanitize_capture_text(text).casefold().split())

    blockers = [
        f"excluded keyword: {phrase}"
        for phrase in preferences.excluded_keywords
        if phrase.strip() and _excluded_keyword_matches(lowered, phrase)
    ]

    allowed_languages = {language.casefold() for language in preferences.languages}
    for language in _required_languages(lowered, allowed_languages):
        blockers.append(f"required language outside current preferences: {language}")

    for shift in preferences.excluded_shifts:
        patterns = _SHIFT_PATTERNS.get(shift, ())
        if any(re.search(pattern, lowered) for pattern in patterns):
            blockers.append(f"shift excluded by current preferences: {shift}")

    if _country_restriction(lowered):
        blockers.append("remote work is restricted to residence in another country")

    if any(re.search(pattern, lowered) for pattern in _RELOCATION_PATTERNS):
        blockers.append("relocation is required")

    if _foreign_onsite_requirement(lowered):
        blockers.append("onsite duties are required outside the configured locality")

    for pattern, label in _EXCLUDED_EMPLOYMENT_PATTERNS:
        if re.search(pattern, lowered):
            blockers.append(label)

    return list(dict.fromkeys(blockers))


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
    """Install saved-preference checks at the canonical evaluator boundary."""
    global _INSTALLED
    if _INSTALLED:
        return
    workflow.evaluate_text = evaluate_text_with_preferences
    _INSTALLED = True
