from pathlib import Path

import pytest
from pydantic import ValidationError

from jolt import linkedin_capture, local_linkedin_capture


def _reset_status() -> None:
    local_linkedin_capture._STATUS = local_linkedin_capture.LocalLinkedInCaptureStatus(  # noqa: SLF001
        status="idle"
    )


def test_local_capture_normalizes_url_and_preserves_multi_page_bounds(
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
            "https://www.linkedin.com/jobs/search/?currentJobId=123456"
            "&geoId=91000000&keywords=IT%20Support&refresh=true"
            "&trackingId=transient"
        ),
        max_jobs=20,
        max_pages=4,
    )

    queued = local_linkedin_capture.queue_local_linkedin_capture(request)
    assert queued.status == "queued"
    assert queued.search_url == (
        "https://www.linkedin.com/jobs/search/?geoId=91000000&keywords=IT+Support"
    )
    assert queued.max_jobs == 20
    assert queued.max_pages == 4

    local_linkedin_capture.run_queued_local_linkedin_capture()

    completed = local_linkedin_capture.get_local_linkedin_capture_status()
    assert completed.status == "completed"
    assert observed["search_url"] == queued.search_url
    assert observed["max_jobs"] == 20
    assert observed["max_pages"] == 4
    assert observed["pause_for_login"] is False
    assert str(observed["api_url"]) == "http://127.0.0.1:8000"
    assert Path(completed.output_zip).exists()


def test_best_effort_screenshot_never_aborts_capture(tmp_path: Path) -> None:
    class BrokenScreenshotPage:
        def screenshot(self, **_: object) -> None:
            raise RuntimeError("fonts never loaded")

    assert (
        linkedin_capture._best_effort_screenshot(  # noqa: SLF001
            BrokenScreenshotPage(),  # type: ignore[arg-type]
            tmp_path / "optional.png",
        )
        is False
    )


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
    defaults = local_linkedin_capture.LocalLinkedInCaptureRequest(
        search_url="https://www.linkedin.com/jobs/search/",
    )
    assert defaults.max_jobs == 100
    assert defaults.max_pages == 10

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
