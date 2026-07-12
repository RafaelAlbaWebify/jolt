from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import CaptureItem, CapturePage, CaptureRun, utc_now
from jolt.schemas import (
    CaptureItemResponse,
    CaptureRunResponse,
    LinkedInFixtureCaptureRequest,
    ManualIntakeRequest,
)
from jolt.sources.linkedin import LinkedInFixtureAdapter
from jolt.workflow import ingest_manual


def _raw_posting_text(title: str, company: str, location: str, description: str) -> str:
    lines = [title, company]
    if location:
        lines.append(f"Location: {location}")
    lines.append(description)
    return "\n".join(line for line in lines if line).strip()


def run_linkedin_fixture_capture(
    session: Session, request: LinkedInFixtureCaptureRequest
) -> CaptureRunResponse:
    adapter = LinkedInFixtureAdapter()
    evidence = adapter.parse_listing_page(request.listing_html, request.page_number)
    now = utc_now()
    run = CaptureRun(
        id=str(uuid4()),
        source="linkedin",
        mode="fixture",
        status="running",
        search_url=request.search_url,
        warnings_json=json.dumps(list(evidence.warnings)),
        started_at=now,
        completed_at=None,
    )
    session.add(run)

    for page in evidence.pages:
        session.add(
            CapturePage(
                id=str(uuid4()),
                capture_run_id=run.id,
                page_number=page.page_number,
                visible_job_ids_json=json.dumps(list(page.visible_job_ids)),
                next_control_present=page.next_control_present,
                next_control_enabled=page.next_control_enabled,
            )
        )

    responses: list[CaptureItemResponse] = []
    unverified_count = 0
    for listing in evidence.listings:
        detail_html = request.detail_html_by_job_id.get(listing.source_job_id, "")
        detail = adapter.parse_detail_page(detail_html, listing)
        status = "verified" if detail.identity_verified else "rejected_unverified"
        source_document_id: str | None = None
        posting_id: str | None = None
        identity_status: str | None = None

        if detail.identity_verified:
            intake = ingest_manual(
                session,
                ManualIntakeRequest(
                    raw_text=_raw_posting_text(
                        detail.title, detail.company, detail.location, detail.description
                    ),
                    source_url=detail.source_url or listing.source_url,
                    source_type="linkedin_fixture",
                ),
            )
            source_document_id = intake.source_document_id
            posting_id = intake.posting_id
            identity_status = intake.identity_status
        else:
            unverified_count += 1

        item = CaptureItem(
            id=str(uuid4()),
            capture_run_id=run.id,
            source_job_id=listing.source_job_id,
            source_url=listing.source_url,
            title=listing.title,
            company=listing.company,
            location=listing.location,
            detail_status=status,
            verification_reasons_json=json.dumps(list(detail.verification_reasons)),
            source_document_id=source_document_id,
            posting_id=posting_id,
        )
        session.add(item)
        responses.append(
            CaptureItemResponse(
                capture_item_id=item.id,
                source_job_id=item.source_job_id,
                detail_status=status,
                verification_reasons=list(detail.verification_reasons),
                source_document_id=source_document_id,
                posting_id=posting_id,
                identity_status=identity_status,
            )
        )

    warnings = list(evidence.warnings)
    if unverified_count:
        warnings.append(f"{unverified_count} detail panel(s) failed identity verification.")
    run.status = "completed_with_warnings" if warnings else "completed"
    run.warnings_json = json.dumps(warnings)
    run.completed_at = utc_now()
    session.commit()
    return _capture_run_response(run, responses)


def get_capture_run(session: Session, capture_run_id: str) -> CaptureRunResponse:
    run = session.get(CaptureRun, capture_run_id)
    if run is None:
        raise LookupError("Capture run was not found.")
    items = session.scalars(
        select(CaptureItem)
        .where(CaptureItem.capture_run_id == capture_run_id)
        .order_by(CaptureItem.source_job_id)
    ).all()
    return _capture_run_response(
        run,
        [
            CaptureItemResponse(
                capture_item_id=item.id,
                source_job_id=item.source_job_id,
                detail_status=item.detail_status,
                verification_reasons=json.loads(item.verification_reasons_json),
                source_document_id=item.source_document_id,
                posting_id=item.posting_id,
                identity_status=None,
            )
            for item in items
        ],
    )


def _capture_run_response(
    run: CaptureRun, items: list[CaptureItemResponse]
) -> CaptureRunResponse:
    return CaptureRunResponse(
        capture_run_id=run.id,
        source=run.source,
        mode=run.mode,
        status=run.status,
        search_url=run.search_url,
        warnings=json.loads(run.warnings_json),
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        items=items,
    )
