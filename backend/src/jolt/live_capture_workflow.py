from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy.orm import Session

from jolt.capture_ingestion import ingest_capture_item
from jolt.database import CaptureItem, CapturePage, CaptureRun, utc_now
from jolt.schemas import (
    CaptureItemResponse,
    CapturePageResponse,
    CaptureRunResponse,
    LinkedInLiveCaptureRequest,
    ManualIntakeRequest,
)


def _posting_text(title: str, company: str, location: str, description: str) -> str:
    lines = [title, company]
    if location:
        lines.append(f"Location: {location}")
    if description:
        lines.append(description)
    return "\n".join(line for line in lines if line).strip()


def run_linkedin_live_capture(
    session: Session, request: LinkedInLiveCaptureRequest
) -> CaptureRunResponse:
    try:
        run = CaptureRun(
            id=str(uuid4()),
            source="linkedin",
            mode="supervised_live",
            status="running",
            search_url=request.search_url,
            warnings_json="[]",
            started_at=utc_now(),
            completed_at=None,
        )
        session.add(run)

        visible_ids = [item.source_job_id for item in request.items]
        page = CapturePage(
            id=str(uuid4()),
            capture_run_id=run.id,
            page_number=1,
            visible_job_ids_json=json.dumps(visible_ids),
            next_control_present=False,
            next_control_enabled=False,
        )
        session.add(page)

        responses: list[CaptureItemResponse] = []
        warnings: list[str] = []
        for evidence in request.items:
            verified = evidence.identity_verified and bool(evidence.description.strip())
            status = "verified" if verified else "rejected_unverified"
            reasons = [evidence.verification_reason] if evidence.verification_reason else []
            if evidence.identity_verified and not evidence.description.strip():
                reasons.append("Verified detail panel contained no usable job description text.")

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
                        source_type="linkedin_live",
                    ),
                )
                source_document_id = intake.source_document_id
                posting_id = intake.posting_id
                identity_status = intake.identity_status
            else:
                warnings.append(f"LinkedIn job {evidence.source_job_id} was not ingested.")

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
                )
            )

        completed_at = utc_now()
        run.status = "completed_with_warnings" if warnings else "completed"
        run.warnings_json = json.dumps(warnings)
        run.completed_at = completed_at
        session.commit()

        verified_count = sum(item.detail_status == "verified" for item in responses)
        rejected_count = len(responses) - verified_count
        return CaptureRunResponse(
            capture_run_id=run.id,
            source=run.source,
            mode=run.mode,
            status=run.status,
            search_url=run.search_url,
            warnings=warnings,
            started_at=run.started_at.isoformat(),
            completed_at=completed_at.isoformat(),
            total_items=len(responses),
            verified_items=verified_count,
            rejected_items=rejected_count,
            pages=[
                CapturePageResponse(
                    page_number=1,
                    visible_job_ids=visible_ids,
                    next_control_present=False,
                    next_control_enabled=False,
                )
            ],
            items=responses,
        )
    except Exception:
        session.rollback()
        raise
