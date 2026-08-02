from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, replace
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

ENGINE_VERSION = "profile-rules-v4"
_PEOPLE_MANAGEMENT_LABEL = "formal people-management ownership"
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
    return _apply_saved_preferences(
        assessment,
        title=title,
        location=location,
        description=sanitized_description,
    )


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
        .order_by(Evaluation.created_at.desc())
    )
    unchanged = bool(
        existing
        and existing.recommendation == assessment.recommendation
        and existing.confidence == assessment.confidence
        and existing.ranking_score == assessment.fit_by_interview
        and existing.reasons_json == reasons_json
    )
    if not unchanged:
        session.add(
            Evaluation(
                id=str(uuid4()),
                posting_id=posting.id,
                profile_version_id=profile_record.id,
                engine_version=ENGINE_VERSION,
                recommendation=assessment.recommendation,
                confidence=assessment.confidence,
                ranking_score=assessment.fit_by_interview,
                reasons_json=reasons_json,
                created_at=utc_now(),
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
