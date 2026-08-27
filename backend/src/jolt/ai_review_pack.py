from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import CaptureItem, CapturePage, CaptureRun, Posting, SourceDocument
from jolt.errors import JoltNotFoundError
from jolt.preference_aware_evaluation import sanitize_capture_text

PACK_VERSION = "1.0"
REVIEW_CONTRACT_VERSION = "1.0"


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
        raise JoltNotFoundError("No capture run exists to export for AI review.")
    return capture


def _analysis_text(
    *,
    title: str,
    company: str,
    location: str,
    description: str,
    source_raw_text: str,
) -> str:
    evidence = source_raw_text.strip() or description.strip()

    cleaned = sanitize_capture_text(evidence)

    header = "\n".join(
        (
            f"Title: {title.strip()}",
            f"Company: {company.strip()}",
            f"Location: {location.strip()}",
        )
    )

    if not cleaned:
        return header

    return f"{header}\n\n{cleaned}".strip()


def build_ai_review_pack(session: Session) -> bytes:
    """Export latest captured evidence for external AI classification.

    This export deliberately contains no JOLT recommendation, score,
    eligibility classification, profile evaluation, or proposed decision.
    JOLT's role here is evidence capture, identity linkage, and text cleaning.
    """

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

    capture_payload = {
        "capture_run_id": capture.id,
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
    }

    page_payload = [
        {
            "capture_run_id": page.capture_run_id,
            "page_number": page.page_number,
            "visible_job_ids": _json_list(page.visible_job_ids_json),
            "next_control_present": page.next_control_present,
            "next_control_enabled": page.next_control_enabled,
        }
        for page in pages
    ]

    jobs_payload: list[dict[str, object]] = []

    for item in items:
        posting = posting_by_id.get(item.posting_id) if item.posting_id is not None else None

        source_document_id = (
            posting.source_document_id if posting is not None else item.source_document_id
        )

        source = source_by_id.get(source_document_id) if source_document_id is not None else None

        title = posting.title if posting is not None else item.title
        company = posting.company if posting is not None else item.company
        location = posting.location if posting is not None else item.location
        description = posting.description if posting is not None else ""
        source_raw_text = source.raw_text if source is not None else ""

        clean_description = sanitize_capture_text(description)
        clean_source_text = sanitize_capture_text(source_raw_text)

        jobs_payload.append(
            {
                "capture_run_id": item.capture_run_id,
                "capture_item_id": item.id,
                "posting_id": item.posting_id,
                "source_job_id": item.source_job_id,
                "source_url": item.source_url,
                "canonical_url": (posting.canonical_url if posting is not None else ""),
                "title": title,
                "company": company,
                "location": location,
                "identity_status": (posting.identity_status if posting is not None else ""),
                "detail_status": item.detail_status,
                "verification_reasons": _json_list(item.verification_reasons_json),
                "source_document_id": source_document_id,
                "description_clean": clean_description,
                "source_text_clean": clean_source_text,
                "analysis_text": _analysis_text(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    source_raw_text=source_raw_text,
                ),
                "audit": {
                    "source_raw_text": source_raw_text,
                    "source_raw_text_sha256": hashlib.sha256(
                        source_raw_text.encode("utf-8")
                    ).hexdigest(),
                },
            }
        )

    response_template = {
        "contract_type": "jolt_ai_review",
        "contract_version": REVIEW_CONTRACT_VERSION,
        "capture_run_id": capture.id,
        "review_source": "chatgpt_source_first",
        "review_version": "<AI review version>",
        "reviewed_at": "<ISO-8601 timestamp>",
        "jobs": [
            {
                "posting_id": "<posting_id from jobs/ai_review_jobs.json>",
                "source_job_id": "<source_job_id>",
                "decision": "strong_pursue|pursue|conditional|reject",
                "priority_score": 0,
                "geography_status": "eligible|conditional|ineligible|unknown",
                "clearance_status": "clear|conditional|blocked|unknown",
                "language_status": "clear|conditional|blocked|unknown",
                "technical_fit": 0,
                "duplicate_of_posting_id": None,
                "summary": "",
                "reasons": [],
            }
        ],
    }

    files: dict[str, bytes] = {
        "README.md": (
            b"# JOLT AI Review Package\n\n"
            b"This package is for external source-first AI analysis.\n\n"
            b"JOLT has captured, linked, and cleaned the vacancy evidence. "
            b"It has NOT supplied a recommendation, ranking score, eligibility "
            b"decision, or classifier result as review authority.\n\n"
            b"Primary analysis input: jobs/ai_review_jobs.json\n"
            b"Expected return shape: contract/ai_review_response_template.json\n"
        ),
        "capture/run.json": _json_bytes(capture_payload),
        "capture/pages.json": _json_bytes(page_payload),
        "jobs/ai_review_jobs.json": _json_bytes(jobs_payload),
        "contract/ai_review_response_template.json": _json_bytes(response_template),
    }

    manifest = {
        "pack_type": "jolt_ai_review_input",
        "pack_version": PACK_VERSION,
        "review_contract_version": REVIEW_CONTRACT_VERSION,
        "generated_at": generated_at,
        "capture_run_id": capture.id,
        "classification_authority": "external_ai",
        "jolt_decisions_included": False,
        "jolt_scores_included": False,
        "counts": {
            "capture_pages": len(page_payload),
            "capture_items": len(jobs_payload),
            "verified_items": sum(item.detail_status == "verified" for item in items),
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
            archive.writestr(name, content)

    return output.getvalue()
