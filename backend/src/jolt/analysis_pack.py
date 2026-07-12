from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    Application,
    ApplicationEvent,
    Evaluation,
    Outcome,
    Posting,
    ProfileVersion,
    ReviewDecision,
    SourceDocument,
)

PACK_VERSION = "1.0"


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _json_bytes(value: object) -> bytes:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True).encode("utf-8")


def _csv_bytes(rows: list[dict[str, object]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _collect(session: Session) -> dict[str, list[dict[str, object]]]:
    sources = session.scalars(select(SourceDocument).order_by(SourceDocument.captured_at)).all()
    profiles = session.scalars(select(ProfileVersion).order_by(ProfileVersion.created_at)).all()
    postings = session.scalars(select(Posting).order_by(Posting.created_at)).all()
    evaluations = session.scalars(select(Evaluation).order_by(Evaluation.created_at)).all()
    reviews = session.scalars(select(ReviewDecision).order_by(ReviewDecision.reviewed_at)).all()
    applications = session.scalars(select(Application).order_by(Application.created_at)).all()
    events = session.scalars(select(ApplicationEvent).order_by(ApplicationEvent.occurred_at)).all()
    outcomes = session.scalars(select(Outcome).order_by(Outcome.recorded_at)).all()

    return {
        "source_documents": [
            {
                "id": item.id,
                "source_type": item.source_type,
                "source_url": item.source_url,
                "raw_text": item.raw_text,
                "content_hash": item.content_hash,
                "captured_at": _iso(item.captured_at),
            }
            for item in sources
        ],
        "profile_versions": [
            {
                "id": item.id,
                "profile_id": item.profile_id,
                "version": item.version,
                "configuration": json.loads(item.configuration_json),
                "created_at": _iso(item.created_at),
            }
            for item in profiles
        ],
        "postings": [
            {
                "id": item.id,
                "source_document_id": item.source_document_id,
                "canonical_url": item.canonical_url,
                "title": item.title,
                "company": item.company,
                "location": item.location,
                "description": item.description,
                "identity_status": item.identity_status,
                "created_at": _iso(item.created_at),
            }
            for item in postings
        ],
        "evaluations": [
            {
                "id": item.id,
                "posting_id": item.posting_id,
                "profile_version_id": item.profile_version_id,
                "engine_version": item.engine_version,
                "recommendation": item.recommendation,
                "confidence": item.confidence,
                "ranking_score": item.ranking_score,
                "reasons": json.loads(item.reasons_json),
                "created_at": _iso(item.created_at),
            }
            for item in evaluations
        ],
        "review_decisions": [
            {
                "id": item.id,
                "posting_id": item.posting_id,
                "evaluation_id": item.evaluation_id,
                "decision": item.decision,
                "reason_code": item.reason_code,
                "notes": item.notes,
                "evaluation_overridden": item.evaluation_overridden,
                "reviewed_at": _iso(item.reviewed_at),
            }
            for item in reviews
        ],
        "applications": [
            {
                "id": item.id,
                "posting_id": item.posting_id,
                "status": item.status,
                "application_url": item.application_url,
                "resume_used": item.resume_used,
                "notes": item.notes,
                "created_at": _iso(item.created_at),
                "updated_at": _iso(item.updated_at),
            }
            for item in applications
        ],
        "application_events": [
            {
                "id": item.id,
                "application_id": item.application_id,
                "event_type": item.event_type,
                "from_status": item.from_status,
                "to_status": item.to_status,
                "notes": item.notes,
                "occurred_at": _iso(item.occurred_at),
            }
            for item in events
        ],
        "outcomes": [
            {
                "id": item.id,
                "posting_id": item.posting_id,
                "application_id": item.application_id,
                "outcome_type": item.outcome_type,
                "stage_reached": item.stage_reached,
                "reason_code": item.reason_code,
                "notes": item.notes,
                "recorded_at": _iso(item.recorded_at),
            }
            for item in outcomes
        ],
    }


def _summary(data: dict[str, list[dict[str, object]]], generated_at: str) -> str:
    evaluations = data["evaluations"]
    reviews = data["review_decisions"]
    applications = data["applications"]
    outcomes = data["outcomes"]

    def count(rows: list[dict[str, object]], key: str, value: str) -> int:
        return sum(1 for row in rows if row.get(key) == value)

    lines = [
        "# JOLT analysis pack",
        "",
        f"Generated: {generated_at}",
        f"Pack format: {PACK_VERSION}",
        "",
        "## Dataset",
        "",
        f"- Captured source documents: {len(data['source_documents'])}",
        f"- Canonical postings: {len(data['postings'])}",
        f"- Evaluations: {len(evaluations)}",
        f"- Human review decisions: {len(reviews)}",
        f"- Applications: {len(applications)}",
        f"- Application events: {len(data['application_events'])}",
        f"- Outcomes: {len(outcomes)}",
        "",
        "## Decision overview",
        "",
        f"- Machine pursue recommendations: {count(evaluations, 'recommendation', 'pursue')}",
        f"- Human pursue decisions: {count(reviews, 'decision', 'pursue')}",
        f"- Evaluation overrides: {sum(1 for row in reviews if row['evaluation_overridden'])}",
        f"- Submitted applications: {sum(1 for row in applications if row['status'] != 'preparing')}",
        f"- Employer rejections: {count(outcomes, 'outcome_type', 'rejected_by_employer')}",
        f"- Accepted offers: {count(outcomes, 'outcome_type', 'offer_accepted')}",
        "",
        "## How to use this pack",
        "",
        "Use `data/full_dataset.json` as the source of truth. CSV files are convenience views. "
        "Do not infer rule quality from small samples. Proposed changes belong in "
        "`feedback/feedback_template.json` and require human approval before implementation.",
        "",
    ]
    return "\n".join(lines)


def build_analysis_pack(session: Session) -> bytes:
    generated_at = datetime.now(UTC).isoformat()
    data = _collect(session)
    files: dict[str, bytes] = {
        "README.md": _summary(data, generated_at).encode("utf-8"),
        "data/full_dataset.json": _json_bytes(
            {"pack_version": PACK_VERSION, "generated_at": generated_at, "data": data}
        ),
        "data/opportunities.csv": _csv_bytes(
            data["postings"],
            [
                "id",
                "source_document_id",
                "canonical_url",
                "title",
                "company",
                "location",
                "identity_status",
                "created_at",
            ],
        ),
        "data/evaluations.csv": _csv_bytes(
            data["evaluations"],
            [
                "id",
                "posting_id",
                "profile_version_id",
                "engine_version",
                "recommendation",
                "confidence",
                "ranking_score",
                "created_at",
            ],
        ),
        "data/reviews.csv": _csv_bytes(
            data["review_decisions"],
            [
                "id",
                "posting_id",
                "evaluation_id",
                "decision",
                "reason_code",
                "notes",
                "evaluation_overridden",
                "reviewed_at",
            ],
        ),
        "data/applications.csv": _csv_bytes(
            data["applications"],
            [
                "id",
                "posting_id",
                "status",
                "application_url",
                "resume_used",
                "notes",
                "created_at",
                "updated_at",
            ],
        ),
        "data/application_events.csv": _csv_bytes(
            data["application_events"],
            [
                "id",
                "application_id",
                "event_type",
                "from_status",
                "to_status",
                "notes",
                "occurred_at",
            ],
        ),
        "data/outcomes.csv": _csv_bytes(
            data["outcomes"],
            [
                "id",
                "posting_id",
                "application_id",
                "outcome_type",
                "stage_reached",
                "reason_code",
                "notes",
                "recorded_at",
            ],
        ),
        "feedback/feedback_template.json": _json_bytes(
            {
                "pack_version": PACK_VERSION,
                "analysis_summary": "",
                "profile_recommendations": [],
                "product_recommendations": [],
                "data_quality_findings": [],
                "approval_required": True,
            }
        ),
    }
    manifest = {
        "pack_version": PACK_VERSION,
        "generated_at": generated_at,
        "files": {
            name: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            for name, content in sorted(files.items())
        },
    }
    files["manifest.json"] = _json_bytes(manifest)

    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
