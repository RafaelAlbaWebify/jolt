from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_readiness import ensure_readiness_report, readiness_payload
from jolt.automated_review import analyze_posting, ensure_automated_reviews
from jolt.database import Application, Evaluation, Outcome, Posting, ReviewDecision
from jolt.schemas import ApplicationReadinessSummary, OpportunitySummary, StrategyGapSummary
from jolt.strategy_runtime import (
    ensure_strategy_reviews,
    latest_strategy_evaluation,
    load_active_strategy_profile,
    proposed_decision,
)


def list_opportunity_workbench(session: Session) -> list[OpportunitySummary]:
    ensure_automated_reviews(session)
    profile = load_active_strategy_profile()
    strategy_assessments = ensure_strategy_reviews(session, profile) if profile else {}

    postings = session.scalars(select(Posting).order_by(Posting.created_at.desc())).all()
    results: list[OpportunitySummary] = []

    for posting in postings:
        legacy_evaluation = session.scalar(
            select(Evaluation)
            .where(Evaluation.posting_id == posting.id)
            .order_by(Evaluation.created_at.desc())
        )
        if legacy_evaluation is None:
            continue

        assessment = strategy_assessments.get(posting.id)
        strategy_evaluation = (
            latest_strategy_evaluation(session, posting.id) if assessment else None
        )
        evaluation = strategy_evaluation or legacy_evaluation
        legacy_analysis = analyze_posting(posting.title, posting.location, posting.description)

        readiness_report = ensure_readiness_report(session, posting)
        readiness = ApplicationReadinessSummary.model_validate(readiness_payload(readiness_report))
        review = session.scalar(
            select(ReviewDecision)
            .where(ReviewDecision.posting_id == posting.id)
            .order_by(ReviewDecision.reviewed_at.desc())
        )
        application = session.scalar(
            select(Application).where(Application.posting_id == posting.id)
        )
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
                f"{assessment.fit_by_interview}; onboarding fit "
                f"{assessment.fit_on_the_job}."
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

        results.append(
            OpportunitySummary(
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
        )

    return results
