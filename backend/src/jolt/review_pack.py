from __future__ import annotations

import hashlib
import io
import json
from collections import defaultdict
from datetime import datetime
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    Application,
    CaptureItem,
    CapturePage,
    CaptureRun,
    Evaluation,
    MarketIntelligenceObservation,
    Outcome,
    Posting,
    ProfileVersion,
    ReviewDecision,
    SourceDocument,
)
from jolt.market_intelligence import build_market_intelligence
from jolt.strategy_runtime import ENGINE_VERSION

PACK_VERSION = "1.0"


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")


def _json_list(value: str) -> list[object]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _latest_capture(session: Session) -> CaptureRun:
    capture = session.scalar(
        select(CaptureRun)
        .order_by(
            CaptureRun.started_at.desc(),
            CaptureRun.id.desc(),
        )
        .limit(1)
    )
    if capture is None:
        raise LookupError("No capture run exists to review.")
    return capture


def _effective_evaluations(
    evaluations: list[Evaluation],
) -> dict[str, Evaluation]:
    current: dict[str, Evaluation] = {}
    latest: dict[str, Evaluation] = {}

    for evaluation in sorted(
        evaluations,
        key=lambda item: (item.created_at, item.id),
        reverse=True,
    ):
        latest.setdefault(evaluation.posting_id, evaluation)

        if evaluation.engine_version == ENGINE_VERSION:
            current.setdefault(evaluation.posting_id, evaluation)

    return {
        posting_id: current.get(posting_id) or evaluation
        for posting_id, evaluation in latest.items()
    }


