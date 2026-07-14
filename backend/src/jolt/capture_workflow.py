from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact, stage_capture_artifact
from jolt.capture_ingestion import ingest_capture_item
from jolt.database import CaptureItem, CapturePage, CaptureRun, utc_now
from jolt.schemas import (
    CaptureItemResponse,
    CapturePageResponse,
    CaptureRunResponse,
    CaptureRunSummary,
    LinkedInFixtureCaptureRequest,
    ManualIntakeRequest,
)
from jolt.sources.linkedin import LinkedInFixtureAdapter


def _raw_posting_text(title: str, company: str, location: str, description: str) -> str:
    lines = [title, company]
    if location:
        lines.append(f"Location: {location}")
    lines.append(description)
    return "\n".join(line for line in lines if line).strip()


def _item_response(
    session: Session, item: CaptureItem, identity_status: str | None = None
) -> CaptureItemResponse:
    artifact = session.scalar(
        select(CaptureArtifact).where(CaptureArtifact.capture_item_id == item.id)
    )
    return CaptureItemResponse(
        capture_item_id=item.id,
        source_job_id=item.source_job_id,
        source_url=item.source_url,
        title=item.title,
        company=item.company,
        location=item.location,
        detail_status=item.detail_status,
        verification_reasons=json.loads(item.verification_reasons_json),
        source_document_id=item.source_document_id,
        posting_id=item.posting_id,
        identity_status=identity_status,
        artifact_id=artifact.id if artifact else None,
        artifact_hash=artifact.content_hash if artifact else None,
    )


def _page_response(page: CapturePage) -> CapturePageResponse:
    return CapturePageResponse(
        page_number=page.page_number,
        visible_job_ids=json.loads(page.visible_job_ids_json),
        next_control_present=page.next_control_present,
        next_control_enabled=page.next_control_enabled,
    )


def run_linkedin_fixture_capture(
    session: Session, request: LinkedInFixtureCaptureRequest
) -> CaptureRunResponse:
    try:
        adapter = LinkedInFixtureAdapter()
        evidence = adapter.parse_listing_page(request.listing_html, request.page_number)
        now = utc_now()
        observed_count = len(evidence.listings)
        run = CaptureRun(
            id=str(uuid4()),
            source="linkedin",
            mode="fixture",
            status="running",
            search_url=request.search_url,
            warnings_json=json.dumps(list(evidence.warnings)),
            requested_item_limit=observed_count,
            observed_item_count=observed_count,
            stop_reason="fixture_page_processed",
            started_at=now,
            completed_at=None,
        )
        session.add(run)

        stored_pages: list[CapturePage] = []
        for page in evidence.pages:
            stored_page = CapturePage(
                id=str(uuid4()),
                capture_run_id=run.id,
                page_number=page.page_number,
                visible_job_ids_json=json.dumps(list(page.visible_job_ids)),
                next_control_present=page.next_control_present,
                next_control_enabled=page.next_control_enabled,
            )
            session.add(stored_page)
            stored_pages.append(stored_page)

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
                intake = ingest_capture_item(
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
            stage_capture_artifact(
                session,
                capture_item_id=item.id,
                artifact_type="linkedin_detail_html",
                content_type="text/html",
                raw_payload=detail_html,
            )
            responses.append(_item_response(session, item, identity_status))

        warnings = list(evidence.warnings)
        if unverified_count:
            warnings.append(f"{unverified_count} detail panel(s) failed identity verification.")
        run.status = "completed_with_warnings" if warnings else "completed"
        run.warnings_json = json.dumps(warnings)
        run.completed_at = utc_now()
        session.commit()
        return _capture_run_response(run, stored_pages, responses)
    except Exception:
        session.rollback()
        raise


def _count_items(session: Session, run_id: str, status: str | None = None) -> int:
    statement = select(func.count(CaptureItem.id)).where(CaptureItem.capture_run_id == run_id)
    if status is not None:
        statement = statement.where(CaptureItem.detail_status == status)
    return int(session.scalar(statement) or 0)


def list_capture_runs(session: Session) -> list[CaptureRunSummary]:
    runs = session.scalars(select(CaptureRun).order_by(CaptureRun.started_at.desc())).all()
    summaries: list[CaptureRunSummary] = []
    for run in runs:
        summaries.append(
            CaptureRunSummary(
                capture_run_id=run.id,
                source=run.source,
                mode=run.mode,
                status=run.status,
                search_url=run.search_url,
                warnings=json.loads(run.warnings_json),
                requested_item_limit=run.requested_item_limit,
                observed_item_count=run.observed_item_count,
                stop_reason=run.stop_reason,
                started_at=run.started_at.isoformat(),
                completed_at=run.completed_at.isoformat() if run.completed_at else None,
                total_items=_count_items(session, run.id),
                verified_items=_count_items(session, run.id, "verified"),
                rejected_items=_count_items(session, run.id, "rejected_unverified"),
            )
        )
    return summaries


def get_capture_run(session: Session, capture_run_id: str) -> CaptureRunResponse:
    run = session.get(CaptureRun, capture_run_id)
    if run is None:
        raise LookupError("Capture run was not found.")
    pages = session.scalars(
        select(CapturePage)
        .where(CapturePage.capture_run_id == capture_run_id)
        .order_by(CapturePage.page_number)
    ).all()
    items = session.scalars(
        select(CaptureItem)
        .where(CaptureItem.capture_run_id == capture_run_id)
        .order_by(CaptureItem.source_job_id)
    ).all()
    return _capture_run_response(
        run,
        list(pages),
        [_item_response(session, item) for item in items],
    )


def _capture_run_response(
    run: CaptureRun,
    pages: list[CapturePage],
    items: list[CaptureItemResponse],
) -> CaptureRunResponse:
    verified = sum(item.detail_status == "verified" for item in items)
    rejected = sum(item.detail_status == "rejected_unverified" for item in items)
    return CaptureRunResponse(
        capture_run_id=run.id,
        source=run.source,
        mode=run.mode,
        status=run.status,
        search_url=run.search_url,
        warnings=json.loads(run.warnings_json),
        requested_item_limit=run.requested_item_limit,
        observed_item_count=run.observed_item_count,
        stop_reason=run.stop_reason,
        started_at=run.started_at.isoformat(),
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        total_items=len(items),
        verified_items=verified,
        rejected_items=rejected,
        pages=[_page_response(page) for page in pages],
        items=items,
    )
