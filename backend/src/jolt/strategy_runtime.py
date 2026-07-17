from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
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

ENGINE_VERSION = "profile-rules-v4"


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


def ensure_strategy_reviews(
    session: Session, profile: StrategyProfile
) -> dict[str, StrategyAssessment]:
    profile_record = ensure_private_profile_version(session, profile)
    assessments: dict[str, StrategyAssessment] = {}
    changed = False

    for posting in session.scalars(select(Posting)).all():
        assessment = assess_posting(profile, posting.title, posting.location, posting.description)
        assessments[posting.id] = assessment
        existing = session.scalar(
            select(Evaluation).where(
                Evaluation.posting_id == posting.id,
                Evaluation.profile_version_id == profile_record.id,
                Evaluation.engine_version == ENGINE_VERSION,
            )
        )
        if existing is not None:
            continue
        session.add(
            Evaluation(
                id=str(uuid4()),
                posting_id=posting.id,
                profile_version_id=profile_record.id,
                engine_version=ENGINE_VERSION,
                recommendation=assessment.recommendation,
                confidence=assessment.confidence,
                ranking_score=assessment.fit_by_interview,
                reasons_json=json.dumps(assessment_reasons(assessment)),
                created_at=utc_now(),
            )
        )
        changed = True

    if changed:
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
