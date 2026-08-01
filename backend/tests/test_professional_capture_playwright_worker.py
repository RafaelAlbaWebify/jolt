from __future__ import annotations

import threading

import pytest

from jolt import professional_intelligence_bounded_capture as bounded_capture
from jolt.professional_intelligence_bounded_capture import BoundedVisibleCaptureSession
from jolt.professional_intelligence_capture_runs import ProfessionalCaptureOptions
from jolt.professional_intelligence_supervised_capture import CapturedProfessionalPage


class _FakeRun:
    cancel_requested = False


class _FakeSession:
    def __init__(self) -> None:
        self.run = _FakeRun()

    def get(self, _model: object, _run_id: str) -> _FakeRun:
        return self.run


def _session() -> BoundedVisibleCaptureSession:
    return BoundedVisibleCaptureSession(
        _FakeSession(),  # type: ignore[arg-type]
        "run-1",
        ProfessionalCaptureOptions(
            max_sources=1,
            max_scroll_batches=1,
            max_items_per_source=5,
            timeout_seconds=10,
            stop_on_failure=True,
        ),
    )


def test_capture_calls_share_one_worker_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    caller_thread_id = threading.get_ident()
    worker_thread_ids: list[int] = []

    def fake_capture_on_worker(
        url: str,
        options: ProfessionalCaptureOptions,
    ) -> CapturedProfessionalPage:
        worker_thread_ids.append(threading.get_ident())
        return CapturedProfessionalPage(
            screenshot_png=b"png",
            visible_text="Application Support Engineer " * 10,
            title="LinkedIn Jobs",
            final_url=url,
            http_status=200,
            readiness_status="body_ready",
            readiness_detail=f"max_items={options.max_items_per_source}",
        )

    monkeypatch.setattr(bounded_capture, "_capture_on_worker", fake_capture_on_worker)

    first = _session()("https://www.linkedin.com/jobs/search/?start=0")
    second = _session()("https://www.linkedin.com/jobs/search/?start=25")

    assert first.http_status == 200
    assert second.http_status == 200
    assert len(worker_thread_ids) == 2
    assert worker_thread_ids[0] == worker_thread_ids[1]
    assert worker_thread_ids[0] != caller_thread_id


def test_worker_exception_is_returned_to_capture_orchestrator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_thread_ids: list[int] = []

    def fake_capture_on_worker(
        _url: str,
        _options: ProfessionalCaptureOptions,
    ) -> CapturedProfessionalPage:
        worker_thread_ids.append(threading.get_ident())
        raise RuntimeError("synthetic worker capture failure")

    monkeypatch.setattr(bounded_capture, "_capture_on_worker", fake_capture_on_worker)

    with pytest.raises(RuntimeError, match="synthetic worker capture failure"):
        _session()("https://www.linkedin.com/jobs/search/")

    assert worker_thread_ids
    assert worker_thread_ids[0] != threading.get_ident()
