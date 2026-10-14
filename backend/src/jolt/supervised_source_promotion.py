"""Explicit, provenance-checked import of supervised source evidence to JOLT Postings.

The operator must request each import. A Posting is not a positive AI review
and not evidence of permission to work remotely from Spain.
"""

from __future__ import annotations

import hashlib
import json
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact
from jolt.capture_ingestion import ingest_capture_item
from jolt.database import CaptureItem, CaptureRun, Posting
from jolt.infojobs_observations import inspect_offer
from jolt.jobgether_preview import jobgether_identity
from jolt.schemas import ManualIntakeRequest


def _complete_evidence(
    run: CaptureRun, item: CaptureItem, artifact: CaptureArtifact
) -> tuple[str, str, str, str]:
    if hashlib.sha256(artifact.raw_payload.encode("utf-8")).hexdigest() != artifact.content_hash:
        raise ValueError("Stored evidence digest mismatch")
    try:
        document = json.loads(artifact.raw_payload)
    except (ValueError, TypeError) as exc:
        raise ValueError("Malformed captured evidence") from exc
    if run.source == "infojobs":
        if artifact.artifact_type != "infojobs_browser_json" or not isinstance(document, dict):
            raise ValueError("Expected InfoJobs browser evidence")
        offer = document.get("offer")
        if not isinstance(offer, dict):
            raise ValueError("Missing InfoJobs offer")
        parsed = inspect_offer(offer)
        if parsed["source_job_id"] != item.source_job_id:
            raise ValueError("InfoJobs identity mismatch")
        if parsed["url"] != item.source_url:
            raise ValueError("InfoJobs URL mismatch")
        if parsed["description_sha256"] != document.get("description_sha256"):
            raise ValueError("InfoJobs isolated description hash mismatch")
        if parsed["description"] != document.get("isolated_description"):
            raise ValueError("InfoJobs description does not match preserved evidence")
        title, company, location, description = (
            parsed["title"],
            parsed["company"],
            parsed["location"],
            parsed["description"],
        )
    elif run.source == "jobgether":
        if artifact.artifact_type != "jobgether_browser_json" or not isinstance(document, dict):
            raise ValueError("Expected Jobgether browser evidence")
        if document.get("status") != "extracted_unverified" or document.get("mismatches"):
            raise ValueError("Jobgether detail evidence is unresolved")
        if (
            jobgether_identity(str(document.get("url") or "")) != item.source_job_id
            or item.source_url != document.get("url")
            or item.source_job_id != document.get("source_job_id")
        ):
            raise ValueError("Jobgether identity mismatch")
        title = str(document.get("title") or "")
        company = str(document.get("company") or "")
        location = ""
        description = str(document.get("description") or "")
    else:
        raise ValueError("Unsupported source")
    if (
        not title.strip()
        or not company.strip()
        or len(company) > 180
        or len(title) > 240
        or len(description.strip()) < 150
        or urlparse(item.source_url).scheme != "https"
    ):
        raise ValueError("Insufficient title, employer or description evidence")
    if title.strip() != item.title.strip():
        raise ValueError("Stored title and detail evidence disagree")
    if item.company.strip() and company.strip() != item.company.strip():
        raise ValueError("Stored employer and detail evidence disagree")
    return title.strip(), company.strip(), location.strip(), description.strip()


def promote_supervised_item(session: Session, capture_item_id: str) -> dict[str, str]:
    """Promote one bounded, structurally complete observation; caller commits."""
    item = session.get(CaptureItem, capture_item_id)
    if item is None:
        raise ValueError("Captured observation not found")
    run = session.get(CaptureRun, item.capture_run_id)
    if run is None or run.mode != "supervised_browser_observation":
        raise ValueError("Not a supervised source observation")
    if run.source not in {"infojobs", "jobgether"}:
        raise ValueError("Unsupported source")
    if item.posting_id:
        return {
            "status": "already_imported",
            "posting_id": item.posting_id,
            "source_document_id": item.source_document_id or "",
        }
    if item.detail_status != "observed_unverified":
        raise ValueError("Observation is not eligible for explicit review import")
    artifact = session.scalar(
        select(CaptureArtifact).where(CaptureArtifact.capture_item_id == item.id)
    )
    if artifact is None:
        raise ValueError("Captured evidence artifact not found")
    title, company, location, description = _complete_evidence(run, item, artifact)
    raw_text = "\n".join(
        part
        for part in [title, company, f"Location: {location}" if location else "", description]
        if part
    )
    intake = ingest_capture_item(
        session,
        ManualIntakeRequest(
            raw_text=raw_text,
            source_url=item.source_url,
            source_type=f"{run.source}_supervised",
        ),
    )
    posting = session.get(Posting, intake.posting_id)
    if posting is not None:
        posting.description = description
    item.source_document_id = intake.source_document_id
    item.posting_id = intake.posting_id
    item.detail_status = "verified"
    item.company = company
    item.location = location
    item.verification_reasons_json = json.dumps(
        [
            "Source URL, title and captured detail consistency checked",
            "Work-from-Spain eligibility is NOT verified; apply review hardlines",
        ]
    )
    session.flush()
    return {
        "status": "imported_for_review",
        "posting_id": intake.posting_id,
        "source_document_id": intake.source_document_id,
    }
