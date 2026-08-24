from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, replace
from datetime import UTC, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import Evaluation, Posting, ProfileVersion, utc_now
from jolt.employment_geography import FOREIGN_COUNTRY_TERMS, normalized_location_scope
from jolt.evaluation_strategy import (
    StrategyAssessment,
    StrategyProfile,
    assess_posting,
    default_profile_path,
    load_strategy_profile,
)
from jolt.job_search_preferences import load_job_search_preferences
from jolt.preference_aware_evaluation import preference_blockers, sanitize_capture_text

ENGINE_VERSION = "profile-rules-v9"
_PEOPLE_MANAGEMENT_LABEL = "formal people-management ownership"
_SPAIN_LOCATION_TERMS = (
    "spain",
    "españa",
    "espana",
    "galicia",
    "madrid",
    "barcelona",
    "valencia",
    "andalusia",
    "andalucía",
    "andalucia",
    "a coruña",
    "coruña",
    "vigo",
    "pontevedra",
    "málaga",
    "malaga",
)

_BROAD_REMOTE_LOCATION_TERMS = (
    "worldwide",
    "global",
    "anywhere",
    "european union",
    "europe",
    "emea",
    "eu remote",
)

_EXPLICIT_REMOTE_WORK_PATTERNS = (
    r"(?im)^\s*remote\s*$",
    r"\b(?:fully|100%)\s+remote\b",
    r"\bremote\s+(?:role|position|work|working|arrangement)\b",
    r"\bthis\s+role\s+is\s+remote\b",
    r"\bwork(?:place)?\s*(?:type|mode)?\s*[:\-]\s*remote\b",
    r"\(\s*remote\s*\)",
    r"(?m)(?:^|[·|/,])\s*remote\s*$",
)

_EXPLICIT_HYBRID_WORK_PATTERNS = (
    r"(?im)^\s*hybrid\s*$",
    r"\bhybrid\s+(?:role|position|work|working|schedule|arrangement)\b",
    r"\bwork(?:place)?\s*(?:type|mode)?\s*[:\-]\s*hybrid\b",
    r"\(\s*hybrid\s*\)",
    r"(?m)(?:^|[·|/,])\s*hybrid\s*$",
)

_EXPLICIT_ONSITE_WORK_PATTERNS = (
    r"(?im)^\s*(?:on[- ]?site|onsite)\s*$",
    r"\b(?:on[- ]?site|onsite)\s+(?:role|position|work|working|requirement)\b",
    r"\bwork(?:place)?\s*(?:type|mode)?\s*[:\-]\s*(?:on[- ]?site|onsite)\b",
    r"\(\s*(?:on[- ]?site|onsite)\s*\)",
    r"(?m)(?:^|[·|/,])\s*(?:on[- ]?site|onsite)\s*$",
)

_VIGO_LOCAL_LOCATION_TERMS = (
    "vigo",
    "redondela",
    "mos",
    "o porriño",
    "o porrino",
    "porriño",
    "porrino",
    "nigrán",
    "nigran",
    "gondomar",
    "baiona",
    "cangas",
    "moaña",
    "moana",
    "salceda de caselas",
    "soutomaior",
    "ponteareas",
)

_CLEARLY_DISTANT_SPANISH_LOCATION_TERMS = (
    "madrid",
    "parla",
    "illescas",
    "barcelona",
    "valencia",
    "sevilla",
    "seville",
    "zaragoza",
    "málaga",
    "malaga",
    "bilbao",
    "a coruña",
    "coruña",
    "santiago de compostela",
    "ourense",
    "lugo",
    "valladolid",
    "salamanca",
    "alicante",
    "murcia",
    "gijón",
    "gijon",
    "oviedo",
    "santander",
    "pamplona",
)

_SOURCE_FIRST_SPECIALIST_REQUIREMENTS = (
    ("AMOS", ("amos",)),
    ("SunView", ("sunview",)),
    ("ChangeGear", ("changegear",)),
    (
        "SailPoint IdentityIQ",
        ("sailpoint identityiq", "identityiq", "sailpoint iiq"),
    ),
    (
        "BMC Helix ITSM",
        ("bmc helix itsm", "bmc helix", "helix itsm"),
    ),
    (
        "BizTalk",
        ("microsoft biztalk", "biztalk server", "biztalk"),
    ),
    (
        "Zendesk",
        ("zendesk administrator", "zendesk administration", "zendesk"),
    ),
    (
        "Microsoft Dynamics Customer Service",
        (
            "microsoft dynamics customer service",
            "dynamics customer service",
        ),
    ),
)

_SOURCE_FIRST_EXCLUDED_TITLE_PATTERNS = (
    (r"\b(?:staff|senior|lead)?\s*data\s+engineer\b", "Data / ML engineering"),
    (r"\b(?:senior|lead)?\s*data\s+scientist\b", "Data science"),
    (r"\b(?:senior|lead)?\s*data\s+analyst\b", "Data analysis"),
    (
        r"\bdata\s+(?:annotator|annotation|labeler|labeller|labeling|labelling)\b",
        "Data annotation",
    ),
    (
        r"\bdata\s+governance\s+(?:lead|manager|specialist)\b",
        "Data governance",
    ),
    (r"\bdataops\b", "Data / AI engineering"),
    (r"\bdata\s+ops\s+engineer\b", "Data / AI engineering"),
    (r"\bingenier[oa]\s+de\s+datos\b", "Data / ML engineering"),
    (r"\bdata\s+science\s+specialist\b", "Data science"),
    (
        r"\b(?:senior\s+)?solutions?\s+architect\b.{0,80}"
        r"\bdata\s*(?:&|and)\s*ai\b|"
        r"\bdata\s*(?:&|and)\s*ai\b.{0,80}"
        r"\b(?:senior\s+)?solutions?\s+architect\b",
        "Data / AI architecture",
    ),
    (r"\bsap\s+abap\s+developer\b", "Software development"),
    (r"\b(?:backend|back-end)\s+developer\b", "Software development"),
    (r"\bprogramador(?:a)?\b", "Software development"),
    (r"\bproject\s+(?:manager|planner)\b", "Pure project management"),
    (r"\bproduct\s+(?:manager|director)\b", "Pure product management"),
    (r"\btransition\s+manager\b", "Pure project management"),
    (r"\bit\s+market\s+lead\b", "IT business / project leadership"),
    (
        r"\b(?:buyer|procurement\s+manager|category\s+manager)\b",
        "Procurement",
    ),
    (r"\bsales\s+manager\b", "Sales"),
)

