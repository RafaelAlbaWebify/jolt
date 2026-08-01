from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt import professional_intelligence_bounded_capture as bounded_capture
from jolt.database import create_session_factory, utc_now
from jolt.main import create_app
from jolt.professional_intelligence_bounded_capture import (
    AUTH_REQUIRED_MESSAGE,
    BoundedVisibleCaptureSession,
    _browser_profile_dir,
    _page_needs_linkedin_login,
)
from jolt.professional_intelligence_capture_runs import (
    AUTHORIZATION_CONFIRMATION_PHRASE,
    ProfessionalCaptureOptions,
)
from jolt.professional_intelligence_records import ProfessionalCaptureRun


class _FakeRun:
    cancel_requested = False


class _FakeSession:
    def __init__(self) -> None:
        self.run = _FakeRun()

    def get(self, _model: object, _run_id: str) -> _FakeRun:
        return self.run


class _FakeLocator:
    def __init__(
        self,
        text: str = "Application Support Engineer\nAcme SaaS Operations\nRemote Spain\nTroubleshoot SQL incidents. " * 3,
    ) -> None:
        self.text = text

    def inner_text(self, timeout: int) -> str:
        return self.text

    def count(self) -> int:
        return 0


class _FakeResponse:
    status = 200


class _SuccessfulPage:
    def __init__(self) -> None:
        self.url = "https://www.linkedin.com/jobs/search/"
        self.closed = False

    def bring_to_front(self) -> None:
        return None

    def goto(self, url: str, wait_until: str, timeout: int) -> _FakeResponse:
        self.url = url
        return _FakeResponse()

    def title(self) -> str:
        return "LinkedIn Jobs"

    def wait_for_load_state(self, state: str, timeout: int) -> None:
        return None

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator()

    def evaluate(self, script: str, arg: object | None = None) -> int | str | None:
        if "innerText" in script:
            return _FakeLocator().text
        if "scrollHeight" in script:
            return 100
        return None

    def wait_for_timeout(self, timeout: int) -> None:
        return None

    def screenshot(self, full_page: bool) -> bytes:
        return b"fake-png"

    def close(self) -> None:
        self.closed = True


class _FailingPage(_SuccessfulPage):
    def goto(self, url: str, wait_until: str, timeout: int) -> _FakeResponse:
        self.url = url
        raise RuntimeError("synthetic navigation failure")


class _ScreenshotFailingPage(_SuccessfulPage):
    def screenshot(self, full_page: bool) -> bytes:
        raise RuntimeError("synthetic screenshot failure")


class _FakeContext:
    def __init__(self, page: _SuccessfulPage) -> None:
        self.page = page

    def new_page(self) -> _SuccessfulPage:
        return self.page


def _capture_session(page: _SuccessfulPage) -> BoundedVisibleCaptureSession:
    session = BoundedVisibleCaptureSession(
        _FakeSession(),
        "run-1",
        ProfessionalCaptureOptions(
            max_sources=1,
            max_scroll_batches=1,
            max_items_per_source=5,
            timeout_seconds=10,
            stop_on_failure=True,
        ),
    )
    session.context = _FakeContext(page)  # type: ignore[assignment]
    return session


def test_professional_capture_detects_linkedin_login_url() -> None:
    assert _page_needs_linkedin_login(
        "https://www.linkedin.com/login?fromSignIn=true",
        "",
    )
    assert _page_needs_linkedin_login(
        "https://www.linkedin.com/checkpoint/challenge/123",
        "Security verification",
    )
    assert _page_needs_linkedin_login(
        "https://www.linkedin.com/authwall?trk=public_profile",
        "",
    )


def test_professional_capture_detects_login_text_markers() -> None:
    assert _page_needs_linkedin_login(
        "https://www.linkedin.com/jobs/search/",
        "Email or phone\nPassword\nSign in",
    )
    assert _page_needs_linkedin_login(
        "https://www.linkedin.com/jobs/search/",
        "Let's do a quick security check before continuing.",
    )


def test_professional_capture_allows_regular_linkedin_content() -> None:
    assert not _page_needs_linkedin_login(
        "https://www.linkedin.com/jobs/search/",
        "Application Support Engineer\nAcme SaaS Operations\nRemote Spain\nTroubleshoot SQL incidents.",
    )


def test_professional_capture_uses_project_local_persistent_profile() -> None:
    profile_dir = _browser_profile_dir()

    assert isinstance(profile_dir, Path)
    assert profile_dir.name == "professional-capture"
    assert profile_dir.parent.name == "playwright"
    assert profile_dir.is_dir()
    assert "JOLT kept the browser session open" in AUTH_REQUIRED_MESSAGE


def test_successful_capture_attempt_keeps_capture_page_open() -> None:
    page = _SuccessfulPage()
    captured = _capture_session(page)("https://www.linkedin.com/jobs/search/")

    assert captured.visible_text
    assert page.closed is False


def test_navigation_timeout_with_visible_text_returns_partial_evidence() -> None:
    page = _FailingPage()
    captured = _capture_session(page)("https://www.linkedin.com/jobs/search/")

    assert "Application Support Engineer" in captured.visible_text
    assert captured.screenshot_png == b"fake-png"
    assert "navigation reported RuntimeError" in captured.readiness_detail
    assert page.closed is False


def test_screenshot_failure_with_visible_text_returns_partial_evidence() -> None:
    page = _ScreenshotFailingPage()
    captured = _capture_session(page)("https://www.linkedin.com/jobs/search/")

    assert "Application Support Engineer" in captured.visible_text
    assert captured.screenshot_png == b""
    assert "screenshot failed" in captured.readiness_detail
    assert page.closed is False


def test_non_auth_capture_exception_does_not_stop_or_close_browser(monkeypatch) -> None:
    stopped = False

    def fake_stop_browser_context() -> None:
        nonlocal stopped
        stopped = True

    monkeypatch.setattr(bounded_capture, "_stop_browser_context", fake_stop_browser_context)
    page = _FailingPage()

    captured = _capture_session(page)("https://www.linkedin.com/jobs/search/")

    assert "Application Support Engineer" in captured.visible_text
    assert stopped is False
    assert page.closed is False


def test_linkedin_login_required_run_can_be_reauthorized_and_started_again(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    client = TestClient(create_app(database_url))
    factory = create_session_factory(database_url)

    created = client.post(
        "/api/professional-intelligence/capture-runs",
        json={
            "options": {
                "max_sources": 1,
                "max_scroll_batches": 1,
                "max_items_per_source": 5,
                "timeout_seconds": 10,
                "stop_on_failure": True,
            }
        },
    )
    assert created.status_code == 200
    run_id = created.json()["id"]

    with factory() as session:
        run = session.get(ProfessionalCaptureRun, run_id)
        assert run is not None
        run.status = "failed"
        run.completed_at = utc_now()
        run.current_source_id = ""
        run.cancel_requested = True
        run.stop_reason = "linkedin_login_required"
        session.commit()

    authorized = client.post(
        f"/api/professional-intelligence/capture-runs/{run_id}/authorize",
        json={"confirmation_phrase": AUTHORIZATION_CONFIRMATION_PHRASE, "user_present": True},
    )

    assert authorized.status_code == 200
    payload = authorized.json()
    assert payload["status"] == "authorized"
    assert payload["stop_reason"] == ""
    assert payload["cancel_requested"] is False
    assert payload["completed_at"] is None
