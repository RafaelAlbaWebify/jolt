from pathlib import Path

import pytest
from pydantic import ValidationError

from jolt import local_linkedin_capture


def _reset_status() -> None:
    local_linkedin_capture._STATUS = local_linkedin_capture.LocalLinkedInCaptureStatus(  # noqa: SLF001
        status="idle"
    )


def test_local_capture_preserves_url_and_multi_page_bounds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _reset_status()
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    observed: dict[str, object] = {}

    def fake_run_capture(**kwargs: object) -> Path:
        observed.update(kwargs)
        output_zip = Path(str(kwargs["output_zip"]))
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        output_zip.write_bytes(b"capture")
        return output_zip

    monkeypatch.setattr(local_linkedin_capture, "run_capture", fake_run_capture)
    request = local_linkedin_capture.LocalLinkedInCaptureRequest(
        search_url=(
            "https://www.linkedin.com/jobs/search/?geoId=91000000"
            "&keywords=IT%20Support&refresh=true"
        ),
        max_jobs=20,
        max_pages=4,
    )

    queued = local_linkedin_capture.queue_local_linkedin_capture(request)
    assert queued.status == "queued"
    assert queued.search_url == request.search_url
    assert queued.max_jobs == 20
    assert queued.max_pages == 4

    local_linkedin_capture.run_queued_local_linkedin_capture()

    completed = local_linkedin_capture.get_local_linkedin_capture_status()
    assert completed.status == "completed"
    assert observed["search_url"] == request.search_url
    assert observed["max_jobs"] == 20
    assert observed["max_pages"] == 4
    assert observed["pause_for_login"] is False
    assert str(observed["api_url"]) == "http://127.0.0.1:8000"
    assert Path(completed.output_zip).exists()


def test_local_capture_rejects_parallel_run() -> None:
    _reset_status()
    request = local_linkedin_capture.LocalLinkedInCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/?keywords=Support",
        max_jobs=5,
        max_pages=2,
    )
    local_linkedin_capture.queue_local_linkedin_capture(request)

    with pytest.raises(ValueError, match="already running"):
        local_linkedin_capture.queue_local_linkedin_capture(request)


def test_local_capture_validates_bounds() -> None:
    accepted = local_linkedin_capture.LocalLinkedInCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/",
        max_jobs=100,
        max_pages=10,
    )
    assert accepted.max_jobs == 100
    assert accepted.max_pages == 10

    with pytest.raises(ValidationError):
        local_linkedin_capture.LocalLinkedInCaptureRequest(
            search_url="https://www.linkedin.com/jobs/search/",
            max_jobs=101,
            max_pages=3,
        )
    with pytest.raises(ValidationError):
        local_linkedin_capture.LocalLinkedInCaptureRequest(
            search_url="https://www.linkedin.com/jobs/search/",
            max_jobs=10,
            max_pages=11,
        )