_SOURCE_FIRST_PRESENCE_PATTERNS = (
    r"\bhybrid\s+(?:role|position|work|working|model|schedule|arrangement)\b",
    r"\b(?:role|position|work|working|model|schedule|arrangement)"
    r"\s+(?:is\s+)?hybrid\b",
    r"\b(?:puesto|trabajo|modalidad)\s+h[ií]brid[oa]\b",
    r"\bh[ií]brid[oa]\s+(?:puesto|trabajo|modalidad)\b",
    r"\bon[-\s]?site\b",
    r"\bonsite\b",
    r"\bpresencial(?:idad|mente)?\b",
    r"\boffice\s+attendance\b",
    r"\battendance\s+(?:at|in|to)\s+(?:the\s+)?office\b",
    r"\b(?:work|working)\s+(?:from|at|in)\s+(?:the\s+)?office\b",
    r"\bclient\s+site\b",
    r"\bcustomer\s+sites?\b",
    r"\btravel\s+to\s+(?:customer|client)\s+sites?\b",
    r"\bon[-\s]?site\s+installations?\b",
    r"\b(?:first|initial)\s+\d+\s+weeks?.{0,60}\boffice\b",
    r"\b\d+\s+days?\s+(?:per|a)\s+week.{0,60}\b(?:office|client|customer)\b",
    r"\b\d+\s*-\s*\d+\s+(?:times?|days?)\s+(?:per|a)\s+month\b",
    r"\b\d+\s*-\s*\d+\s+(?:veces|d[ií]as)\s+al\s+mes\b",
    r"\b\d+\s+d[ií]as?\s+en\s+(?:cliente|oficinas?|presencial)\b",
    r"\b(?:primeras?|iniciales?)\s+\d+\s+semanas?.{0,100}"
    r"\b(?:oficinas?|presencial|situad[oa])\b",
    r"\bdisponibilidad\s+para\s+asistir.{0,100}\boficinas?\b",
)

_SOURCE_FIRST_LOCALITY_RESTRICTION_PATTERNS = (
    r"\bonly\s+(?:candidates|applicants).{0,100}"
    r"(?:from|based\s+in|located\s+in|living\s+in|near)\b",
    r"\b(?:candidates|applicants)\s+must.{0,80}"
    r"(?:be\s+)?(?:based|located|resident)\s+(?:in|near)\b",
    r"\bonly\s+consider(?:ing|ed)?.{0,60}"
    r"(?:candidates|applicants).{0,80}(?:from|in|near)\b",
    r"\bsolo\s+se\s+valorar[aá]n\s+candidaturas?.{0,80}\bde\b",
    r"\bsolo\s+se\s+considerar[aá]n\s+candidaturas?.{0,80}\bde\b",
)

_SOURCE_FIRST_DOMAIN_DEGREE_PATTERNS = (
    r"\bminimum\s+(?:bs|bsc|bachelor(?:'s)?(?:\s+degree)?)"
    r"(?:\s+or\s+equivalent)?\s*,?\s+in\s+[^.\n]{3,180}",
    r"\b(?:bachelor(?:'s)?|university)\s+degree\s+"
    r"(?:is\s+)?(?:required|mandatory)\s+in\s+[^.\n]{3,180}",
    r"\bdegree\s+in\s+[^.\n]{3,180}\s+(?:is\s+)?(?:required|mandatory)\b",
)

_SOURCE_FIRST_CLEARANCE_PATTERNS = (
    r"\bhps\s+(?:security\s+)?clearance\b",
    r"\b(?:security\s+)?clearance\s+(?:is\s+)?required\b",
    r"\brequired\s+(?:security\s+)?clearance\b",
    r"\bhabilitaci[oó]n\s+personal\s+de\s+seguridad\s+hps\b",
    r"\bhps\b.{0,80}\b(?:tramitaci[oó]n|vigente|antes\s+de\s+incorporaci[oó]n)\b",
)

_FOREIGN_RESIDENCE_PATTERN = (
    "(?:" + "|".join(re.escape(location) for location in FOREIGN_COUNTRY_TERMS) + ")"
)

_EXPLICIT_FOREIGN_RESIDENCE_PATTERNS = (
    rf"\bmust\s+(?:already\s+)?(?:live|reside|be based)\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bonly\s+(?:open|available)\s+to\s+(?:candidates|applicants)\s+"
    rf"(?:living|resident|based)\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\brequires?\s+(?:current\s+)?(?:residence|residency)\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bwork\s+authori[sz]ation\s+(?:is\s+)?required\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bright\s+to\s+work\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\b(?:must|required\s+to)\s+(?:already\s+)?(?:be\s+)?"
    rf"(?:legally\s+)?authori[sz]ed\s+to\s+work\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\b(?:must|required\s+to)\s+(?:already\s+)?(?:be\s+)?"
    rf"(?:legally\s+)?eligible\s+to\s+work\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\b(?:candidates|applicants|employees)\s+must\s+(?:already\s+)?"
    rf"(?:be\s+)?(?:legally\s+)?authori[sz]ed\s+to\s+work\s+in\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bremote\s+(?:only\s+)?within\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bremote\s+from\s+(?:the\s+)?"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
)

