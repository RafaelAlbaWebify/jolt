from __future__ import annotations

import json
import zipfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from jolt.database import (
    LinkedInDiscoveryBatch,
    LinkedInDiscoveryBatchSearch,
    utc_now,
)
from jolt.errors import JoltNotFoundError
from jolt.linkedin_capture import linkedin_capture_browser, run_capture_in_context
from jolt.local_linkedin_capture import linkedin_capture_runtime_lock

_FATAL_SESSION_MARKERS = (
    "linkedin authentication_required",
    "linkedin checkpoint",
    "linkedin safety_warning",
    "linkedin network failure",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _profile_dir() -> Path:
    path = _repo_root() / ".jolt" / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _batch_evidence_dir(batch_id: str) -> Path:
    root = _repo_root() / ".jolt" / "discovery-batches" / batch_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _capture_package_metrics(output_zip: Path) -> dict[str, int | str]:
    with zipfile.ZipFile(output_zip) as archive:
        summary = json.loads(archive.read("capture_summary.json"))
        api_result = json.loads(archive.read("api_result.json"))

    items = api_result.get("items", []) or []
    duplicate_count = sum(
        1 for item in items if item.get("identity_status") == "confirmed_duplicate"
    )
    return {
        "capture_run_id": str(api_result.get("capture_run_id", "") or ""),
        "captured_count": int(summary.get("captured_count", 0) or 0),
        "verified_count": int(summary.get("verified_count", 0) or 0),
        "new_posting_count": max(0, len(items) - duplicate_count),
        "duplicate_count": duplicate_count,
    }


def _batch_searches(
    session: Session,
    batch_id: str,
) -> list[LinkedInDiscoveryBatchSearch]:
    return list(
        session.scalars(
            select(LinkedInDiscoveryBatchSearch)
            .where(LinkedInDiscoveryBatchSearch.batch_id == batch_id)
            .order_by(LinkedInDiscoveryBatchSearch.position.asc())
        ).all()
    )


def _is_fatal_session_failure(error: Exception) -> bool:
    message = str(error).casefold()
    return any(marker in message for marker in _FATAL_SESSION_MARKERS)


def _mark_remaining_skipped(
    session: Session,
    searches: list[LinkedInDiscoveryBatchSearch],
    *,
    after_position: int,
    reason: str,
) -> None:
    now = utc_now()
    for search in searches:
        if search.position <= after_position or search.status != "queued":
            continue
        search.status = "skipped"
        search.error = reason
        search.completed_at = now
    session.commit()


def schedule_discovery_batch(session: Session, batch_id: str) -> None:
    batch = session.get(LinkedInDiscoveryBatch, batch_id)
    if batch is None:
        raise JoltNotFoundError("LinkedIn discovery batch was not found.")
    if batch.status != "queued":
        raise ValueError("Only queued LinkedIn discovery batches can be scheduled.")
    active_batch_id = session.scalar(
        select(LinkedInDiscoveryBatch.id)
        .where(
            LinkedInDiscoveryBatch.id != batch_id,
            LinkedInDiscoveryBatch.status.in_(("scheduled", "running")),
        )
        .limit(1)
    )
    if active_batch_id is not None:
        raise ValueError("Another LinkedIn discovery batch is already active.")
    batch.status = "scheduled"
    session.commit()


def mark_discovery_batch_background_failure(
    session: Session,
    batch_id: str,
    error: Exception,
) -> None:
    batch = session.get(LinkedInDiscoveryBatch, batch_id)
    if batch is None:
        return
    if batch.status in {"completed", "completed_with_failures", "failed"}:
        return
    batch.status = "failed"
    batch.completed_at = utc_now()
    searches = _batch_searches(session, batch_id)
    for search in searches:
        if search.status in {"queued", "running"}:
            search.status = "skipped" if search.status == "queued" else "failed"
            search.error = f"Discovery batch background failure: {error}"
            search.completed_at = utc_now()
    session.commit()


def execute_discovery_batch(
    session: Session,
    batch_id: str,
    *,
    api_url: str = "http://127.0.0.1:8000",
    profile_dir: Path | None = None,
) -> None:
    batch = session.get(LinkedInDiscoveryBatch, batch_id)
    if batch is None:
        raise JoltNotFoundError("LinkedIn discovery batch was not found.")
    if batch.status != "scheduled":
        raise ValueError("Only scheduled LinkedIn discovery batches can be started.")

    searches = _batch_searches(session, batch.id)
    if not searches:
        raise ValueError("LinkedIn discovery batch contains no searches.")

    batch.status = "running"
    batch.started_at = utc_now()
    batch.completed_at = None
    session.commit()

    fatal_failure = False
    failed_count = 0
    evidence_dir = _batch_evidence_dir(batch.id)
    browser_profile = profile_dir or _profile_dir()

    try:
        with linkedin_capture_runtime_lock():
            with linkedin_capture_browser(browser_profile) as (context, page):
                for search in searches:
                    search.status = "running"
                    search.started_at = utc_now()
                    search.completed_at = None
                    search.error = ""
                    session.commit()

                    output_zip = evidence_dir / (
                        f"{search.position:02d}_{search.saved_search_id}_capture.zip"
                    )
                    try:
                        run_capture_in_context(
                            context=context,
                            page=page,
                            search_url=search.search_url_snapshot,
                            api_url=api_url,
                            output_zip=output_zip,
                            max_jobs=search.max_jobs_snapshot,
                            max_pages=search.max_pages_snapshot,
                            pause_for_login=False,
                        )
                        metrics = _capture_package_metrics(output_zip)
                        capture_run_id = str(metrics["capture_run_id"])
                        if not capture_run_id:
                            raise RuntimeError(
                                "LinkedIn capture completed without a persisted capture_run_id."
                            )
                        search.capture_run_id = capture_run_id
                        search.captured_count = int(metrics["captured_count"])
                        search.verified_count = int(metrics["verified_count"])
                        search.new_posting_count = int(metrics["new_posting_count"])
                        search.duplicate_count = int(metrics["duplicate_count"])
                        search.status = "completed"
                        search.completed_at = utc_now()
                        session.commit()
                    except Exception as exc:
                        failed_count += 1
                        search.status = "failed"
                        search.error = str(exc)
                        search.completed_at = utc_now()
                        session.commit()

                        if _is_fatal_session_failure(exc):
                            fatal_failure = True
                            _mark_remaining_skipped(
                                session,
                                searches,
                                after_position=search.position,
                                reason=(
                                    "Batch stopped because the shared LinkedIn session "
                                    f"became unsafe/unavailable: {exc}"
                                ),
                            )
                            break
    except Exception as exc:
        batch.status = "failed"
        batch.completed_at = utc_now()
        session.commit()
        raise RuntimeError(f"LinkedIn discovery batch runtime failed: {exc}") from exc

    batch.completed_at = utc_now()
    if fatal_failure:
        batch.status = "failed"
    elif failed_count:
        batch.status = "completed_with_failures"
    else:
        batch.status = "completed"
    session.commit()


def default_batch_profile_dir() -> Path:
    return _profile_dir()


def discovery_batch_evidence_dir(batch_id: str) -> Path:
    return _batch_evidence_dir(batch_id)
