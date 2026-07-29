from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select

from jolt.capture_deletion import delete_capture_run_with_unclassified_opportunities
from jolt.capture_workflow import list_capture_runs
from jolt.database import CaptureItem, CaptureRun, create_session_factory
from jolt.opportunity_index import list_opportunity_index


def _default_db_url() -> str:
    return f"sqlite:///{(Path('backend') / 'data' / 'jolt.db').as_posix()}"


def _run_payload(session, run: CaptureRun) -> dict[str, Any]:
    items = session.scalars(select(CaptureItem).where(CaptureItem.capture_run_id == run.id)).all()
    return {
        "capture_run_id": run.id,
        "source": run.source,
        "mode": run.mode,
        "status": run.status,
        "search_url": run.search_url,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "item_count": len(items),
        "posting_count": len([item for item in items if item.posting_id]),
    }


def audit_imported_batches(database_url: str) -> dict[str, Any]:
    session_factory = create_session_factory(database_url)
    session = session_factory()
    try:
        runs = session.scalars(select(CaptureRun).order_by(CaptureRun.started_at.desc())).all()
        opportunities = list_opportunity_index(session)
        return {
            "database_url": database_url,
            "capture_run_count": len(runs),
            "pending_opportunity_count": len(opportunities),
            "capture_runs": [_run_payload(session, run) for run in runs],
        }
    finally:
        session.close()


def delete_imported_batches(database_url: str) -> dict[str, Any]:
    session_factory = create_session_factory(database_url)
    session = session_factory()
    try:
        runs = session.scalars(select(CaptureRun).order_by(CaptureRun.started_at.desc())).all()
    finally:
        session.close()

    results: list[dict[str, Any]] = []
    for run in runs:
        session = session_factory()
        try:
            result = delete_capture_run_with_unclassified_opportunities(session, run.id)
            results.append(result.model_dump(mode="json"))
        finally:
            session.close()

    session = session_factory()
    try:
        remaining_runs = list_capture_runs(session)
        remaining_opportunities = list_opportunity_index(session)
        return {
            "deleted_capture_run_count": len(results),
            "deleted": results,
            "remaining_capture_run_count": len(remaining_runs),
            "remaining_pending_opportunity_count": len(remaining_opportunities),
        }
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preview or delete imported job capture batches that feed the Opportunities review inbox. "
            "By default this is read-only. Use --apply to delete normal capture_runs/capture_items and "
            "their still-unclassified imported opportunities. Reviewed/applied postings are protected."
        )
    )
    parser.add_argument("--database-url", default=_default_db_url())
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    before = audit_imported_batches(args.database_url)
    payload: dict[str, Any] = {"mode": "preview", "before": before}
    if args.apply:
        payload["mode"] = "apply"
        payload["after"] = delete_imported_batches(args.database_url)

    text = json.dumps(payload, indent=2, ensure_ascii=False)
    print(text)

    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "jolt_imported_capture_batch_cleanup.json").write_text(text, encoding="utf-8")

    if not args.apply:
        print("\nPreview only. Re-run with --apply to delete these imported capture batches.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