def build_review_pack(session: Session) -> bytes:
    generated_at = datetime.now().astimezone().isoformat()
    capture = _latest_capture(session)

    pages = list(
        session.scalars(
            select(CapturePage)
            .where(CapturePage.capture_run_id == capture.id)
            .order_by(CapturePage.page_number, CapturePage.id)
        ).all()
    )

    items = list(
        session.scalars(
            select(CaptureItem)
            .where(CaptureItem.capture_run_id == capture.id)
            .order_by(CaptureItem.id)
        ).all()
    )

    posting_ids = {item.posting_id for item in items if item.posting_id is not None}

    postings = (
        list(
            session.scalars(
                select(Posting)
                .where(Posting.id.in_(posting_ids))
                .order_by(Posting.created_at, Posting.id)
            ).all()
        )
        if posting_ids
        else []
    )

    posting_by_id = {posting.id: posting for posting in postings}

    source_document_ids = {
        item.source_document_id for item in items if item.source_document_id is not None
    }
    source_document_ids.update(posting.source_document_id for posting in postings)

    source_documents = (
        list(
            session.scalars(
                select(SourceDocument)
                .where(SourceDocument.id.in_(source_document_ids))
                .order_by(SourceDocument.captured_at, SourceDocument.id)
            ).all()
        )
        if source_document_ids
        else []
    )

    source_by_id = {source.id: source for source in source_documents}

    evaluations = (
        list(
            session.scalars(
                select(Evaluation)
                .where(Evaluation.posting_id.in_(posting_ids))
                .order_by(Evaluation.created_at, Evaluation.id)
            ).all()
        )
        if posting_ids
        else []
    )

    effective_evaluations = _effective_evaluations(evaluations)

    profile_ids = {evaluation.profile_version_id for evaluation in evaluations}

    profiles = (
        list(
            session.scalars(
                select(ProfileVersion)
                .where(ProfileVersion.id.in_(profile_ids))
                .order_by(ProfileVersion.created_at, ProfileVersion.id)
            ).all()
        )
        if profile_ids
        else []
    )

    reviews = (
        list(
            session.scalars(
                select(ReviewDecision)
                .where(ReviewDecision.posting_id.in_(posting_ids))
                .order_by(ReviewDecision.reviewed_at, ReviewDecision.id)
            ).all()
        )
        if posting_ids
        else []
    )

    applications = (
        list(
            session.scalars(
                select(Application)
                .where(Application.posting_id.in_(posting_ids))
                .order_by(Application.created_at, Application.id)
            ).all()
        )
        if posting_ids
        else []
    )

    outcomes = (
        list(
            session.scalars(
                select(Outcome)
                .where(Outcome.posting_id.in_(posting_ids))
                .order_by(Outcome.recorded_at, Outcome.id)
            ).all()
        )
        if posting_ids
        else []
    )

    observations = list(
        session.scalars(
            select(MarketIntelligenceObservation)
            .where(MarketIntelligenceObservation.source_capture_run_id == capture.id)
            .order_by(
                MarketIntelligenceObservation.captured_at,
                MarketIntelligenceObservation.source_job_id,
                MarketIntelligenceObservation.id,
            )
        ).all()
    )

    evaluation_ids_by_posting: dict[str, list[str]] = defaultdict(list)
    review_ids_by_posting: dict[str, list[str]] = defaultdict(list)
    application_ids_by_posting: dict[str, list[str]] = defaultdict(list)
    outcome_ids_by_posting: dict[str, list[str]] = defaultdict(list)
    observation_ids_by_job: dict[str, list[str]] = defaultdict(list)

    for evaluation in evaluations:
        evaluation_ids_by_posting[evaluation.posting_id].append(evaluation.id)

    for review in reviews:
        review_ids_by_posting[review.posting_id].append(review.id)

    for application in applications:
        application_ids_by_posting[application.posting_id].append(application.id)

    for outcome in outcomes:
        outcome_ids_by_posting[outcome.posting_id].append(outcome.id)

    for observation in observations:
        observation_ids_by_job[observation.source_job_id].append(observation.id)

    latest_review_by_posting: dict[str, ReviewDecision] = {}
    for review in reversed(reviews):
        latest_review_by_posting.setdefault(
            review.posting_id,
            review,
        )

    application_by_posting = {application.posting_id: application for application in applications}

    capture_payload = {
        "id": capture.id,
        "source": capture.source,
        "mode": capture.mode,
        "status": capture.status,
        "search_url": capture.search_url,
        "warnings": _json_list(capture.warnings_json),
        "requested_item_limit": capture.requested_item_limit,
        "observed_item_count": capture.observed_item_count,
        "stop_reason": capture.stop_reason,
        "started_at": _iso(capture.started_at),
        "completed_at": _iso(capture.completed_at),
        "page_count": len(pages),
        "item_count": len(items),
        "verified_item_count": sum(item.detail_status == "verified" for item in items),
        "non_verified_item_count": sum(item.detail_status != "verified" for item in items),
    }

    page_payload = [
        {
            "id": page.id,
            "capture_run_id": page.capture_run_id,
            "page_number": page.page_number,
            "visible_job_ids": _json_list(page.visible_job_ids_json),
            "next_control_present": page.next_control_present,
            "next_control_enabled": page.next_control_enabled,
        }
        for page in pages
    ]

    jobs_payload: list[dict[str, object]] = []
    lineage_payload: list[dict[str, object]] = []

    for item in items:
        posting = posting_by_id.get(item.posting_id) if item.posting_id is not None else None

        source_id = posting.source_document_id if posting is not None else item.source_document_id

        source = source_by_id.get(source_id) if source_id is not None else None

        jobs_payload.append(
            {
                "capture_item_id": item.id,
                "capture_run_id": item.capture_run_id,
                "source_job_id": item.source_job_id,
                "source_url": item.source_url,
                "captured_title": item.title,
                "captured_company": item.company,
                "captured_location": item.location,
                "detail_status": item.detail_status,
                "verification_reasons": _json_list(item.verification_reasons_json),
                "posting_id": item.posting_id,
                "canonical_url": (posting.canonical_url if posting is not None else ""),
                "title": (posting.title if posting is not None else item.title),
                "company": (posting.company if posting is not None else item.company),
                "location": (posting.location if posting is not None else item.location),
                "description": (posting.description if posting is not None else ""),
                "identity_status": (posting.identity_status if posting is not None else ""),
                "source_document_id": source_id,
                "source_raw_text": (source.raw_text if source is not None else ""),
            }
        )

        effective = (
            effective_evaluations.get(item.posting_id) if item.posting_id is not None else None
        )

        lineage_payload.append(
            {
                "capture_item_id": item.id,
                "source_job_id": item.source_job_id,
                "posting_id": item.posting_id,
                "source_document_id": source_id,
                "evaluation_ids": (
                    evaluation_ids_by_posting.get(
                        item.posting_id,
                        [],
                    )
                    if item.posting_id is not None
                    else []
                ),
                "effective_evaluation_id": (effective.id if effective is not None else None),
                "review_decision_ids": (
                    review_ids_by_posting.get(
                        item.posting_id,
                        [],
                    )
                    if item.posting_id is not None
                    else []
                ),
                "application_ids": (
                    application_ids_by_posting.get(
                        item.posting_id,
                        [],
                    )
                    if item.posting_id is not None
                    else []
                ),
                "outcome_ids": (
                    outcome_ids_by_posting.get(
                        item.posting_id,
                        [],
                    )
                    if item.posting_id is not None
                    else []
                ),
                "market_observation_ids": (
                    observation_ids_by_job.get(
                        item.source_job_id,
                        [],
                    )
                ),
            }
        )

    classifications_payload = [
        {
            "posting_id": posting.id,
            "title": posting.title,
            "company": posting.company,
            "effective_evaluation": (
                {
                    "id": evaluation.id,
                    "profile_version_id": (evaluation.profile_version_id),
                    "engine_version": evaluation.engine_version,
                    "recommendation": evaluation.recommendation,
                    "confidence": evaluation.confidence,
                    "ranking_score": evaluation.ranking_score,
                    "reasons": _json_list(evaluation.reasons_json),
                    "created_at": _iso(evaluation.created_at),
                }
                if (evaluation := effective_evaluations.get(posting.id)) is not None
                else None
            ),
            "all_evaluations": [
                {
                    "id": evaluation.id,
                    "profile_version_id": (evaluation.profile_version_id),
                    "engine_version": evaluation.engine_version,
                    "recommendation": evaluation.recommendation,
                    "confidence": evaluation.confidence,
                    "ranking_score": evaluation.ranking_score,
                    "reasons": _json_list(evaluation.reasons_json),
                    "created_at": _iso(evaluation.created_at),
                }
                for evaluation in evaluations
                if evaluation.posting_id == posting.id
            ],
        }
        for posting in postings
    ]

    state_payload = []
    for posting in postings:
        review = latest_review_by_posting.get(posting.id)
        application = application_by_posting.get(posting.id)

        if application is not None:
            lifecycle_state = "application"
        elif review is not None:
            lifecycle_state = review.decision
        else:
            lifecycle_state = "pending_review"

        state_payload.append(
            {
                "posting_id": posting.id,
                "title": posting.title,
                "company": posting.company,
                "lifecycle_state": lifecycle_state,
                "latest_review": (
                    {
                        "id": review.id,
                        "decision": review.decision,
                        "reason_code": review.reason_code,
                        "notes": review.notes,
                        "evaluation_overridden": (review.evaluation_overridden),
                        "reviewed_at": _iso(review.reviewed_at),
                    }
                    if review is not None
                    else None
                ),
                "application": (
                    {
                        "id": application.id,
                        "status": application.status,
                        "application_url": (application.application_url),
                        "resume_used": application.resume_used,
                        "notes": application.notes,
                        "created_at": _iso(application.created_at),
                        "updated_at": _iso(application.updated_at),
                    }
                    if application is not None
                    else None
                ),
            }
        )

    observations_payload = [
        {
            "id": observation.id,
            "source_capture_run_id": (observation.source_capture_run_id),
            "source_job_id": observation.source_job_id,
            "posting_identity_key": (observation.posting_identity_key),
            "source_url": observation.source_url,
            "title": observation.title,
            "company": observation.company,
            "location": observation.location,
            "description": observation.description,
            "engine_version": observation.engine_version,
            "recommendation": observation.recommendation,
            "confidence": observation.confidence,
            "ranking_score": observation.ranking_score,
            "reasons": _json_list(observation.reasons_json),
            "captured_at": _iso(observation.captured_at),
            "observed_at": _iso(observation.observed_at),
        }
        for observation in observations
    ]

    profiles_payload = [
        {
            "id": profile.id,
            "profile_id": profile.profile_id,
            "version": profile.version,
            "configuration": json.loads(profile.configuration_json),
            "created_at": _iso(profile.created_at),
        }
        for profile in profiles
    ]

    evidence_payload = [
        {
            "id": source.id,
            "source_type": source.source_type,
            "source_url": source.source_url,
            "raw_text": source.raw_text,
            "content_hash": source.content_hash,
            "captured_at": _iso(source.captured_at),
        }
        for source in source_documents
    ]

    review_payload = [
        {
            "id": review.id,
            "posting_id": review.posting_id,
            "evaluation_id": review.evaluation_id,
            "decision": review.decision,
            "reason_code": review.reason_code,
            "notes": review.notes,
            "evaluation_overridden": (review.evaluation_overridden),
            "reviewed_at": _iso(review.reviewed_at),
        }
        for review in reviews
    ]

    outcome_payload = [
        {
            "id": outcome.id,
            "posting_id": outcome.posting_id,
            "application_id": outcome.application_id,
            "outcome_type": outcome.outcome_type,
            "stage_reached": outcome.stage_reached,
            "reason_code": outcome.reason_code,
            "notes": outcome.notes,
            "recorded_at": _iso(outcome.recorded_at),
        }
        for outcome in outcomes
    ]

    market_payload = {
        "latest_capture_id": capture.id,
        "latest_capture_observation_count": len(observations_payload),
        "capture_batches_view": build_market_intelligence(
            session,
            timeframe="all",
            source_scope="capture_batches",
        ),
        "all_sources_view": build_market_intelligence(
            session,
            timeframe="all",
            source_scope="all",
        ),
    }

    files: dict[str, bytes] = {
        "README.md": (
            b"# JOLT Review Pack\n\n"
            b"Upload this ZIP to ChatGPT to audit JOLT against its own evidence.\n\n"
            b"The pack is scoped to the latest capture for job-level evidence and "
            b"classification lineage, while Market Insights also includes JOLT's "
            b"current durable capture-market and all-source aggregate views.\n"
        ),
        "capture/run.json": _json_bytes(capture_payload),
        "capture/pages.json": _json_bytes(page_payload),
        "jobs/jobs.json": _json_bytes(jobs_payload),
        "jobs/jolt_classifications.json": _json_bytes(classifications_payload),
        "jobs/state.json": _json_bytes(state_payload),
        "profile/profile_versions.json": _json_bytes(profiles_payload),
        "evidence/source_documents.json": _json_bytes(evidence_payload),
        "audit/lineage.json": _json_bytes(lineage_payload),
        "audit/review_decisions.json": _json_bytes(review_payload),
        "audit/outcomes.json": _json_bytes(outcome_payload),
        "market/latest_capture_observations.json": _json_bytes(observations_payload),
        "market/current_views.json": _json_bytes(market_payload),
    }

    manifest = {
        "pack_type": "jolt_review_pack",
        "pack_version": PACK_VERSION,
        "generated_at": generated_at,
        "latest_capture_id": capture.id,
        "counts": {
            "capture_pages": len(page_payload),
            "capture_items": len(jobs_payload),
            "canonical_postings": len(postings),
            "classifications": len(classifications_payload),
            "source_documents": len(evidence_payload),
            "market_observations": len(observations_payload),
            "review_decisions": len(review_payload),
            "applications": len(applications),
            "outcomes": len(outcome_payload),
        },
        "files": {
            name: {
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
            for name, content in sorted(files.items())
        },
    }

    files["manifest.json"] = _json_bytes(manifest)

    output = io.BytesIO()

    with ZipFile(
        output,
        "w",
        compression=ZIP_DEFLATED,
    ) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(
                name,
                content,
            )

    return output.getvalue()
