from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from jolt.database import create_session_factory, utc_now
from jolt.main import create_app
from jolt.professional_intelligence_bounded_capture import (
    AUTH_REQUIRED_MESSAGE,
    _browser_profile_dir,
    _page_needs_linkedin_login,
)
from jolt.professional_intelligence_capture_runs import AUTHORIZATION_CONFIRMATION_PHRASE
from jolt.professional_intelligence_records import ProfessionalCaptureRun


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
