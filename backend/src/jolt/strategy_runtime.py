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
from jolt.evaluation_strategy import (
    StrategyAssessment,
    StrategyProfile,
    assess_posting,
    default_profile_path,
    load_strategy_profile,
)
from jolt.job_search_preferences import load_job_search_preferences
from jolt.preference_aware_evaluation import preference_blockers, sanitize_capture_text

ENGINE_VERSION = "profile-rules-v5"
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
)

_EXPLICIT_HYBRID_WORK_PATTERNS = (
    r"(?im)^\s*hybrid\s*$",
    r"\bhybrid\s+(?:role|position|work|working|schedule|arrangement)\b",
    r"\bwork(?:place)?\s*(?:type|mode)?\s*[:\-]\s*hybrid\b",
)

_EXPLICIT_ONSITE_WORK_PATTERNS = (
    r"(?im)^\s*(?:on[- ]?site|onsite)\s*$",
    r"\b(?:on[- ]?site|onsite)\s+(?:role|position|work|working|requirement)\b",
    r"\bwork(?:place)?\s*(?:type|mode)?\s*[:\-]\s*(?:on[- ]?site|onsite)\b",
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

_FOREIGN_COUNTRY_LOCATION_TERMS = (
    "austria",
    "belgium",
    "bulgaria",
    "croatia",
    "cyprus",
    "czechia",
    "czech republic",
    "denmark",
    "estonia",
    "finland",
    "france",
    "germany",
    "greece",
    "hungary",
    "ireland",
    "italy",
    "latvia",
    "lithuania",
    "luxembourg",
    "netherlands",
    "norway",
    "poland",
    "portugal",
    "romania",
    "slovakia",
    "slovenia",
    "sweden",
    "switzerland",
    "united kingdom",
    "uk",
)

_FOREIGN_RESIDENCE_PATTERN = (
    "(?:" + "|".join(re.escape(location) for location in _FOREIGN_COUNTRY_LOCATION_TERMS) + ")"
)

_EXPLICIT_FOREIGN_RESIDENCE_PATTERNS = (
    rf"\bmust\s+(?:already\s+)?(?:live|reside|be based)\s+in\s+"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bonly\s+(?:open|available)\s+to\s+(?:candidates|applicants)\s+"
    rf"(?:living|resident|based)\s+in\s+{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\brequires?\s+(?:current\s+)?(?:residence|residency)\s+in\s+"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bwork\s+authori[sz]ation\s+(?:is\s+)?required\s+in\s+"
    rf"{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bright\s+to\s+work\s+in\s+{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bremote\s+(?:only\s+)?within\s+{_FOREIGN_RESIDENCE_PATTERN}\b",
    rf"\bremote\s+from\s+{_FOREIGN_RESIDENCE_PATTERN}\b",
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
    normalized = " ".join(location.casefold().split())

    if any(term in normalized for term in _SPAIN_LOCATION_TERMS):
        return "spain"

    if any(term in normalized for term in _BROAD_REMOTE_LOCATION_TERMS):
        return "broad"

    if any(term in normalized for term in _FOREIGN_COUNTRY_LOCATION_TERMS):
        return "foreign_country"

    return "unknown"


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
    evidence_text = "\n".join((title, description))
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

    if clearly_distant or scope == "foreign_country":
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

    if scope == "spain" or not location.strip():
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

    if scope != "foreign_country":
        return assessment

    uncertainties = tuple(
        dict.fromkeys(
            [
                *assessment.uncertainties,
                (
                    "Location eligibility: the vacancy is advertised as remote "
                    "from another specific country; cross-border employment from "
                    "Spain has not been confirmed."
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

    if assessment.eligibility == "uncertain":
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
