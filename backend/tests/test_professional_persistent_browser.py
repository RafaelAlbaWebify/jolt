from __future__ import annotations

from pathlib import Path

from jolt.professional_intelligence_bounded_capture import (
    AUTH_REQUIRED_MESSAGE,
    _browser_profile_dir,
    _page_needs_linkedin_login,
)


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