_EXPLICIT_PEOPLE_MANAGEMENT_PATTERNS = (
    r"\bmanage(?:s|d|ment|ing)?\s+(?:a|the|our)?\s*team\b",
    r"\blead(?:s|ing)?\s+(?:a|the|our)?\s*team\b",
    r"\bteam\s+of\s+\d+\b",
    r"\bdirect\s+reports?\b",
    r"\bline\s+management\b",
    r"\bpeople\s+manager\b",
    r"\bstaff\s+management\b",
    r"\bpersonnel\s+management\b",
    r"\bperformance\s+reviews?\b",
    r"\b(?:hire|hiring),?\s+(?:coach|coaching|develop|developing)\b",
    r"\bcoach(?:ing)?\s+(?:and\s+mentor(?:ing)?\s+)?(?:a|the|our)?\s*team\b",
)


def _source_first_normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _source_first_term_pattern(term: str) -> re.Pattern[str]:
    normalized = _source_first_normalize(term)
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)")


def _source_first_window(
    text: str,
    start: int,
    end: int,
    *,
    radius: int = 120,
) -> str:
    return text[max(0, start - radius) : min(len(text), end + radius)]


def _source_first_preferred(window: str, alias: str) -> bool:
    marker = (
        r"preferred|nice\s+to\s+have|advantage|a\s+plus|"
        r"desirable|optional|valorable|deseable"
    )
    escaped = re.escape(alias)
    return bool(
        re.search(
            rf"\b{escaped}\b.{{0,55}}\b(?:{marker})\b|"
            rf"\b(?:{marker})\b.{{0,45}}\b{escaped}\b",
            window,
        )
    )


def _source_first_alias_required(text: str, alias: str) -> bool:
    normalized = _source_first_normalize(text)
    pattern = _source_first_term_pattern(alias)

    mandatory = (
        r"required|mandatory|essential|must\s+have|"
        r"requisito\s+imprescindible|requisitos\s+imprescindibles|"
        r"experiencia\s+imprescindible"
    )

    experience = (
        r"hands[-\s]?on\s+experience|proven\s+experience|"
        r"demonstrable\s+experience|solid\s+experience|"
        r"professional\s+experience|experiencia\s+profesional|"
        r"experiencia\s+demostrable"
    )

    for match in pattern.finditer(normalized):
        window = _source_first_window(
            normalized,
            match.start(),
            match.end(),
        )

        if _source_first_preferred(window, alias):
            continue

        escaped = re.escape(alias)

        checks = (
            rf"\b(?:{mandatory})\b.{{0,90}}\b{escaped}\b",
            rf"\b{escaped}\b.{{0,90}}\b(?:{mandatory})\b",
            rf"\b(?:{experience})\b.{{0,80}}\b{escaped}\b",
            rf"\b(?:minimum|at\s+least)\s+\d+\+?\s+years?"
            rf".{{0,90}}\b{escaped}\b",
            rf"\b\d+\+?\s+years?.{{0,80}}\b{escaped}\b",
        )

        if any(re.search(check, window) for check in checks):
            return True

    return False


def _source_first_profile_has_evidence(
    profile: StrategyProfile,
    aliases: tuple[str, ...],
) -> bool:
    for capability in profile.capabilities:
        if capability.evidence_level <= 0:
            continue

        text = _source_first_normalize(
            "\n".join(
                (
                    capability.id,
                    capability.label,
                    *capability.terms,
                )
            )
        )

        if any(_source_first_term_pattern(alias).search(text) for alias in aliases):
            return True

    return False


def _source_first_missing_platforms(
    profile: StrategyProfile,
    text: str,
) -> tuple[str, ...]:
    missing: list[str] = []

    for label, aliases in _SOURCE_FIRST_SPECIALIST_REQUIREMENTS:
        if _source_first_profile_has_evidence(profile, aliases):
            continue

        if any(_source_first_alias_required(text, alias) for alias in aliases):
            missing.append(label)

    return tuple(dict.fromkeys(missing))


def _source_first_excluded_title(title: str) -> str | None:
    normalized = _source_first_normalize(title)

    for pattern, label in _SOURCE_FIRST_EXCLUDED_TITLE_PATTERNS:
        if re.search(pattern, normalized):
            return label

    return None


def _source_first_distant_presence(text: str) -> str | None:
    normalized = _source_first_normalize(text)

    for place in _CLEARLY_DISTANT_SPANISH_LOCATION_TERMS:
        place_pattern = _source_first_term_pattern(place)

        for match in place_pattern.finditer(normalized):
            window = _source_first_window(
                normalized,
                match.start(),
                match.end(),
                radius=180,
            )

            if any(re.search(pattern, window) for pattern in _SOURCE_FIRST_PRESENCE_PATTERNS):
                return place

    return None


def _source_first_distant_locality(text: str) -> str | None:
    normalized = _source_first_normalize(text)

    for place in _CLEARLY_DISTANT_SPANISH_LOCATION_TERMS:
        place_pattern = _source_first_term_pattern(place)

        for match in place_pattern.finditer(normalized):
            window = _source_first_window(
                normalized,
                match.start(),
                match.end(),
                radius=180,
            )

            if any(
                re.search(pattern, window)
                for pattern in _SOURCE_FIRST_LOCALITY_RESTRICTION_PATTERNS
            ):
                return place

    return None


