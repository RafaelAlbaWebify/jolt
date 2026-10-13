"""Validate and stage bounded InfoJobs browser evidence without promoting postings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import stage_capture_artifact
from jolt.database import CaptureItem, CapturePage, CaptureRun, create_session_factory, utc_now
from jolt.infojobs_browser_probe import is_offer_url

_ID_RE = re.compile(r"/of-i([0-9a-f]{32})(?:/|$)", re.IGNORECASE)


def inspect_offer(offer: dict) -> dict[str, str]:
    """Require original body integrity and extract job-specific text conservatively."""
    url = offer.get("url")
    body = offer.get("body_text")
    title = offer.get("title_observed")
    if not isinstance(url, str) or not is_offer_url(url):
        raise ValueError("untrusted offer URL")
    match = _ID_RE.search(url.split("?", 1)[0])
    if match is None:
        raise ValueError("unsupported canonical InfoJobs identity")
    if offer.get("status") != "extracted_unverified":
        raise ValueError("offer was not extracted")
    if not isinstance(body, str) or not isinstance(title, str):
        raise ValueError("missing title or body")
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != offer.get("body_sha256"):
        raise ValueError("body hash mismatch")
    if not title.strip() or title not in body:
        raise ValueError("title missing from evidence")
    if body.count("\nDescripción\n") != 1:
        raise ValueError("description section ambiguous")
    remainder = body.split("\nDescripción\n", 1)[1]
    if "\nCategoría\n" not in remainder:
        raise ValueError("description ending absent")
    description = remainder.split("\nCategoría\n", 1)[0].strip()
    if len(description) < 150:
        raise ValueError("description too short")
    return {
        "source_job_id": match.group(1).lower(),
        "url": url.split("?", 1)[0],
        "title": title.strip(),
        "description": description,
        "description_sha256": hashlib.sha256(description.encode("utf-8")).hexdigest(),
    }


def stage_report(session: Session, report: dict) -> dict[str, object]:
    offers = report.get("offers")
    search_url = report.get("search_url")
    if (
        report.get("source") != "infojobs"
        or report.get("mode") != "supervised_browser_evidence_read_only"
        or not isinstance(search_url, str)
        or not search_url.startswith("https://www.infojobs.net/ofertas-trabajo/")
        or not isinstance(offers, list)
        or not 1 <= len(offers) <= 5
    ):
        raise ValueError("invalid bounded InfoJobs report")
    checked = [inspect_offer(offer) for offer in offers]
    ids = [job["source_job_id"] for job in checked]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate identities in report")
    existing = set(
        session.scalars(
            select(CaptureItem.source_job_id)
            .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
            .where(CaptureRun.source == "infojobs")
            .where(CaptureItem.source_job_id.in_(ids))
        ).all()
    )
    novel = [(job, offer) for job, offer in zip(checked, offers, strict=True) if job["source_job_id"] not in existing]
    if not novel:
        return {"capture_run_id": None, "reliable_ids": len(ids), "staged_unverified": 0, "already_known": len(ids)}
    now = utc_now()
    run = CaptureRun(
        id=str(uuid4()),
        source="infojobs",
        mode="supervised_browser_observation",
        status="completed",
        search_url=search_url,
        warnings_json=json.dumps(["Observed browser evidence only; description and work eligibility not independently verified"]),
        requested_item_limit=len(offers),
        observed_item_count=len(offers),
        stop_reason="bounded_supervised_report_staged",
        started_at=now,
        completed_at=now,
    )
    session.add(run)
    session.flush()
    session.add(
        CapturePage(
            id=str(uuid4()),
            capture_run_id=run.id,
            page_number=1,
            visible_job_ids_json=json.dumps(ids),
            next_control_present=False,
            next_control_enabled=False,
        )
    )
    for job, offer in novel:
        item = CaptureItem(
            id=str(uuid4()),
            capture_run_id=run.id,
            source_job_id=job["source_job_id"],
            source_url=job["url"],
            title=job["title"],
            company="",
            location="",
            detail_status="observed_unverified",
            verification_reasons_json=json.dumps(["Source job description isolated but not independently verified", "Eligibility from Spain not verified"]),
            source_document_id=None,
            posting_id=None,
        )
        session.add(item)
        session.flush()
        stage_capture_artifact(
            session,
            capture_item_id=item.id,
            artifact_type="infojobs_browser_json",
            content_type="application/json",
            raw_payload=json.dumps({"offer": offer, "isolated_description": job["description"], "description_sha256": job["description_sha256"]}, ensure_ascii=False, sort_keys=True),
        )
    return {"capture_run_id": run.id, "reliable_ids": len(ids), "staged_unverified": len(novel), "already_known": len(ids) - len(novel)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        parser.error("Expected a JSON report object")
    factory = create_session_factory()
    with factory() as session:
        try:
            result = stage_report(session, report)
            if args.commit:
                session.commit()
            else:
                session.rollback()
        except Exception:
            session.rollback()
            raise
    print(json.dumps({**result, "committed": bool(args.commit and result["capture_run_id"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
