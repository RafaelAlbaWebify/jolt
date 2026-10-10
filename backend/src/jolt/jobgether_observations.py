"""Stage API observations as capture evidence without promoting unverified postings."""

from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import stage_capture_artifact
from jolt.database import CaptureItem, CapturePage, CaptureRun, utc_now
from jolt.jobgether_preview import jobgether_identity


def stage_jobgether_observations(
    session: Session, *, search_url: str, jobs: list[dict]
) -> dict[str, object]:
    """Stage one bounded API result; caller owns transaction and commit."""
    if not 1 <= len(jobs) <= 25:
        raise ValueError("Expected 1..25 API observations")
    observed: list[dict] = []
    seen: set[str] = set()
    for job in jobs:
        identifier = job.get("source_job_id")
        url = job.get("url")
        if not isinstance(identifier, str) or len(identifier) != 24:
            continue
        if not isinstance(url, str) or jobgether_identity(url) != identifier:
            continue
        if job.get("identity_mismatch") or identifier in seen:
            continue
        seen.add(identifier)
        observed.append(job)

    if not observed:
        raise ValueError("No reliable Jobgether identities for staging")
    existing = set(
        session.scalars(
            select(CaptureItem.source_job_id)
            .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
            .where(CaptureRun.source == "jobgether")
            .where(CaptureItem.source_job_id.in_(seen))
        ).all()
    )
    run = CaptureRun(
        id=str(uuid4()),
        source="jobgether",
        mode="official_api_observation",
        status="completed",
        search_url=search_url,
        warnings_json="[]",
        requested_item_limit=len(jobs),
        observed_item_count=len(jobs),
        stop_reason="single_api_page_observed",
        started_at=utc_now(),
        completed_at=utc_now(),
    )
    session.add(run)
    session.flush()
    session.add(
        CapturePage(
            id=str(uuid4()),
            capture_run_id=run.id,
            page_number=1,
            visible_job_ids_json=json.dumps([job["source_job_id"] for job in observed]),
            next_control_present=False,
            next_control_enabled=False,
        )
    )
    staged = 0
    for job in observed:
        identifier = job["source_job_id"]
        if identifier in existing:
            continue
        item = CaptureItem(
            id=str(uuid4()),
            capture_run_id=run.id,
            source_job_id=identifier,
            source_url=job["url"],
            title=str(job.get("title") or ""),
            company=str(job.get("company") or ""),
            location=str(job.get("location") or ""),
            detail_status="observed_unverified",
            verification_reasons_json=json.dumps(
                ["API listing metadata only; description and hiring eligibility unverified"]
                + list(job.get("quality_flags") or [])
            ),
            source_document_id=None,
            posting_id=None,
        )
        session.add(item)
        session.flush()
        stage_capture_artifact(
            session,
            capture_item_id=item.id,
            artifact_type="jobgether_api_json",
            content_type="application/json",
            raw_payload=json.dumps(job, ensure_ascii=False, sort_keys=True),
        )
        staged += 1
    return {
        "capture_run_id": run.id,
        "observed": len(jobs),
        "reliable_ids": len(observed),
        "staged_unverified": staged,
        "already_known": len(observed) - staged,
        "committed": False,
    }
