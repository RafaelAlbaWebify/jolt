from __future__ import annotations

from datetime import UTC, datetime

from jolt.candidate_evidence import profile_capture_quality_issue
from jolt.database import LinkedInPresenceCapture


def _capture(notes: str) -> LinkedInPresenceCapture:
    return LinkedInPresenceCapture(
        id="capture",
        category="profile",
        title="Licenses & certifications",
        source_url="https://www.linkedin.com/in/example/details/certifications/",
        visible_text="Licenses & certifications\nCredential 1\nCredential 2",
        notes=notes,
        content_hash="a" * 64,
        previous_capture_id=None,
        changed_since_previous=True,
        captured_at=datetime.now(UTC),
    )


def test_complete_profile_section_rejects_zero_movement_when_scrolling_required() -> None:
    capture = _capture(
        "\n".join(
            [
                "JOLT profile section completeness: complete",
                "JOLT profile section stop reason: stable_at_scroll_surface_end",
                "JOLT profile section scroll count: 3",
                "JOLT profile section character count: 1800",
                "JOLT profile section scroll strategy: scrollable_container",
                "JOLT profile section furthest scroll position: 0",
                "JOLT profile section viewport extent: 700",
                "JOLT profile section final scroll extent: 4200",
                "JOLT profile section observed movement: false",
                "JOLT profile section scroll required: true",
            ]
        )
    )

    assert profile_capture_quality_issue(capture) == "unverified_linkedin_profile_section_traversal"


def test_complete_profile_section_accepts_observed_nested_surface_traversal() -> None:
    capture = _capture(
        "\n".join(
            [
                "JOLT profile section completeness: complete",
                "JOLT profile section stop reason: stable_at_scroll_surface_end",
                "JOLT profile section scroll count: 14",
                "JOLT profile section character count: 9200",
                "JOLT profile section scroll strategy: scrollable_container",
                "JOLT profile section furthest scroll position: 6200",
                "JOLT profile section viewport extent: 700",
                "JOLT profile section final scroll extent: 6900",
                "JOLT profile section observed movement: true",
                "JOLT profile section scroll required: true",
            ]
        )
    )

    assert profile_capture_quality_issue(capture) is None


def test_complete_profile_section_accepts_defensible_no_scroll_needed_case() -> None:
    capture = _capture(
        "\n".join(
            [
                "JOLT profile section completeness: complete",
                "JOLT profile section stop reason: stable_at_scroll_surface_end",
                "JOLT profile section scroll count: 3",
                "JOLT profile section character count: 900",
                "JOLT profile section scroll strategy: window",
                "JOLT profile section furthest scroll position: 0",
                "JOLT profile section viewport extent: 1000",
                "JOLT profile section final scroll extent: 1000",
                "JOLT profile section observed movement: false",
                "JOLT profile section scroll required: false",
            ]
        )
    )

    assert profile_capture_quality_issue(capture) is None
