from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from jolt.capture_artifacts import stage_capture_artifact
from jolt.capture_ingestion import ingest_capture_item
from jolt.database import CaptureItem, CapturePage, CaptureRun, Posting, utc_now
from jolt.market_intelligence_observations import extract_market_intelligence_observations
from jolt.schemas import (
    CaptureItemResponse,
    CapturePageResponse,
    CaptureRunResponse,
    IndeedLiveCaptureItemRequest,
    IndeedLiveCaptureRequest,
    ManualIntakeRequest,
)
from jolt.strategy_runtime import ensure_strategy_review, load_active_strategy_profile


def _posting_text(title: str, company: str, location: str, description: str) -> str:
    lines = [title, company]
    if location:
        lines.append(f"Location: {location}")
    if description:
        lines.append(description)
    return "\n".join(line for line in lines if line).strip()


def _structure_failures(evidence: IndeedLiveCaptureItemRequest) -> list[str]:
    failures: list[str] = []
    if not evidence.title.strip():
        failures.append("Verified Indeed detail page contained no usable job title.")
    if not evidence.company.strip():
        failures.append("Verified Indeed detail page contained no usable company name.")
    if not evidence.description.strip():
        failures.append("Verified Indeed detail page contained no usable job description.")
    return failures


def run_indeed_live_capture(
    session: Session,
    request: IndeedLiveCaptureRequest,
) -> CaptureRunResponse:
    try:
        run = CaptureRun(
            id=str(uuid4()),
            source="indeed",
            mode="supervised_live",
            status="running",
            search_url=request.search_url,
            warnings_json="[]",
            requested_item_limit=request.requested_item_limit or len(request.items),
            observed_item_count=len(request.items),
            stop_reason=request.stop_reason or "submitted_batch_completed",
            started_at=utc_now(),
            completed_at=None,
        )
        session.add(run)
        session.flush()

        page_evidence = (
            [(page.page_number, list(page.visible_job_ids)) for page in request.pages]
            if request.pages
            else [(1, [item.source_job_id for item in request.items])]
        )
        page_responses: list[CapturePageResponse] = []
        for index, (page_number, visible_job_ids) in enumerate(page_evidence):
            page_response = CapturePageResponse(
                page_number=page_number,
                visible_job_ids=visible_job_ids,
                next_control_present=index < len(page_evidence) - 1,
                next_control_enabled=index < len(page_requests) - 1,
            )
            page_responses.append(page_response)
            session.add(
                CapturePage(
                    id=str(uuid4()),
                    capture_run_id=run.id,
                    page_number=page_response.page_number,
                    visible_job_ids_json=json.dumps(page_response.visible_job_ids),
                    next_control_present=page_response.next_control_present,
                    next_control_enabled=page_response.next_control_enabled,
                )
            )

        profile = load_active_strategy_profile()
        warnings: list[str] = []
        responses: list[CaptureItemResponse] = []

        for evidence in request.items:
            failures = _structure_failures(evidence)
            verified = evidence.identity_verified and not failures
            status = "verified" if verified else "rejected_unverified"
            reasons = [evidence.verification_reason] if evidence.verification_reason else []
            reasons.extend(failures)
            if not evidence.identity_verified and not evidence.verification_reason:
                reasons.append("Indeed detail-page identity was not verified.")

            source_document_id: str | None = None
            posting_id: str | None = None
            identity_status: str | None = None

            if verified:
                intake = ingest_capture_item(
                    session,
                    ManualIntakeRequest(
                        raw_text=_posting_text(
                            evidence.title,
                            evidence.company,
                            evidence.location,
                            evidence.description,
                        ),
                        source_url=evidence.source_url,
                        source_type="indeed_live",
                    ),
                )
                source_document_id = intake.source_document_id
                posting_id = intake.posting_id
                identity_status = intake.identity_status
                if profile is not None:
                    posting = session.get(Posting, posting_id)
                    if posting is not None:
                        ensure_strategy_review(session, profile, posting, commit=False)
            else:
                warnings.append(f"Indeed job {evidence.source_job_id} was not ingested.")

            item = CaptureItem(
                id=str(uuid4()),
                capture_run_id=run.id,
                source_job_id=evidence.source_job_id,
                source_url=evidence.source_url,
                title=evidence.title,
                company=evidence.company,
                location=evidence.location,
                detail_status=status,
                verification_reasons_json=json.dumps(reasons),
                source_document_id=source_document_id,
                posting_id=posting_id,
            )
            session.add(item)
            session.flush()
            artifact = stage_capture_artifact(
                session,
                capture_item_id=item.id,
                artifact_type="indeed_live_item_json",
                content_type="application/json",
                raw_payload=json.dumps(evidence.model_dump(mode="json"), sort_keys=True),
            )
            responses.append(
                CaptureItemResponse(
                    capture_item_id=item.id,
                    source_job_id=item.source_job_id,
                    source_url=item.source_url,
                    title=item.title,
                    company=item.company,
                    location=item.location,
                    detail_status=item.detail_status,
                    verification_reasons=reasons,
                    source_document_id=source_document_id,
                    posting_id=posting_id,
                    identity_status=identity_status,
                    artifact_id=artifact.id,
                    artifact_hash=artifact.content_hash,
                )
            )

        completed_at = utc_now()
        run.status = "completed_with_warnings" if warnings else "completed"
        run.warnings_json = json.dumps(warnings)
        run.completed_at = completed_at
        extract_market_intelligence_observations(session, run.id)
        session.commit()

        verified_count = sum(item.detail_status == "verified" for item in responses)
        return CaptureRunResponse(
            capture_run_id=run.id,
            source=run.source,
            mode=run.mode,
            status=run.status,
            search_url=run.search_url,
            warnings=warnings,
            requested_item_limit=run.requested_item_limit,
            observed_item_count=run.observed_item_count,
            stop_reason=run.stop_reason,
            started_at=run.started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            total_items=len(responses),
            verified_items=verified_count,
            rejected_items=len(responses) - verified_count,
            pages=page_responses,
            items=responses,
        )
    except Exception:
        session.rollback()
        raise