def _source_first_domain_degree(text: str) -> str | None:
    normalized = _source_first_normalize(text)

    for pattern in _SOURCE_FIRST_DOMAIN_DEGREE_PATTERNS:
        match = re.search(pattern, normalized)
        if match is not None:
            return match.group(0)

    return None


def _source_first_clearance(text: str) -> str | None:
    normalized = _source_first_normalize(text)

    for pattern in _SOURCE_FIRST_CLEARANCE_PATTERNS:
        match = re.search(pattern, normalized)
        if match is not None:
            return match.group(0)

    return None


def _source_first_large_experience(text: str) -> str | None:
    normalized = _source_first_normalize(text)

    pattern = re.compile(
        r"\b(?:(?:minimum|at\s+least)\s+)?"
        r"(?P<years>\d+)\+?\s+years?\s+"
        r"(?:"
        r"(?:of\s+)?(?:professional\s+)?experience\b"
        r"|"
        r"(?:running|operating|administering|managing|supporting)\b"
        r"|"
        r"working\s+(?:with|in|on)\b"
        r")"
        r"[^.\n]{0,150}"
    )

    requirement_markers = (
        "minimum",
        "at least",
        "required",
        "requirement",
        "requirements",
        "must have",
        "must-have",
        "you have",
        "you bring",
        "candidate",
        "qualifications",
        "we are looking for",
        "we're looking for",
        "seeking",
    )

    organizational_history_markers = (
        "company has",
        "company with",
        "organisation has",
        "organization has",
        "organisation with",
        "organization with",
        "we have over",
        "we have more than",
        "with over",
        "with more than",
        "more than",
        "over",
        "founded",
        "established",
        "delivering services worldwide",
        "serving customers",
    )

    for match in pattern.finditer(normalized):
        years = int(match.group("years"))

        if years < 4:
            continue

        # Job requirements above twenty years are implausible enough that
        # they are substantially more likely to describe company history.
        if years > 20:
            continue

        before = normalized[max(0, match.start() - 100) : match.start()]
        window = _source_first_window(
            normalized,
            match.start(),
            match.end(),
            radius=60,
        )

        if any(
            marker in window
            for marker in (
                "preferred",
                "nice to have",
                "advantage",
                "desirable",
            )
        ):
            continue

        explicit_requirement = any(marker in before for marker in requirement_markers)

        organizational_history = any(marker in before for marker in organizational_history_markers)

        if organizational_history and not explicit_requirement:
            continue

        return match.group(0)

    return None


def _apply_source_first_requirement_gate(
    assessment: StrategyAssessment,
    profile: StrategyProfile,
    *,
    title: str,
    location: str,
    description: str,
) -> StrategyAssessment:
    text = "\n".join((title, location, description))

    excluded = _source_first_excluded_title(title)

    if excluded is not None:
        return replace(
            assessment,
            recommendation="do_not_pursue",
            confidence="high",
            fit_now=0,
            fit_by_interview=0,
            fit_on_the_job=0,
            blockers=tuple(
                dict.fromkeys(
                    [
                        *assessment.blockers,
                        (f"Source-first career scope: excluded role family {excluded}."),
                    ]
                )
            ),
        )

    place = _source_first_distant_presence(text) or _source_first_distant_locality(text)

    if place is not None:
        preferences = load_job_search_preferences()

        return replace(
            assessment,
            eligibility="ineligible",
            recommendation="do_not_pursue",
            confidence="high",
            fit_now=0,
            fit_by_interview=0,
            fit_on_the_job=0,
            blockers=tuple(
                dict.fromkeys(
                    [
                        *assessment.blockers,
                        (
                            "Source-first location eligibility: "
                            f"required presence/locality around {place} "
                            "is outside the configured "
                            f"{preferences.max_hybrid_distance_km} km "
                            f"radius from {preferences.base_locality}."
                        ),
                    ]
                )
            ),
        )

    clearance = _source_first_clearance(text)

    if clearance is not None:
        return replace(
            assessment,
            eligibility="ineligible",
            recommendation="do_not_pursue",
            confidence="high",
            fit_now=0,
            fit_by_interview=0,
            fit_on_the_job=0,
            blockers=tuple(
                dict.fromkeys(
                    [
                        *assessment.blockers,
                        (
                            "Source-first mandatory requirement: "
                            f"clearance not evidenced: {clearance}."
                        ),
                    ]
                )
            ),
        )

    platforms = _source_first_missing_platforms(profile, text)

    if platforms:
        return replace(
            assessment,
            eligibility="ineligible",
            recommendation="do_not_pursue",
            confidence="high",
            fit_now=0,
            fit_by_interview=0,
            fit_on_the_job=0,
            blockers=tuple(
                dict.fromkeys(
                    [
                        *assessment.blockers,
                        *(
                            "Source-first mandatory specialist requirement: "
                            f"{platform} experience is required "
                            "but not evidenced."
                            for platform in platforms
                        ),
                    ]
                )
            ),
        )

    unresolved: list[str] = []

    degree = _source_first_domain_degree(text)
    if degree is not None:
        unresolved.append("domain-specific education requirement: " + degree)

    experience = _source_first_large_experience(text)
    if experience is not None:
        unresolved.append("high-seniority experience requirement: " + experience)

    if not unresolved:
        return assessment

    requirement_uncertainties = tuple(
        "Source-first mandatory requirement must be verified before pursuit: " + item
        for item in unresolved
    )

    # Requirement reconciliation is monotonic. A later conditional
    # requirement may strengthen an otherwise eligible assessment, but
    # it must never weaken an earlier hard rejection.
    if assessment.eligibility == "ineligible" or assessment.recommendation == "do_not_pursue":
        return replace(
            assessment,
            uncertainties=tuple(
                dict.fromkeys(
                    [
                        *assessment.uncertainties,
                        *requirement_uncertainties,
                    ]
                )
            ),
        )

    return replace(
        assessment,
        eligibility="eligible_with_conditions",
        recommendation="pursue_if_condition_met",
        confidence="low",
        fit_now=min(assessment.fit_now, 69),
        fit_by_interview=min(assessment.fit_by_interview, 69),
        fit_on_the_job=min(assessment.fit_on_the_job, 74),
        uncertainties=tuple(
            dict.fromkeys(
                [
                    *assessment.uncertainties,
                    *requirement_uncertainties,
                ]
            )
        ),
    )


