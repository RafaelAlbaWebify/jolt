"""Commit bounded InfoJobs observations and import only their new Postings for AI review.

No AI decision, application, browser navigation, or source eligibility claim is made.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from jolt.ai_review_opportunity_index import list_ai_review_opportunity_index
from jolt.database import CaptureItem, CaptureRun, create_session_factory, default_database_url
from jolt.infojobs_observations import inspect_offer, stage_report
from jolt.supervised_source_promotion import promote_supervised_item


def backup_local_database(directory: Path) -> Path:
    """Create a consistent SQLite backup before any database writes."""
    url = default_database_url()
    if not url.startswith("sqlite:///"):
        raise ValueError("Only local SQLite databases are supported by this operator workflow")
    database = Path(url[len("sqlite:///") :])
    if not database.is_file():
        raise FileNotFoundError(f"JOLT database not found: {database}")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"jolt-before-infojobs-{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(str(database)) as source, sqlite3.connect(str(destination)) as target:
        source.backup(target)
    return destination


def import_report(session, report: dict) -> dict[str, object]:
    """Stage and promote only offers in this report; caller owns commit/rollback."""
    staged = stage_report(session, report)
    inspected = [inspect_offer(offer) for offer in report["offers"]]
    identities = [row["source_job_id"] for row in inspected]
    items = session.scalars(
        select(CaptureItem)
        .join(CaptureRun, CaptureRun.id == CaptureItem.capture_run_id)
        .where(CaptureRun.source == "infojobs", CaptureItem.source_job_id.in_(identities))
    ).all()
    by_identity: dict[str, CaptureItem] = {}
    for item in items:
        previous = by_identity.get(item.source_job_id)
        if (
            previous is None
            or (staged["capture_run_id"] and item.capture_run_id == staged["capture_run_id"])
            or (item.posting_id is not None and previous.posting_id is None)
        ):
            by_identity[item.source_job_id] = item
    if len(by_identity) != len(identities):
        raise ValueError("Not all InfoJobs capture items were staged")

    imported = []
    already_imported = []
    for identity in identities:
        item = by_identity[identity]
        # Existing unpromoted observations may originate from a previous run.
        result = promote_supervised_item(session, item.id)
        if result["status"] == "imported_for_review":
            imported.append(result["posting_id"])
        else:
            already_imported.append(result["posting_id"])

    inbox = {entry.posting_id: entry for entry in list_ai_review_opportunity_index(session)}
    verified = []
    for posting_id in imported + already_imported:
        item = inbox.get(posting_id)
        if item is None:
            raise ValueError(f"Posting not visible in Review Inbox: {posting_id}")
        if item.ai_review_status not in {"awaiting_ai_review", "reviewed"}:
            raise ValueError(f"Unexpected AI review state for {posting_id}")
        verified.append(
            {
                "posting_id": posting_id,
                "title": item.title,
                "company": item.company,
                "ai_review_status": item.ai_review_status,
            }
        )
    return {
        **staged,
        "newly_imported": len(imported),
        "already_imported": len(already_imported),
        "review_inbox_verified": len(verified),
        "postings": verified,
        "work_from_spain_verified": False,
        "ai_review_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--commit", action="store_true")
    parser.add_argument(
        "--backup-dir", type=Path, default=Path.home() / "Downloads" / "JOLT_BACKUPS"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        parser.error("Expected a JSON report object")

    # Validate whole report before creating any backup or opening write transaction.
    offers = report.get("offers")
    if not isinstance(offers, list) or not 1 <= len(offers) <= 5:
        parser.error("Expected 1..5 extracted InfoJobs offers")
    for offer in offers:
        inspect_offer(offer)

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
