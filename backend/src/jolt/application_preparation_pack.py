from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.orm import Session

from jolt.application_readiness import ensure_readiness_report, readiness_payload
from jolt.database import Posting


def _markdown(posting: Posting, readiness: dict[str, object]) -> str:
    def section(title: str, key: str) -> str:
        values = readiness.get(key, [])
        if not isinstance(values, list) or not values:
            return f"## {title}\n\nNo evidence recorded.\n"
        lines = "\n".join(f"- {value}" for value in values)
        return f"## {title}\n\n{lines}\n"

    return "\n".join(
        [
            f"# JOLT Application Preparation Pack\n\n## Opportunity\n\n- Title: {posting.title}\n- Company: {posting.company}\n- Location: {posting.location}\n- Source: {posting.canonical_url or posting.source_document.source_url}\n",
            f"## Readiness\n\n- Priority: {readiness['priority']}\n- Score: {readiness['readiness_score']}/100\n- Profile: {readiness['profile_version_id']}\n- Engine: {readiness['engine_version']}\n",
            section("Evidence to use", "evidence_matches"),
            section("Credibility warnings", "credibility_warnings"),
            section("CV tailoring points", "cv_tailoring_points"),
            section("Application talking points", "talking_points"),
            section("Likely interview questions", "interview_questions"),
            section("Technical revision topics", "revision_topics"),
            section("Application checklist", "checklist"),
            "## Safety boundary\n\nUse only evidence that is accurate and supportable. This pack does not submit an application, modify a CV, or contact a recruiter.\n",
        ]
    )


def build_application_preparation_pack(session: Session, posting_id: str) -> bytes:
    posting = session.get(Posting, posting_id)
    if posting is None:
        raise LookupError("Posting not found.")

    report = ensure_readiness_report(session, posting)
    readiness = readiness_payload(report)
    payload = {
        "posting": {
            "posting_id": posting.id,
            "title": posting.title,
            "company": posting.company,
            "location": posting.location,
            "source_url": posting.canonical_url or posting.source_document.source_url,
        },
        "readiness": readiness,
    }

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("application-preparation.md", _markdown(posting, readiness))
        archive.writestr(
            "application-preparation.json",
            json.dumps(payload, indent=2, ensure_ascii=True),
        )
        archive.writestr(
            "README.txt",
            (
                "JOLT application preparation pack\n\n"
                "Review the Markdown and JSON files before applying.\n"
                "No application, CV edit, or recruiter contact was performed.\n"
            ),
        )
    return buffer.getvalue()
