from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Literal

from pydantic import BaseModel, Field

from jolt.linkedin_capture import run_capture
from jolt.linkedin_source_urls import install_linkedin_url_normalization

install_linkedin_url_normalization()


class LocalLinkedInCaptureRequest(BaseModel):
    search_url: str = Field(min_length=1, max_length=4000)
    max_jobs: int = Field(default=10, ge=1, le=50)
    max_pages: int = Field(default=3, ge=1, le=10)


class LocalLinkedInCaptureStatus(BaseModel):
    status: Literal["idle", "queued", "running", "completed", "failed"]
    search_url: str = ""
    max_jobs: int = 0
    max_pages: int = 0
    output_zip: str = ""
    started_at: str = ""
    completed_at: str = ""
    error: str = ""


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
            search_url=request.search_url.strip(),
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
        with _STATUS_LOCK:
            _STATUS = _STATUS.model_copy(
                update={
                    "status": "completed",
                    "completed_at": datetime.now(UTC).isoformat(),
                    "error": "",
                }
            )
