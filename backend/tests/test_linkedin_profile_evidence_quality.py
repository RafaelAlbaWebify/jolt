from __future__ import annotations

from datetime import UTC, datetime

from jolt.candidate_evidence import build_candidate_evidence_ledger, profile_capture_quality_issue
from jolt.database import LinkedInPresenceCapture, create_session_factory
from jolt.linkedin_profile_exchange import _command_center_evidence


def _capture(
    *,
    capture_id: str,
    source_url: str,
    visible_text: str,
    title: str = "Profile",
) -> LinkedInPresenceCapture:
    return LinkedInPresenceCapture(
        id=capture_id,
        category="profile",
        title=title,
        source_url=source_url,
        visible_text=visible_text,
        notes="",
        content_hash=(capture_id * 64)[:64],
        previous_capture_id=None,
        changed_since_previous=True,
        captured_at=datetime.now(UTC),
    )


def test_profile_capture_quality_rejects_linkedin_authwall() -> None:
    capture = _capture(
        capture_id="a",
        source_url=(
            "https://www.linkedin.com/authwall?sessionRedirect="
            "https%3A%2F%2Fwww.linkedin.com%2Fin%2Fexample"
        ),
        visible_text="LinkedIn\nJoin LinkedIn\nAlready on Linkedin? Sign in",
    )

    assert profile_capture_quality_issue(capture) == "linkedin_login_or_authwall_url"


def test_candidate_ledger_excludes_authwall_but_preserves_usable_profile(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    try:
        session.add_all(
            [
                _capture(
                    capture_id="a",
                    source_url="https://www.linkedin.com/authwall?sessionRedirect=profile",
                    visible_text="Join LinkedIn\nAlready on Linkedin? Sign in",
                    title="Invalid profile",
                ),
                _capture(
                    capture_id="b",
                    source_url="https://www.linkedin.com/in/example/",
                    visible_text="Example Person\nIT Operations Engineer\nExperience\nMicrosoft 365",
                    title="Usable profile",
                ),
            ]
        )
        session.commit()

        ledger = build_candidate_evidence_ledger(session)

        assert ledger["counts"]["available_profile_captures"] == 2
        assert ledger["counts"]["usable_profile_captures"] == 1
        assert ledger["counts"]["invalid_profile_captures"] == 1
        assert [item["capture_id"] for item in ledger["source_evidence"]] == ["b"]
        assert ledger["excluded_profile_captures"][0]["capture_id"] == "a"
        assert ledger["excluded_profile_captures"][0]["reason"].startswith(
            "linkedin_login_or_authwall"
        )
    finally:
        session.close()


def test_linkedin_ai_exchange_excludes_invalid_profile_capture(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    try:
        session.add_all(
            [
                _capture(
                    capture_id="a",
                    source_url="https://www.linkedin.com/authwall?sessionRedirect=profile",
                    visible_text="Join LinkedIn\nAlready on Linkedin? Sign in",
                    title="Invalid profile",
                ),
                _capture(
                    capture_id="b",
                    source_url="https://www.linkedin.com/in/example/",
                    visible_text="Example Person\nIT Operations Engineer\nExperience\nMicrosoft 365",
                    title="Usable profile",
                ),
            ]
        )
        session.commit()

        evidence = _command_center_evidence(session)

        assert evidence["counts"]["invalid_profile_captures"] == 1
        assert evidence["counts"]["usable_exported_captures"] == 1
        assert [item["id"] for item in evidence["captures"]] == ["b"]
        assert evidence["excluded_profile_captures"][0]["capture_id"] == "a"
    finally:
        session.close()