def load_active_strategy_profile(path: Path | None = None) -> StrategyProfile | None:
    profile_path = path or default_profile_path()
    if not profile_path.is_file():
        return None
    return load_strategy_profile(profile_path)


def profile_fingerprint(profile: StrategyProfile) -> str:
    canonical = json.dumps(
        profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def preferences_fingerprint() -> str:
    preferences = load_job_search_preferences()
    canonical = preferences.model_dump_json(exclude_none=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def public_profile_metadata(profile: StrategyProfile) -> dict[str, object]:
    return {
        "schema_version": profile.schema_version,
        "profile_id": profile.profile_id,
        "version": profile.version,
        "profile_sha256": profile_fingerprint(profile),
        "private_configuration_stored": False,
    }


def assessment_payload(assessment: StrategyAssessment) -> dict[str, object]:
    return asdict(assessment)


def assessment_reasons(assessment: StrategyAssessment) -> list[str]:
    reasons = [
        f"Eligibility: {assessment.eligibility}.",
        f"Recommendation: {assessment.recommendation}.",
        (
            "Fit: "
            f"now {assessment.fit_now}, "
            f"by interview {assessment.fit_by_interview}, "
            f"on the job {assessment.fit_on_the_job}."
        ),
        (
            f"Interview preparation window: {assessment.interview_days} days; "
            f"estimated preparation {assessment.estimated_preparation_hours} hours."
        ),
        f"Job-search preferences SHA256: {preferences_fingerprint()}.",
    ]
    reasons.extend(f"Strength: {item}" for item in assessment.strengths)
    reasons.extend(f"Blocker: {item}" for item in assessment.blockers)
    reasons.extend(f"Uncertainty: {item}" for item in assessment.uncertainties)
    reasons.append(
        "Strategy assessment JSON: " + json.dumps(assessment_payload(assessment), sort_keys=True)
    )
    return reasons


def proposed_decision(assessment: StrategyAssessment) -> str:
    return {
        "strong_pursue": "pursue",
        "pursue": "pursue",
        "pursue_if_condition_met": "consider",
        "review_manually": "needs_more_information",
        "defer": "consider",
        "do_not_pursue": "reject",
    }[assessment.recommendation]


def ensure_private_profile_version(session: Session, profile: StrategyProfile) -> ProfileVersion:
    expected_metadata = public_profile_metadata(profile)
    existing = session.get(ProfileVersion, profile.version_id)
    if existing is not None:
        stored_metadata = json.loads(existing.configuration_json)
        if stored_metadata.get("profile_sha256") != expected_metadata["profile_sha256"]:
            raise ValueError(
                "Private strategy profile content changed without a version increment. "
                "Increase the profile version before recalculating evaluations."
            )
        return existing
    record = ProfileVersion(
        id=profile.version_id,
        profile_id=profile.profile_id,
        version=profile.version,
        configuration_json=json.dumps(expected_metadata, sort_keys=True),
        created_at=utc_now(),
    )
    session.add(record)
    session.flush()
    return record


def _has_explicit_people_management_requirement(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return any(re.search(pattern, normalized) for pattern in _EXPLICIT_PEOPLE_MANAGEMENT_PATTERNS)


def _remove_unsubstantiated_people_management_gap(
    assessment: StrategyAssessment,
    *,
    title: str,
    location: str,
    description: str,
) -> StrategyAssessment:
    text = "\n".join((title, location, description))
    if _has_explicit_people_management_requirement(text):
        return assessment

    removed_gaps = tuple(
        gap for gap in assessment.gaps if gap.label.casefold() == _PEOPLE_MANAGEMENT_LABEL
    )
    if not removed_gaps:
        return assessment

    removed_topics = {
        topic for gap in removed_gaps for topic in gap.preparation_topics if topic.strip()
    }
    return replace(
        assessment,
        strengths=tuple(
            strength
            for strength in assessment.strengths
            if not strength.casefold().startswith(_PEOPLE_MANAGEMENT_LABEL)
        ),
        gaps=tuple(
            gap for gap in assessment.gaps if gap.label.casefold() != _PEOPLE_MANAGEMENT_LABEL
        ),
        preparation_plan=tuple(
            topic for topic in assessment.preparation_plan if topic not in removed_topics
        ),
    )


def _normalized_location_scope(location: str) -> str:
    return normalized_location_scope(location)


def _has_explicit_foreign_residence_requirement(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return any(re.search(pattern, normalized) for pattern in _EXPLICIT_FOREIGN_RESIDENCE_PATTERNS)


def _explicit_work_mode(text: str) -> str | None:
    lowered = text.casefold()

    matches = {
        mode
        for mode, patterns in (
            ("remote", _EXPLICIT_REMOTE_WORK_PATTERNS),
            ("hybrid", _EXPLICIT_HYBRID_WORK_PATTERNS),
            ("onsite", _EXPLICIT_ONSITE_WORK_PATTERNS),
        )
        if any(re.search(pattern, lowered) for pattern in patterns)
    }

    if not matches:
        return None
    if len(matches) > 1:
        return "conflict"
    return next(iter(matches))


def _location_contains_term(location: str, terms: tuple[str, ...]) -> bool:
    normalized = " ".join(location.casefold().split())
    return any(re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized) for term in terms)


def _has_explicit_spain_geography(text: str) -> bool:
    normalized = " ".join(text.casefold().split())

    negative_patterns = (
        r"\b(?:candidates|applicants|employees)\s+"
        r"(?:based|located|resident)?\s*(?:in|from)?\s*spain\s+"
        r"(?:are|may be|can be)?\s*not\s+"
        r"(?:eligible|accepted|considered|hired|permitted)\b",
        r"\b(?:candidates|applicants|employees)\s+"
        r"(?:based|located|resident)?\s*(?:in|from)?\s*spain\s+"
        r"(?:are not|aren't)\s+"
        r"(?:eligible|accepted|considered|hired|permitted)\b",
        r"\b(?:cannot|can't|may not|must not)\s+"
        r"work(?:\s+remotely)?\s+from\s+spain\b",
        r"\bspain\s+(?:is\s+)?(?:not|isn't)\s+"
        r"(?:eligible|supported|available|permitted|allowed)\b",
        r"\b(?:no|without)\s+"
        r"(?:hiring|employment|contracting)\s+in\s+spain\b",
        r"\b(?:exclude|excluding|excluded)\s+"
        r"(?:candidates|applicants|employees|residents)?\s*"
        r"(?:from|in)?\s*spain\b",
    )

    if any(re.search(pattern, normalized) for pattern in negative_patterns):
        return False

    return any(
        re.search(pattern, normalized)
        for pattern in (
            r"(?<!\w)spain(?!\w)",
            r"(?<!\w)españa(?!\w)",
            r"(?<!\w)espana(?!\w)",
        )
    )


_LEGACY_LOCAL_WORK_MODE_UNCERTAINTY_PREFIX = "Onsite or hybrid work requires confirmation "
_LEGACY_REMOTE_WORK_UNCERTAINTY_PREFIX = "Remote work is suitable when the employer can contract "


def _remove_legacy_local_work_mode_uncertainty(
    assessment: StrategyAssessment,
) -> StrategyAssessment:
    retained = tuple(
        uncertainty
        for uncertainty in assessment.uncertainties
        if not uncertainty.startswith(_LEGACY_LOCAL_WORK_MODE_UNCERTAINTY_PREFIX)
    )

    if retained == assessment.uncertainties:
        return assessment

    eligibility = assessment.eligibility

    if (
        eligibility in {"uncertain", "eligible_with_conditions"}
        and not retained
        and not assessment.blockers
    ):
        eligibility = "eligible"

    return replace(
        assessment,
        eligibility=eligibility,
        uncertainties=retained,
    )


def _remove_legacy_remote_work_uncertainty(
    assessment: StrategyAssessment,
) -> StrategyAssessment:
    retained = tuple(
        uncertainty
        for uncertainty in assessment.uncertainties
        if not uncertainty.startswith(_LEGACY_REMOTE_WORK_UNCERTAINTY_PREFIX)
    )

    if retained == assessment.uncertainties:
        return assessment

    eligibility = assessment.eligibility

    if (
        eligibility in {"uncertain", "eligible_with_conditions"}
        and not retained
        and not assessment.blockers
    ):
        eligibility = "eligible"

    return replace(
        assessment,
        eligibility=eligibility,
        uncertainties=retained,
    )


def _apply_local_work_mode_eligibility(
    assessment: StrategyAssessment,
    *,
    title: str,
    location: str,
    description: str,
) -> StrategyAssessment:
    if assessment.eligibility == "ineligible":
        return assessment

    preferences = load_job_search_preferences()
    evidence_text = "\n".join((title, location, description))
    work_mode = _explicit_work_mode(evidence_text)

    if work_mode is None or work_mode == "remote":
        return assessment

    if work_mode == "conflict":
        uncertainties = tuple(
            dict.fromkeys(
                [
                    *assessment.uncertainties,
                    (
                        "Work-mode eligibility: conflicting explicit remote and "
                        "hybrid/onsite evidence requires manual verification."
                    ),
                ]
            )
        )
        return replace(
            assessment,
            eligibility="eligible_with_conditions",
            recommendation="pursue_if_condition_met",
            confidence="low",
            uncertainties=uncertainties,
        )

    if _location_contains_term(location, _VIGO_LOCAL_LOCATION_TERMS):
        return assessment

    scope = _normalized_location_scope(location)
    clearly_distant = _location_contains_term(
        location,
        _CLEARLY_DISTANT_SPANISH_LOCATION_TERMS,
    )
    explicit_spain_option = _has_explicit_spain_geography(title)

    if clearly_distant or (scope == "foreign_country" and not explicit_spain_option):
        blockers = tuple(
            dict.fromkeys(
                [
                    *assessment.blockers,
                    (
                        f"Location eligibility: explicit {work_mode} work is advertised "
                        f"from {location or 'a non-local location'}, outside the configured "
                        f"{preferences.max_hybrid_distance_km} km local radius from "
                        f"{preferences.base_locality}."
                    ),
                ]
            )
        )
        return replace(
            assessment,
            eligibility="ineligible",
            recommendation="do_not_pursue",
            confidence="high",
            blockers=blockers,
        )

    if (
        scope == "spain"
        or not location.strip()
        or (scope == "foreign_country" and explicit_spain_option)
    ):
        uncertainties = tuple(
            dict.fromkeys(
                [
                    *assessment.uncertainties,
                    (
                        f"Location eligibility: explicit {work_mode} work requires "
                        f"verification that the workplace is within the configured "
                        f"{preferences.max_hybrid_distance_km} km radius from "
                        f"{preferences.base_locality}."
                    ),
                ]
            )
        )
        return replace(
            assessment,
            eligibility="eligible_with_conditions",
            recommendation="pursue_if_condition_met",
            confidence="low",
            uncertainties=uncertainties,
        )

    return assessment


def _has_explicit_cross_border_eligibility(text: str) -> bool:
    normalized = " ".join(text.casefold().split())

    # Negative statements take precedence over positive-looking wording.
    negative_patterns = (
        r"\b(?:candidates|applicants)\s+(?:based|located|resident)\s+in\s+spain"
        r"\s+(?:are|may be|can be)\s+not\s+(?:eligible|accepted|considered|hired)\b",
        r"\b(?:candidates|applicants)\s+(?:based|located|resident)\s+in\s+spain"
        r"\s+(?:are not|aren't)\s+(?:eligible|accepted|considered|hired)\b",
        r"\b(?:cannot|can't|may not|must not)\s+work(?:\s+remotely)?\s+from\s+spain\b",
        r"\bspain\s+(?:is\s+)?(?:not|isn't)\s+"
        r"(?:eligible|supported|available|permitted|allowed)\b",
        r"\b(?:no|without)\s+(?:hiring|employment|contracting)\s+in\s+spain\b",
        r"\b(?:exclude|excluding|excluded)\s+"
        r"(?:candidates|applicants|residents)?\s*(?:from|in)?\s*spain\b",
    )

    if any(re.search(pattern, normalized) for pattern in negative_patterns):
        return False

    positive_patterns = (
        r"\bremote\s+(?:worldwide|globally|internationally)\b",
        r"\bwork\s+from\s+anywhere\b(?!\s+(?:in|within|across)\b)",
        r"\b(?:available|open)\s+(?:across|throughout|within)\s+"
        r"(?:emea|europe|the european union|eu)\b",
        r"\b(?:eu|europe|emea)[-\s]?based\s*(?=,|;|\.|$)",
        r"\b(?:candidate|applicant|employee|you)\s+"
        r"(?:must\s+be\s+|are\s+)?(?:eu|europe|emea)[-\s]?based\b",
        r"\b(?:candidate|applicant|employee|you)\s+"
        r"(?:must\s+be\s+|are\s+)?based\s+in\s+"
        r"(?:the\s+)?(?:eu|europe|emea)\b",
        r"\b(?:candidates|applicants)\s+(?:based|located|resident)\s+in\s+spain"
        r"\s+(?:(?:are|may be|can be)\s+"
        r"(?:eligible|accepted|considered|hired)"
        r"|(?:may|can)\s+work(?:\s+remotely)?)\b",
        r"\b(?:may|can|are permitted to|are allowed to)\s+"
        r"(?:work|work remotely)\s+from\s+spain\b",
        r"\b(?:hiring|hire|employment)\s+(?:is\s+)?"
        r"(?:available|supported|permitted)\s+in\s+spain\b",
        r"\binternational\s+(?:b2b|contractor|contracting)\s+"
        r"(?:is\s+)?(?:supported|available|permitted|accepted)\b",
    )

    return any(re.search(pattern, normalized) for pattern in positive_patterns)


def _apply_location_eligibility(
    assessment: StrategyAssessment,
    *,
    title: str,
    location: str,
    description: str,
) -> StrategyAssessment:
    if assessment.eligibility == "ineligible":
        return assessment

    combined_text = "\n".join((title, location, description))
    scope = _normalized_location_scope(location)

    if _has_explicit_foreign_residence_requirement(combined_text):
        blockers = tuple(
            dict.fromkeys(
                [
                    *assessment.blockers,
                    (
                        "Location eligibility: the vacancy explicitly requires "
                        "residence or work authorization outside Spain."
                    ),
                ]
            )
        )
        return replace(
            assessment,
            eligibility="ineligible",
            recommendation="do_not_pursue",
            confidence="high",
            blockers=blockers,
        )

    explicit_spain_option = _has_explicit_spain_geography(title)
    explicit_cross_border = _has_explicit_cross_border_eligibility(combined_text)

    if scope == "foreign_country":
        if explicit_spain_option or explicit_cross_border:
            return _remove_legacy_remote_work_uncertainty(assessment)

        blockers = tuple(
            dict.fromkeys(
                [
                    *assessment.blockers,
                    (
                        "Location eligibility: the vacancy is explicitly tied to "
                        f"{location or 'another specific country'}, and the posting "
                        "does not establish that employment from Spain is permitted."
                    ),
                ]
            )
        )
        return replace(
            assessment,
            eligibility="ineligible",
            recommendation="do_not_pursue",
            confidence="high",
            blockers=blockers,
        )

    if scope == "spain" or explicit_cross_border:
        assessment = _remove_legacy_remote_work_uncertainty(assessment)

    normalized_location = " ".join(location.casefold().split())
    explicit_remote = (
        normalized_location in {"remote", "fully remote", "100% remote"}
        or _explicit_work_mode(combined_text) == "remote"
    )

    if scope == "unknown" and explicit_remote:
        uncertainties = tuple(
            dict.fromkeys(
                [
                    *assessment.uncertainties,
                    (
                        "Location eligibility: the vacancy is remote but does not "
                        "state an employment geography or explicitly confirm that "
                        "employment from Spain is permitted."
                    ),
                ]
            )
        )
        return replace(
            assessment,
            eligibility="eligible_with_conditions",
            recommendation="pursue_if_condition_met",
            confidence="low",
            uncertainties=uncertainties,
        )

    return assessment


def _apply_saved_preferences(
    assessment: StrategyAssessment,
    *,
    title: str,
    location: str,
    description: str,
) -> StrategyAssessment:
    text = "\n".join((title, location, description))
    configured_blockers = preference_blockers(text)
    if not configured_blockers:
        return assessment
    blockers = tuple(
        dict.fromkeys(
            [
                *assessment.blockers,
                *(f"Job-search preference: {item}." for item in configured_blockers),
            ]
        )
    )
    return replace(
        assessment,
        eligibility="ineligible",
        recommendation="do_not_pursue",
        confidence="high",
        blockers=blockers,
    )


def _actionable_ranking_score(assessment: StrategyAssessment) -> int:
    """Convert technical fit into a score suitable for an actionable queue."""
    if assessment.eligibility == "ineligible" or assessment.recommendation == "do_not_pursue":
        return 0
    if assessment.eligibility == "uncertain":
        return min(assessment.fit_now, 49)
    if assessment.eligibility == "eligible_with_conditions":
        return min(assessment.fit_by_interview, 79)
    return assessment.fit_by_interview


def _calibrate_interview_uplift(assessment: StrategyAssessment) -> StrategyAssessment:
    """Prevent short preparation plans from producing unrealistic score jumps."""
    capped_interview = min(assessment.fit_by_interview, assessment.fit_now + 10)
    recommendation = assessment.recommendation
    confidence = assessment.confidence

    if recommendation == "do_not_pursue":
        return replace(
            assessment,
            fit_by_interview=capped_interview,
        )

    if assessment.eligibility in {"uncertain", "eligible_with_conditions"}:
        recommendation = "pursue_if_condition_met"
        confidence = "low"
    elif recommendation == "strong_pursue" and capped_interview < 80:
        recommendation = "pursue"

    return replace(
        assessment,
        fit_by_interview=capped_interview,
        recommendation=recommendation,
        confidence=confidence,
    )


def calibrated_strategy_assessment(
    profile: StrategyProfile,
    *,
    title: str,
    location: str,
    description: str,
) -> StrategyAssessment:
    sanitized_description = sanitize_capture_text(description)
    assessment = assess_posting(profile, title, location, sanitized_description)
    assessment = _remove_unsubstantiated_people_management_gap(
        assessment,
        title=title,
        location=location,
        description=sanitized_description,
    )
    assessment = _remove_legacy_local_work_mode_uncertainty(
        assessment,
    )
    assessment = _apply_saved_preferences(
        assessment,
        title=title,
        location=location,
        description=sanitized_description,
    )
    assessment = _apply_local_work_mode_eligibility(
        assessment,
        title=title,
        location=location,
        description=sanitized_description,
    )
    assessment = _apply_location_eligibility(
        assessment,
        title=title,
        location=location,
        description=sanitized_description,
    )
    assessment = _apply_source_first_requirement_gate(
        assessment,
        profile,
        title=title,
        location=location,
        description=sanitized_description,
    )
    return _calibrate_interview_uplift(assessment)


def ensure_strategy_review(
    session: Session,
    profile: StrategyProfile,
    posting: Posting,
    *,
    commit: bool = True,
) -> StrategyAssessment:
    """Assess one posting and append a new evaluation only when the result changed."""
    profile_record = ensure_private_profile_version(session, profile)
    assessment = calibrated_strategy_assessment(
        profile,
        title=posting.title,
        location=posting.location,
        description=posting.description,
    )
    reasons = assessment_reasons(assessment)
    reasons_json = json.dumps(reasons)
    existing = session.scalar(
        select(Evaluation)
        .where(
            Evaluation.posting_id == posting.id,
            Evaluation.profile_version_id == profile_record.id,
            Evaluation.engine_version == ENGINE_VERSION,
        )
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    )
    latest_any = session.scalar(
        select(Evaluation)
        .where(Evaluation.posting_id == posting.id)
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    )
    unchanged = bool(
        existing
        and existing.recommendation == assessment.recommendation
        and existing.confidence == assessment.confidence
        and existing.ranking_score == _actionable_ranking_score(assessment)
        and existing.reasons_json == reasons_json
    )
    current_is_latest = bool(existing and latest_any and existing.id == latest_any.id)
    if not unchanged or not current_is_latest:
        created_at = utc_now()
        if latest_any is not None:
            latest_created_at = latest_any.created_at
            if latest_created_at.tzinfo is None:
                latest_created_at = latest_created_at.replace(tzinfo=UTC)
            else:
                latest_created_at = latest_created_at.astimezone(UTC)

            if latest_created_at >= created_at:
                created_at = latest_created_at + timedelta(microseconds=1)

        session.add(
            Evaluation(
                id=str(uuid4()),
                posting_id=posting.id,
                profile_version_id=profile_record.id,
                engine_version=ENGINE_VERSION,
                recommendation=assessment.recommendation,
                confidence=assessment.confidence,
                ranking_score=_actionable_ranking_score(assessment),
                reasons_json=reasons_json,
                created_at=created_at,
            )
        )
    if commit:
        session.commit()
    return assessment


def ensure_strategy_reviews(
    session: Session, profile: StrategyProfile
) -> dict[str, StrategyAssessment]:
    assessments: dict[str, StrategyAssessment] = {}
    for posting in session.scalars(select(Posting)).all():
        assessments[posting.id] = ensure_strategy_review(session, profile, posting, commit=False)
    session.commit()
    return assessments


def latest_strategy_evaluation(session: Session, posting_id: str) -> Evaluation | None:
    return session.scalar(
        select(Evaluation)
        .where(
            Evaluation.posting_id == posting_id,
            Evaluation.engine_version == ENGINE_VERSION,
        )
        .order_by(Evaluation.created_at.desc())
    )
