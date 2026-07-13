from __future__ import annotations

import csv
import hashlib
import io
import json
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.analysis_pack import build_analysis_pack as build_base_analysis_pack
from jolt.application_readiness import ApplicationReadiness
from jolt.database import CaptureItem, CapturePage, CaptureRun
from jolt.opportunity_workbench import list_opportunity_workbench


def _csv_bytes(rows: list[dict[str, object]], fieldnames: list[str]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _capture_data(session: Session) -> dict[str, list[dict[str, object]]]:
    runs = session.scalars(select(CaptureRun).order_by(CaptureRun.started_at)).all()
    pages = session.scalars(select(CapturePage).order_by(CapturePage.page_number)).all()
    items = session.scalars(select(CaptureItem).order_by(CaptureItem.source_job_id)).all()
    return {
        "capture_runs": [
            {
                "id": item.id,
                "source": item.source,
                "mode": item.mode,
                "status": item.status,
                "search_url": item.search_url,
                "warnings": json.loads(item.warnings_json),
                "started_at": item.started_at.isoformat(),
                "completed_at": item.completed_at.isoformat() if item.completed_at else None,
            }
            for item in runs
        ],
        "capture_pages": [
            {
                "id": item.id,
                "capture_run_id": item.capture_run_id,
                "page_number": item.page_number,
                "visible_job_ids": json.loads(item.visible_job_ids_json),
                "next_control_present": item.next_control_present,
                "next_control_enabled": item.next_control_enabled,
            }
            for item in pages
        ],
        "capture_items": [
            {
                "id": item.id,
                "capture_run_id": item.capture_run_id,
                "source_job_id": item.source_job_id,
                "source_url": item.source_url,
                "title": item.title,
                "company": item.company,
                "location": item.location,
                "detail_status": item.detail_status,
                "verification_reasons": json.loads(item.verification_reasons_json),
                "source_document_id": item.source_document_id,
                "posting_id": item.posting_id,
            }
            for item in items
        ],
    }


def _readiness_data(session: Session) -> list[dict[str, object]]:
    list_opportunity_workbench(session)
    reports = session.scalars(
        select(ApplicationReadiness).order_by(ApplicationReadiness.created_at)
    ).all()
    rows: list[dict[str, object]] = []
    for report in reports:
        payload = json.loads(report.report_json)
        rows.append(
            {
                "id": report.id,
                "posting_id": report.posting_id,
                "profile_version_id": report.profile_version_id,
                "engine_version": report.engine_version,
                "priority": report.priority,
                "readiness_score": report.readiness_score,
                "evidence_matches": payload.get("evidence_matches", []),
                "credibility_warnings": payload.get("credibility_warnings", []),
                "cv_tailoring_points": payload.get("cv_tailoring_points", []),
                "talking_points": payload.get("talking_points", []),
                "interview_questions": payload.get("interview_questions", []),
                "revision_topics": payload.get("revision_topics", []),
                "checklist": payload.get("checklist", []),
                "created_at": report.created_at.isoformat(),
            }
        )
    return rows


def build_analysis_pack(session: Session) -> bytes:
    capture_data = _capture_data(session)
    readiness_reports = _readiness_data(session)
    with ZipFile(io.BytesIO(build_base_analysis_pack(session))) as base_archive:
        files = {
            name: base_archive.read(name)
            for name in base_archive.namelist()
            if name != "manifest.json"
        }

    dataset = json.loads(files["data/full_dataset.json"])
    dataset["data"].update(capture_data)
    dataset["data"]["application_readiness_reports"] = readiness_reports
    files["data/full_dataset.json"] = json.dumps(
        dataset, indent=2, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")

    runs = capture_data["capture_runs"]
    items = capture_data["capture_items"]
    files["data/capture_runs.csv"] = _csv_bytes(
        runs,
        ["id", "source", "mode", "status", "search_url", "started_at", "completed_at"],
    )
    files["data/capture_items.csv"] = _csv_bytes(
        items,
        [
            "id",
            "capture_run_id",
            "source_job_id",
            "source_url",
            "title",
            "company",
            "location",
            "detail_status",
            "source_document_id",
            "posting_id",
        ],
    )
    files["data/application_readiness_reports.csv"] = _csv_bytes(
        readiness_reports,
        [
            "id",
            "posting_id",
            "profile_version_id",
            "engine_version",
            "priority",
            "readiness_score",
            "created_at",
        ],
    )

    rejected = sum(item["detail_status"] != "verified" for item in items)
    summary = files["README.md"].decode("utf-8")
    summary = summary.replace(
        "## Dataset\n\n",
        "## Dataset\n\n"
        f"- Capture runs: {len(runs)}\n"
        f"- Capture items: {len(items)}\n"
        f"- Rejected capture items: {rejected}\n"
        f"- Application readiness reports: {len(readiness_reports)}\n",
    )
    files["README.md"] = summary.encode("utf-8")

    manifest = {
        "pack_version": dataset["pack_version"],
        "generated_at": dataset["generated_at"],
        "files": {
            name: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            for name, content in sorted(files.items())
        },
    }
    files["manifest.json"] = json.dumps(
        manifest, indent=2, ensure_ascii=False, sort_keys=True
    ).encode("utf-8")

    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in sorted(files.items()):
            archive.writestr(name, content)
    return output.getvalue()
