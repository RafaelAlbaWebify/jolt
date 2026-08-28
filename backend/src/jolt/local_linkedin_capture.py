from __future__ import annotations

import json
import os
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

from jolt.linkedin_capture import run_capture
from jolt.linkedin_source_urls import (
    install_linkedin_url_normalization,
    normalize_linkedin_search_url,
)
from jolt.preference_aware_evaluation import install_preference_aware_evaluation

install_linkedin_url_normalization()
install_preference_aware_evaluation()


class LocalLinkedInCaptureRequest(BaseModel):
    search_url: str = Field(min_length=1, max_length=4000)
    max_jobs: int = Field(default=100, ge=1, le=100)
    max_pages: int = Field(default=10, ge=1, le=10)


class LocalLinkedInCaptureStatus(BaseModel):
    status: Literal["idle", "queued", "running", "completed", "failed"]
    search_url: str = ""
    max_jobs: int = 0
    max_pages: int = 0
    output_zip: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""
    captured_count: int = 0
    verified_count: int = 0
    skipped_count: int = 0
    pages_used: int = 0
    stop_reason: str = ""
    retry_attempted_count: int = 0
    new_items: int = 0
    duplicate_items: int = 0
    health: Literal["", "green", "yellow", "red"] = ""


_STATUS_LOCK = Lock()
_CAPTURE_LOCK = Lock()
_STATUS = LocalLinkedInCaptureStatus(status="idle")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _profile_dir() -> Path:
    path = _repo_root() / ".jolt" / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _downloads_dir() -> Path:
    profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    downloads = profile / "Downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


def _new_output_zip() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return _downloads_dir() / f"JOLT_LINKEDIN_CAPTURE_{timestamp}.zip"


def _capture_metrics(output_zip: Path) -> dict[str, int | str]:
    metrics: dict[str, int | str] = {
        "captured_count": 0,
        "verified_count": 0,
        "skipped_count": 0,
        "pages_used": 0,
        "stop_reason": "",
        "retry_attempted_count": 0,
        "new_items": 0,
        "duplicate_items": 0,
        "health": "",
    }

    try:
        with zipfile.ZipFile(output_zip) as archive:
            summary = json.loads(archive.read("capture_summary.json"))
            api_result = json.loads(archive.read("api_result.json"))
    except (OSError, KeyError, zipfile.BadZipFile, json.JSONDecodeError):
        return metrics

    captured = int(summary.get("captured_count", 0) or 0)
    verified = int(summary.get("verified_count", 0) or 0)
    skipped = len(summary.get("skipped_cards", []) or [])
    pages_used = len(summary.get("pages", []) or [])
    stop_reason = str(summary.get("stop_reason", "") or "")
    retry_metrics = summary.get("retry_metrics", {}) or {}
    retry_attempted = int(retry_metrics.get("retry_attempted_count", 0) or 0)
    failed_after_retry = int(retry_metrics.get("failed_after_retry_count", 0) or 0)

    api_items = api_result.get("items", []) or []
    duplicates = sum(
        1 for item in api_items if item.get("identity_status") == "confirmed_duplicate"
    )
    new_items = max(0, len(api_items) - duplicates)

    seen = captured + skipped
    verified_ratio = verified / captured if captured else 0.0
    skip_ratio = skipped / seen if seen else 0.0

    if (
        captured > 0
        and verified_ratio >= 0.98
        and skip_ratio <= 0.20
        and failed_after_retry == 0
        and stop_reason
        in {
            "requested_limit_reached",
            "max_pages_reached",
            "no_next_page",
            "next_page_disabled",
        }
    ):
        health = "green"
    elif captured > 0 and verified_ratio >= 0.95 and failed_after_retry == 0:
        health = "yellow"
    else:
        health = "red"

    metrics.update(
        {
            "captured_count": captured,
            "verified_count": verified,
            "skipped_count": skipped,
            "pages_used": pages_used,
            "stop_reason": stop_reason,
            "retry_attempted_count": retry_attempted,
            "new_items": new_items,
            "duplicate_items": duplicates,
            "health": health,
        }
    )
    return metrics


def get_local_linkedin_capture_status() -> LocalLinkedInCaptureStatus:
    with _STATUS_LOCK:
        return _STATUS.model_copy(deep=True)


def queue_local_linkedin_capture(
    request: LocalLinkedInCaptureRequest,
) -> LocalLinkedInCaptureStatus:
    global _STATUS
    with _STATUS_LOCK:
        if _STATUS.status in {"queued", "running"}:
            raise ValueError("A LinkedIn capture is already running.")
        output_zip = _new_output_zip()
        _STATUS = LocalLinkedInCaptureStatus(
            status="queued",
            search_url=normalize_linkedin_search_url(request.search_url),
            max_jobs=request.max_jobs,
            max_pages=request.max_pages,
            output_zip=str(output_zip),
        )
        return _STATUS.model_copy(deep=True)


def run_queued_local_linkedin_capture() -> None:
    global _STATUS
    with _CAPTURE_LOCK:
        with _STATUS_LOCK:
            if _STATUS.status != "queued":
                return
            request = LocalLinkedInCaptureRequest(
                search_url=_STATUS.search_url,
                max_jobs=_STATUS.max_jobs,
                max_pages=_STATUS.max_pages,
            )
            output_zip = Path(_STATUS.output_zip)
            _STATUS = _STATUS.model_copy(
                update={
                    "status": "running",
                    "started_at": datetime.now(UTC).isoformat(),
                    "error": "",
                }
            )
        try:
            run_capture(
                search_url=request.search_url,
                api_url="http://127.0.0.1:8000",
                profile_dir=_profile_dir(),
                output_zip=output_zip,
                max_jobs=request.max_jobs,
                max_pages=request.max_pages,
                pause_for_login=False,
            )
        except Exception as exc:
            with _STATUS_LOCK:
                _STATUS = _STATUS.model_copy(
                    update={
                        "status": "failed",
                        "completed_at": datetime.now(UTC).isoformat(),
                        "error": str(exc),
                    }
                )
            return
        metrics = _capture_metrics(output_zip)

        with _STATUS_LOCK:
            _STATUS = _STATUS.model_copy(
                update={
                    "status": "completed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "error": "",
                    **metrics,
                }
            )
