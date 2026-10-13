"""Stage a supervised Jobgether JSON report as unverified capture evidence.

Only --commit commits the caller's transaction; never creates Postings or Applications.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.capture_artifacts import CaptureArtifact, stage_capture_artifact
from jolt.database import CaptureItem, CapturePage, CaptureRun, create_session_factory, utc_now
from jolt.jobgether_preview import jobgether_identity


def stage_supervised_batch(session: Session, report: dict) -> dict[str, object]:
    """Stage reliable, previously unseen identities from a bounded supervised report."""
    offers = report.get("offers")
    search_url = report.get("search_url")
    if (
        report.get("source") != "jobgether"
        or report.get("mode") != "supervised_search_tab_read_only"
        or not isinstance(search_url, str)
        or not search_url.startswith("https://jobgether.com/")
        or not isinstance(offers, list)
        or not 1 <= len(offers) <= 5
    ):
        raise ValueError("Expected a bounded supervised Jobgether capture report")
    accepted: list[dict] = []
    seen: set[str] = set()
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        identifier = offer.get("source_job_id")
        url = offer.get("url")
        if (
            not isinstance(identifier, str)
            or not isinstance(url, str)
            or jobgether_identity(url) != identifier
            or identifier in seen
            or offer.get("status") != "extracted_unverified"
            or offer.get("mismatches")
        ):
            continue
        seen.add(identifier)
        accepted.append(offer)
    if not accepted:
        return {
            "capture_run_id": None,
            "staged_unverified": 0,
            "already_known": 0,
            "reliable_ids": 0,
        }
    existing = set(
        session.scalars(
            select(CaptureItem.source_job_id)
            .join(CaptureRun, CaptureItem.capture_run_id == CaptureRun.id)
            .where(CaptureRun.source == "jobgether")
            .where(CaptureItem.source_job_id.in_(seen))
        ).all()
    )
    novel = [offer for offer in accepted if offer["source_job_id"] not in existing]
    previous_items = session.scalars(
        select(CaptureItem)
        .join(CaptureRun, CaptureItem.capture_run_id == CaptureRun.id)
        .where(CaptureRun.source == "jobgether")
        .where(CaptureItem.source_job_id.in_(seen))
    ).all()
    item_ids = [item.id for item in previous_items]
    complete_previous_ids: set[str] = set()
    if item_ids:
        artifacts = session.scalars(
            select(CaptureArtifact)
            .where(CaptureArtifact.capture_item_id.in_(item_ids))
            .where(CaptureArtifact.artifact_type == "jobgether_browser_json")
        ).all()
        id_by_item = {item.id: item.source_job_id for item in previous_items}
        for artifact in artifacts:
            try:
                previous = json.loads(artifact.raw_payload)
            except (ValueError, TypeError):
                continue
            if (
                isinstance(previous, dict)
                and isinstance(previous.get("description"), str)
                and len(previous["description"].strip()) >= 150
            ):
                complete_previous_ids.add(id_by_item[artifact.capture_item_id])
    improved = [
        offer
        for offer in accepted
        if offer["source_job_id"] in existing
        and offer["source_job_id"] not in complete_previous_ids
        and isinstance(offer.get("description"), str)
        and len(offer["description"].strip()) >= 150
    ]
    staged_offers = novel + improved
    if not staged_offers:
        return {
            "capture_run_id": None,
            "staged_unverified": 0,
            "already_known": len(accepted),
            "reliable_ids": len(accepted),
        }
    now = utc_now()
    run = CaptureRun(
        id=str(uuid4()),
        source="jobgether",
        mode="supervised_browser_observation",
        status="completed",
        search_url=search_url,
        warnings_json="[]",
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
            visible_job_ids_json=json.dumps([x["source_job_id"] for x in accepted]),
            next_control_present=False,
            next_control_enabled=False,
        )
    )
    for offer in staged_offers:
        reasons = ["Supervised JobPosting extraction; source and eligibility not verified"]
        if not offer.get("spain_declared"):
            reasons.append("spain_not_declared")
        countries = offer.get("applicant_countries")
        if isinstance(countries, list) and len(countries) > 100:
            reasons.append("overbroad_country_metadata")
        item = CaptureItem(
            id=str(uuid4()),
            capture_run_id=run.id,
            source_job_id=offer["source_job_id"],
            source_url=offer["url"],
            title=str(offer.get("title") or ""),
            company=str(offer.get("company") or ""),
            location="",
            detail_status="observed_unverified",
            verification_reasons_json=json.dumps(reasons),
            source_document_id=None,
            posting_id=None,
        )
        session.add(item)
        session.flush()
        stage_capture_artifact(
            session,
            capture_item_id=item.id,
            artifact_type="jobgether_browser_json",
            content_type="application/json",
            raw_payload=json.dumps(offer, ensure_ascii=False, sort_keys=True),
        )
    return {
        "capture_run_id": run.id,
        "reliable_ids": len(accepted),
        "staged_unverified": len(staged_offers),
        "new_source_id_count": len(novel),
        "refreshed_evidence": len(improved),
        "already_known": len(accepted) - len(staged_offers),
    }


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
            result = stage_supervised_batch(session, report)
            if args.commit:
                session.commit()
            else:
                session.rollback()
        except Exception:
            session.rollback()
            raise
    print(
        json.dumps(
            {**result, "committed": args.commit and result["capture_run_id"] is not None}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
