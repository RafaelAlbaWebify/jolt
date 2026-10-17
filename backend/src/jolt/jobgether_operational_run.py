"""Explicit bounded Jobgether supervised evidence import into Review Inbox.

Only --commit persists; the production SQLite file is backed up before any writes.
No eligibility, AI decision or application is inferred.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from jolt.ai_review_opportunity_index import list_ai_review_opportunity_index
from jolt.database import CaptureItem, CaptureRun, create_session_factory
from jolt.infojobs_operational_run import backup_local_database
from jolt.jobgether_preview import jobgether_identity
from jolt.jobgether_supervised_stage import stage_supervised_batch
from jolt.supervised_source_promotion import promote_supervised_item


def validated_offers(report: dict) -> list[dict]:
    offers = report.get("offers")
    if report.get("source") != "jobgether" or not isinstance(offers, list):
        raise ValueError("Expected supervised Jobgether evidence")
    if not 1 <= len(offers) <= 5:
        raise ValueError("Expected at most five supervised offers")
    accepted = []
    seen: set[str] = set()
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        identifier = offer.get("source_job_id")
        url = offer.get("url")
        if (
            offer.get("status") != "extracted_unverified"
            or offer.get("mismatches")
            or not isinstance(identifier, str)
            or not isinstance(url, str)
            or jobgether_identity(url) != identifier
            or identifier in seen
            or not isinstance(offer.get("title"), str)
            or not offer["title"].strip()
            or not isinstance(offer.get("company"), str)
            or not offer["company"].strip()
            or not isinstance(offer.get("description"), str)
            or len(offer["description"].strip()) < 150
        ):
            continue
        seen.add(identifier)
        accepted.append(offer)
    return accepted


def import_report(session, report: dict) -> dict:
    accepted = validated_offers(report)
    if not accepted:
        raise ValueError("No Jobgether offers have a complete, consistent description")
    staged = stage_supervised_batch(session, {**report, "offers": accepted})
    identities = [offer["source_job_id"] for offer in accepted]
    items = session.scalars(
        select(CaptureItem)
        .join(CaptureRun, CaptureItem.capture_run_id == CaptureRun.id)
        .where(CaptureRun.source == "jobgether", CaptureItem.source_job_id.in_(identities))
    ).all()
    by_identity = {}
    for item in items:
        previous = by_identity.get(item.source_job_id)
        if (
            previous is None
            or item.capture_run_id == staged["capture_run_id"]
            or (item.posting_id and not previous.posting_id)
        ):
            by_identity[item.source_job_id] = item
    if any(identifier not in by_identity for identifier in identities):
        raise ValueError("Missing preserved Jobgether source evidence")
    imported = []
    for identifier in identities:
        imported.append(promote_supervised_item(session, by_identity[identifier].id))
    inbox = {entry.posting_id for entry in list_ai_review_opportunity_index(session)}
    if any(item["posting_id"] not in inbox for item in imported):
        raise ValueError("Jobgether evidence not visible in Review Inbox")
    return {
        **staged,
        "review_inbox_verified": len(imported),
        "newly_imported": sum(item["status"] == "imported_for_review" for item in imported),
        "work_from_spain_verified": False,
        "ai_review_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument(
        "--backup-dir", type=Path, default=Path.home() / "Downloads" / "JOLT_BACKUPS"
    )
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not validated_offers(report):
        parser.error("No complete Jobgether offers in report")
    backup = str(backup_local_database(args.backup_dir)) if args.commit else None
    factory = create_session_factory()
    with factory() as session:
        try:
            result = import_report(session, report)
            if args.commit:
                session.commit()
            else:
                session.rollback()
        except Exception:
            session.rollback()
            raise
    output = {**result, "committed": args.commit, "backup": backup}
    rendered = json.dumps(output, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
