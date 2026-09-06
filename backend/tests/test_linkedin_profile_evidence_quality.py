from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jolt.candidate_evidence import build_candidate_evidence_ledger, profile_capture_quality_issue
from jolt.database import LinkedInPresenceCapture, create_session_factory
from jolt.linkedin_profile_exchange import _command_center_evidence


def _capture(
    *,
    capture_id: str,
    source_url: str,
    visible_text: str,
    title: str = "Profile",
    notes: str = "",
    captured_at: datetime | None = None,
) -> LinkedInPresenceCapture:
    return LinkedInPresenceCapture(
        id=capture_id,
        category="profile",
        title=title,
        source_url=source_url,
        visible_text=visible_text,
        notes=notes,
        content_hash=(capture_id * 64)[:64],
        previous_capture_id=None,
        changed_since_previous=True,
        captured_at=captured_at or datetime.now(UTC),
    )


def _complete_progressive_notes(*, scroll_count: int = 12, character_count: int = 4000) -> str:
    return "\n".join(
        [
            "JOLT profile section completeness: complete",
            "JOLT profile section stop reason: stable_at_scroll_surface_end",
            f"JOLT profile section scroll count: {scroll_count}",
            f"JOLT profile section character count: {character_count}",
            "JOLT profile section scroll strategy: scrollable_container",
            "JOLT profile section furthest scroll position: 6400",
            "JOLT profile section viewport extent: 700",
            "JOLT profile section final scroll extent: 7100",
            "JOLT profile section observed movement: true",
            "JOLT profile section scroll required: true",
        ]
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


def test_profile_capture_quality_rejects_explicitly_partial_profile_section() -> None:
    capture = _capture(
        capture_id="p",
        source_url="https://www.linkedin.com/in/example/details/certifications/",
        visible_text="Licenses & certifications\nFirst credential only",
        title="Licenses & certifications",
        notes=(
            "Captured by JOLT LinkedIn Command Center Playwright flow.\n"
            "JOLT profile section completeness: partial\n"
            "JOLT profile section stop reason: maximum_scrolls_reached"
        ),
    )

    assert profile_capture_quality_issue(capture) == "partial_linkedin_profile_section"


def test_profile_capture_quality_rejects_legacy_false_complete_detail_section() -> None:
    capture = _capture(
        capture_id="legacy",
        source_url="https://www.linkedin.com/in/example/details/certifications/",
        visible_text="Licenses & certifications\nCredential 1\nCredential 2",
        title="Licenses & certifications",
        notes=(
            "JOLT profile section completeness: complete\n"
            "JOLT profile section stop reason: stable_at_document_end\n"
            "JOLT profile section scroll count: 4"
        ),
    )

    assert profile_capture_quality_issue(capture) == "legacy_non_scroll_surface_profile_section"


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


def test_candidate_ledger_exports_only_latest_usable_capture_per_profile_section(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    try:
        session.add_all(
            [
                _capture(
                    capture_id="old-cert",
                    source_url="https://www.linkedin.com/in/example/details/certifications/?foo=old",
                    visible_text="Licenses & certifications\nCredential old",
                    title="Licenses & certifications",
                    notes=_complete_progressive_notes(scroll_count=9, character_count=2800),
                    captured_at=now - timedelta(days=10),
                ),
                _capture(
                    capture_id="new-cert",
                    source_url="https://www.linkedin.com/in/example/details/certifications/?foo=new",
                    visible_text="Licenses & certifications\nCredential 1\nCredential 2\nCredential 3",
                    title="Licenses & certifications",
                    notes=_complete_progressive_notes(),
                    captured_at=now,
                ),
                _capture(
                    capture_id="experience",
                    source_url="https://www.linkedin.com/in/example/details/experience/",
                    visible_text="Experience\nIT Operations Engineer",
                    title="Experience",
                    notes=_complete_progressive_notes(scroll_count=6, character_count=1700),
                    captured_at=now - timedelta(minutes=1),
                ),
            ]
        )
        session.commit()

        ledger = build_candidate_evidence_ledger(session)

        assert [item["capture_id"] for item in ledger["source_evidence"]] == [
            "new-cert",
            "experience",
        ]
        assert ledger["counts"]["historical_profile_captures_not_exported"] == 1
        assert ledger["historical_profile_captures"][0]["capture_id"] == "old-cert"
        assert ledger["historical_profile_captures"][0]["reason"] == (
            "superseded_profile_section_snapshot"
        )
        certification = ledger["source_evidence"][0]
        assert certification["capture_metadata"] == {
            "completeness": "complete",
            "stop_reason": "stable_at_scroll_surface_end",
            "scroll_count": 12,
            "character_count": 4000,
            "scroll_strategy": "scrollable_container",
            "furthest_scroll_position": 6400,
            "viewport_extent": 700,
            "final_scroll_extent": 7100,
            "observed_movement": True,
            "scroll_required": True,
            "progressive_traversal_verified": True,
        }
    finally:
        session.close()


def test_newer_partial_section_does_not_hide_older_complete_section(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    now = datetime.now(UTC)
    try:
        session.add_all(
            [
                _capture(
                    capture_id="complete-cert",
                    source_url="https://www.linkedin.com/in/example/details/certifications/",
                    visible_text="Licenses & certifications\nCredential A\nCredential B",
                    title="Licenses & certifications",
                    notes=_complete_progressive_notes(),
                    captured_at=now - timedelta(hours=1),
                ),
                _capture(
                    capture_id="partial-cert",
                    source_url="https://www.linkedin.com/in/example/details/certifications/",
                    visible_text="Licenses & certifications\nCredential A",
                    title="Licenses & certifications",
                    notes="JOLT profile section completeness: partial",
                    captured_at=now,
                ),
            ]
        )
        session.commit()

        ledger = build_candidate_evidence_ledger(session)

        assert [item["capture_id"] for item in ledger["source_evidence"]] == ["complete-cert"]
        assert ledger["excluded_profile_captures"][0]["capture_id"] == "partial-cert"
        assert ledger["excluded_profile_captures"][0]["reason"] == (
            "partial_linkedin_profile_section"
        )
    finally:
        session.close()


def test_legacy_complete_section_is_excluded_until_progressive_recapture(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    try:
        session.add(
            _capture(
                capture_id="legacy-cert",
                source_url="https://www.linkedin.com/in/example/details/certifications/",
                visible_text="Licenses & certifications\nOnly first visible batch",
                title="Licenses & certifications",
                notes=(
                    "JOLT profile section completeness: complete\n"
                    "JOLT profile section stop reason: stable_at_document_end"
                ),
            )
        )
        session.commit()

        ledger = build_candidate_evidence_ledger(session)

        assert ledger["source_evidence"] == []
        assert ledger["excluded_profile_captures"][0]["reason"] == (
            "legacy_non_scroll_surface_profile_section"
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

        assert evidence["counts"] == {
            "captures": 2,
            "recommendations": 0,
            "open_recommendations": 0,
        }
        assert evidence["profile_capture_quality"]["invalid_profile_captures"] == 1
        assert evidence["profile_capture_quality"]["usable_exported_captures"] == 1
        assert [item["id"] for item in evidence["captures"]] == ["b"]
        assert evidence["excluded_profile_captures"][0]["capture_id"] == "a"
    finally:
        session.close()
