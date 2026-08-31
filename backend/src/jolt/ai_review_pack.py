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
from jolt.job_search_preferences import load_job_search_preferences
from jolt.preference_aware_evaluation import sanitize_capture_text

PACK_VERSION = "2.0"
REVIEW_CONTRACT_VERSION = "2.0"


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
        select(CaptureRun).order_by(CaptureRun.started_at.desc(), CaptureRun.id.desc()).limit(1)
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
    return header if not cleaned else f"{header}\n\n{cleaned}".strip()


def build_ai_review_pack(session: Session) -> bytes:
    """Export the latest vacancy evidence and candidate policy for one AI round.

    JOLT remains evidence/workflow authority only. The external AI is responsible
    for recommendation, transferability, hard-blocker interpretation, learnability,
    and aggregate market intelligence.
    """

    generated_at = datetime.now().astimezone().isoformat()
    capture = _latest_capture(session)
    preferences = load_job_search_preferences()

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

        jobs_payload.append(
            {
                "capture_run_id": item.capture_run_id,
                "capture_item_id": item.id,
                "posting_id": item.posting_id,
                "source_job_id": item.source_job_id,
                "source_url": item.source_url,
                "canonical_url": posting.canonical_url if posting is not None else "",
                "title": title,
                "company": company,
                "location": location,
                "identity_status": posting.identity_status if posting is not None else "",
                "detail_status": item.detail_status,
                "verification_reasons": _json_list(item.verification_reasons_json),
                "source_document_id": source_document_id,
                "description_clean": sanitize_capture_text(description),
                "source_text_clean": sanitize_capture_text(source_raw_text),
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

    candidate_payload = preferences.model_dump(mode="json")

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
                "geography_basis": "explicit_eligible|neutral_location|explicit_restricted|unknown",
                "clearance_status": "clear|conditional|blocked|unknown",
                "language_status": "clear|conditional|blocked|unknown",
                "language_required_level": None,
                "language_certificate_required": False,
                "language_requirement_evidence": None,
                "technical_fit": 0,
                "duplicate_of_posting_id": None,
                "hard_blockers": [
                    {
                        "blocker_type": "language|geography|work_authorization|citizenship|clearance|duplicate|other_legal",
                        "evidence": "Exact vacancy evidence for the blocker",
                    }
                ],
                "transferable_skills": [],
                "skill_gaps": [],
                "learnability": "already_ready|quick_1_7_days|short_1_2_weeks|substantial|unknown",
                "preparation_actions": [],
                "summary": "",
                "reasons": [],
            }
        ],
        "market_insights": {
            "summary": "",
            "demanded_technologies": [],
            "recurring_skill_gaps": [],
            "quick_learn_gaps": [],
            "strong_existing_skills": [],
            "promising_role_families": [],
            "search_terms": [],
            "learning_priorities": [],
            "application_strategy": [],
        },
    }

    readme = """# JOLT AI Review + Market Insights Package

One package, one external AI analysis round, one return import.

JOLT has captured, linked and cleaned vacancy evidence. It has NOT supplied a
recommendation, ranking score, eligibility decision, or classifier result as
review authority.

Use:
- `jobs/ai_review_jobs.json` for source-first vacancy evidence.
- `candidate/job_search_preferences.json` for candidate constraints and policy.
- `contract/ai_review_response_template.json` for the exact return shape.

Critical review policy:
- A foreign LinkedIn/listing location is neutral by itself.
- Geography becomes a hard blocker on positive evidence: mandatory residency,
  work authorization, hiring-region limits, citizenship/clearance, OR a required
  physical workplace outside the candidate's accepted commuting range when the
  candidate does not relocate. Phrases such as "Location: Brussels", "work from
  the European Commission", required office attendance, or a named client site
  are physical-workplace evidence, not a neutral listing location.
- Mandatory unsupported human language remains a hard blocker.
- Record stated CEFR/language level separately from certification. For example,
  "European level C1 in English is mandatory" means C1 proficiency is mandatory.
  Set `language_required_level` accordingly, but set
  `language_certificate_required=true` only when the vacancy explicitly asks for
  a certificate, certification, credential, diploma, or documentary proof.
- Shifts, weekends and holidays are not rejection criteria.
- Unfamiliar tools, specialist technologies, seniority gaps and different role
  families require AI transferability + learnability assessment before rejection.
- Prefer a good application over unnecessary pre-application employer contact.
- Aggregate Market Insights must come from this same reviewed vacancy batch.
"""

    files: dict[str, bytes] = {
        "README.md": readme.encode("utf-8"),
        "capture/run.json": _json_bytes(capture_payload),
        "capture/pages.json": _json_bytes(page_payload),
        "candidate/job_search_preferences.json": _json_bytes(candidate_payload),
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
        "market_intelligence_authority": "external_ai",
        "jolt_decisions_included": False,
        "jolt_scores_included": False,
        "candidate_context_included": True,
        "market_insights_return_in_same_contract": True,
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
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
