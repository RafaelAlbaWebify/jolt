from __future__ import annotations

import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.application_readiness import (
    PROFILE_VERSION_ID,
    READINESS_ENGINE_VERSION,
    ApplicationReadiness,
    analyze_readiness,
    readiness_payload,
)
from jolt.database import Posting, utc_now


def _get_posting(session: Session, posting_id: str) -> Posting:
    posting = session.get(Posting, posting_id)
    if posting is None:
        raise LookupError(f"Posting {posting_id} was not found.")
    return posting


def list_readiness_history(session: Session, posting_id: str) -> list[dict[str, object]]:
    _get_posting(session, posting_id)
    reports = session.scalars(
        select(ApplicationReadiness)
        .where(ApplicationReadiness.posting_id == posting_id)
        .order_by(ApplicationReadiness.created_at.desc())
    ).all()
    return [
        {
            **readiness_payload(report),
            "created_at": report.created_at.isoformat(),
            "is_current": index == 0,
        }
        for index, report in enumerate(reports)
    ]


def refresh_readiness_report(session: Session, posting_id: str) -> dict[str, object]:
    posting = _get_posting(session, posting_id)
    previous = session.scalar(
        select(ApplicationReadiness)
        .where(ApplicationReadiness.posting_id == posting_id)
        .order_by(ApplicationReadiness.created_at.desc())
    )
    analysis = analyze_readiness(posting)
    report_data = analysis.as_dict()
    report_data.update(
        {
            "refresh_reason": "manual_recalculation",
            "supersedes_report_id": previous.id if previous else None,
        }
    )
    report = ApplicationReadiness(
        id=str(uuid4()),
        posting_id=posting.id,
        profile_version_id=PROFILE_VERSION_ID,
        engine_version=READINESS_ENGINE_VERSION,
        priority=analysis.priority,
        readiness_score=analysis.readiness_score,
        report_json=json.dumps(report_data, sort_keys=True),
        created_at=utc_now(),
    )
    session.add(report)
    session.commit()
    return {
        **readiness_payload(report),
        "created_at": report.created_at.isoformat(),
        "is_current": True,
    }
