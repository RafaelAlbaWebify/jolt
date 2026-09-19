from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from sqlalchemy import select

from jolt.backup import create_backup, inspect_backup, restore_backup
from jolt.database import Application, CaptureItem, CaptureRun, Posting, create_session_factory
from jolt.retention_ownership import (
    build_guarded_retention_cleanup_plan,
    execute_guarded_retention_cleanup,
)

CORE_TABLES = (
    "source_documents",
    "postings",
    "review_decisions",
    "applications",
    "application_events",
    "outcomes",
    "capture_runs",
    "capture_items",
    "market_intelligence_observations",
    "ai_reviews",
)


def _counts(path: Path) -> dict[str, int]:
    result: dict[str, int] = {}
    with sqlite3.connect(path) as connection:
        existing = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for table in CORE_TABLES:
            if table not in existing:
                continue
            value = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
            result[table] = int(value[0] if value else 0)
    return result


def _choose_superseded_posting(session) -> Posting:
    current = session.scalar(
        select(CaptureRun)
        .where(CaptureRun.status != "archived")
        .order_by(CaptureRun.started_at.desc(), CaptureRun.id.desc())
        .limit(1)
    )
    if current is None:
        raise RuntimeError("No current capture run exists.")

    row = session.execute(
        select(Posting)
        .join(CaptureItem, CaptureItem.posting_id == Posting.id)
        .where(CaptureItem.capture_run_id != current.id)
        .order_by(Posting.created_at.asc(), Posting.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        raise RuntimeError("No posting from a superseded capture is available for retention rehearsal.")
    return row


def _retention_rehearsal(restored_database: Path) -> dict[str, object]:
    database_url = f"sqlite:///{restored_database.as_posix()}"
    factory = create_session_factory(database_url)

    with factory() as session:
        posting = _choose_superseded_posting(session)

        existing_application = session.scalar(
            select(Application).where(Application.posting_id == posting.id).limit(1)
        )
        fixture_created = existing_application is None

        if existing_application is None:
            now = datetime.now(UTC)
            application = Application(
                id=str(uuid4()),
                posting_id=posting.id,
                status="submitted",
                application_url="",
                resume_used="acceptance-rehearsal",
                notes="Temporary retention acceptance fixture on restored database copy.",
                created_at=now,
                updated_at=now,
            )
            session.add(application)
            session.commit()
        else:
            application = existing_application

        application_id = application.id
        posting_id = posting.id

        plan = build_guarded_retention_cleanup_plan(session)
        if bool(plan["blocked"]):
            raise RuntimeError(
                "Guarded retention cleanup is blocked on the restored production copy: "
                + "; ".join(str(value) for value in plan["blocked_reasons"])
            )

        if int(plan["retained_posting_count"]) < 1:
            raise RuntimeError("Retention plan did not recognize the application-owned posting as retained.")

        confirmation = str(plan["required_confirmation"])
        cleanup = execute_guarded_retention_cleanup(session, confirmation=confirmation)
        session.commit()

        retained_application = session.get(Application, application_id)
        retained_posting = session.get(Posting, posting_id)

        if retained_application is None:
            raise RuntimeError("Retention cleanup deleted the pursued/submitted application.")
        if retained_posting is None:
            raise RuntimeError("Retention cleanup deleted the posting owned by the application.")

        return {
            "fixture_created_on_restored_copy": fixture_created,
            "protected_application_id": application_id,
            "protected_posting_id": posting_id,
            "plan": plan,
            "cleanup": cleanup,
            "application_survived": True,
            "posting_survived": True,
        }


def run(database: Path, output_dir: Path) -> dict[str, object]:
    database = database.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    backup_path = output_dir / f"JOLT_ACCEPTANCE_BACKUP_{stamp}.zip"
    restored_database = output_dir / f"JOLT_ACCEPTANCE_RESTORE_{stamp}.db"

    source_counts = _counts(database)
    created_manifest = create_backup(database, backup_path)
    verified_manifest = inspect_backup(backup_path)
    restored_manifest = restore_backup(backup_path, restored_database)
    restored_counts_before_cleanup = _counts(restored_database)

    if created_manifest != verified_manifest or created_manifest != restored_manifest:
        raise RuntimeError("Backup create/verify/restore manifests do not match.")
    if source_counts != restored_counts_before_cleanup:
        raise RuntimeError("Restored database core record counts differ from the active database.")

    retention = _retention_rehearsal(restored_database)
    restored_counts_after_cleanup = _counts(restored_database)

    report = {
        "acceptance_type": "jolt_real_prospect_rehearsal",
        "performed_at": datetime.now(UTC).isoformat(),
        "active_database": str(database),
        "backup_path": str(backup_path),
        "restored_database": str(restored_database),
        "backup_manifest": created_manifest,
        "source_counts": source_counts,
        "restored_counts_before_cleanup": restored_counts_before_cleanup,
        "restored_counts_after_cleanup": restored_counts_after_cleanup,
        "backup_restore_passed": True,
        "retention_protection_passed": True,
        "retention": retention,
        "active_database_modified": False,
        "passed": True,
    }

    report_path = output_dir / f"JOLT_REAL_PROSPECT_ACCEPTANCE_{stamp}.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a non-destructive JOLT real-prospect acceptance rehearsal: "
            "backup -> verify -> restore, then guarded retention cleanup on the restored copy."
        )
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=REPO_ROOT / "backend" / "data" / "jolt.db",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.home() / "Downloads" / "JOLT_ACCEPTANCE",
    )
    args = parser.parse_args()

    report = run(args.database, args.output_dir)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
