from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_readiness import (
    PROFILE_VERSION_ID as READINESS_PROFILE_VERSION_ID,
)
from jolt.application_readiness import (
    READINESS_ENGINE_VERSION,
    analyze_readiness,
    readiness_payload,
)
from jolt.automated_review import analyze_posting
from jolt.database import Application, Outcome, Posting, ReviewDecision
from jolt.evaluation_authority import authoritative_evaluation, latest_readiness_report
from jolt.evaluation_strategy import StrategyAssessment
from jolt.schemas import ApplicationReadinessSummary, OpportunitySummary, StrategyGapSummary
from jolt.strategy_runtime import (
    ENGINE_VERSION as STRATEGY_ENGINE_VERSION,
)
from jolt.strategy_runtime import (
    calibrated_strategy_assessment,
    load_active_strategy_profile,
    proposed_decision,
)


def _authoritative_assessment(posting: Posting) -> StrategyAssessment | None:
    profile = load_active_strategy_profile()
    if profile is None:
        return None
    return calibrated_strategy_assessment(
        profile,
        title=posting.title,
        location=posting.location,
        description=posting.description,
    )


def _build_summary(session: Session, posting: Posting) -> OpportunitySummary | None:
    evaluation = authoritative_evaluation(session, posting.id)
    if evaluation is None:
        return None

    assessment: StrategyAssessment | None = None
    if evaluation.engine_version == STRATEGY_ENGINE_VERSION:
        assessment = _authoritative_assessment(posting)
    legacy_analysis = analyze_posting(posting.title, posting.location, posting.description)

    readiness_report = latest_readiness_report(session, posting.id)
    if readiness_report is not None:
        readiness = ApplicationReadinessSummary.model_validate(readiness_payload(readiness_report))
    else:
        readiness_analysis = analyze_readiness(posting)
        readiness = ApplicationReadinessSummary(
            report_id="",
            profile_version_id=READINESS_PROFILE_VERSION_ID,
            engine_version=READINESS_ENGINE_VERSION,
            priority=readiness_analysis.priority,
            readiness_score=readiness_analysis.readiness_score,
            evidence_matches=readiness_analysis.evidence_matches,
            credibility_warnings=readiness_analysis.credibility_warnings,
            cv_tailoring_points=readiness_analysis.cv_tailoring_points,
            talking_points=readiness_analysis.talking_points,
            interview_questions=readiness_analysis.interview_questions,
            revision_topics=readiness_analysis.revision_topics,
            checklist=readiness_analysis.checklist,
        )
    review = session.scalar(
        select(ReviewDecision)
        .where(ReviewDecision.posting_id == posting.id)
        .order_by(ReviewDecision.reviewed_at.desc())
    )
    application = session.scalar(select(Application).where(Application.posting_id == posting.id))
    outcome = (
        session.scalar(select(Outcome).where(Outcome.application_id == application.id))
        if application
        else None
    )

    if assessment:
        gap_summaries = [
            StrategyGapSummary(
                capability_id=gap.capability_id,
                label=gap.label,
                evidence_level=gap.evidence_level,
                gap_type=gap.gap_type,
                matched_terms=list(gap.matched_terms),
                preparation_topics=list(gap.preparation_topics),
            )
            for gap in assessment.gaps
        ]
        fit_summary = (
            f"Current fit {assessment.fit_now}; interview-ready fit "
            f"{assessment.fit_by_interview}; onboarding fit {assessment.fit_on_the_job}."
        )
        proposed = proposed_decision(assessment)
        strengths = list(assessment.strengths)
        gaps = [
            f"{gap.label}: {gap.gap_type} (evidence level {gap.evidence_level})."
            for gap in assessment.gaps
        ]
        blockers = list(assessment.blockers)
        uncertainties = list(assessment.uncertainties)
        dimensions = assessment.dimensions
    else:
        gap_summaries = []
        fit_summary = legacy_analysis.summary
        proposed = legacy_analysis.proposed_decision
        strengths = legacy_analysis.strengths
        gaps = legacy_analysis.gaps
        blockers = legacy_analysis.blockers
        uncertainties = legacy_analysis.uncertainties
        dimensions = legacy_analysis.dimensions

    return OpportunitySummary(
        posting_id=posting.id,
        evaluation_id=evaluation.id,
        source_url=posting.source_document.source_url,
        title=posting.title,
        company=posting.company,
        location=posting.location,
        recommendation=evaluation.recommendation,
        proposed_decision=proposed,
        confidence=evaluation.confidence,
        ranking_score=evaluation.ranking_score,
        fit_summary=fit_summary,
        strengths=strengths,
        gaps=gaps,
        blockers=blockers,
        uncertainties=uncertainties,
        dimensions=dimensions,
        reasons=json.loads(evaluation.reasons_json),
        profile_version_id=evaluation.profile_version_id,
        engine_version=evaluation.engine_version,
        eligibility=assessment.eligibility if assessment else "",
        role_family_id=assessment.role_family_id if assessment else None,
        fit_now=assessment.fit_now if assessment else None,
        fit_by_interview=assessment.fit_by_interview if assessment else None,
        fit_on_the_job=assessment.fit_on_the_job if assessment else None,
        interview_days=assessment.interview_days if assessment else None,
        estimated_preparation_hours=(
            assessment.estimated_preparation_hours if assessment else None
        ),
        strategy_gaps=gap_summaries,
        preparation_plan=(list(assessment.preparation_plan) if assessment else []),
        readiness=readiness,
        review_decision=review.decision if review else None,
        application_id=application.id if application else None,
        application_status=application.status if application else None,
        outcome_type=outcome.outcome_type if outcome else None,
    )


def list_opportunity_workbench(session: Session) -> list[OpportunitySummary]:
    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    return [
        summary for posting in postings if (summary := _build_summary(session, posting)) is not None
    ]


def get_opportunity_workbench(session: Session, posting_id: str) -> OpportunitySummary:
    posting = session.get(Posting, posting_id)
    if posting is None:
        raise LookupError(f"Opportunity {posting_id} was not found.")

    summary = _build_summary(session, posting)
    if summary is None:
        raise LookupError(f"Opportunity {posting_id} has no evaluation.")
    return summary
