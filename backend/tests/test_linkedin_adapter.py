# ruff: noqa: I001
from pathlib import Path

from jolt.sources.linkedin import LinkedInFixtureAdapter


FIXTURE = Path(__file__).parent / "fixtures" / "linkedin_search.html"


def test_listing_and_detail_contracts() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    adapter = LinkedInFixtureAdapter()

    run = adapter.parse_listing_page(html, page_number=1)

    assert [item.source_job_id for item in run.listings] == ["4434979232", "4435000001"]
    assert run.listings[0].title == "Application Support Engineer"
    assert run.listings[0].company == "Example Systems"
    assert run.pages[0].visible_job_ids == ("4434979232", "4435000001")
    assert run.pages[0].next_control_present is True
    assert run.pages[0].next_control_enabled is True
    assert run.warnings == ()

    detail = adapter.parse_detail_page(html, run.listings[0])
    assert detail.identity_verified is True
    assert detail.source_job_id == "4434979232"
    assert "SQL-backed application incidents" in detail.description


def test_stale_detail_panel_is_rejected() -> None:
    html = FIXTURE.read_text(encoding="utf-8")
    adapter = LinkedInFixtureAdapter()
    run = adapter.parse_listing_page(html)

    stale = adapter.parse_detail_page(html, run.listings[1])

    assert stale.identity_verified is False
    assert any(
        "does not match expected 4435000001" in reason for reason in stale.verification_reasons
    )
    assert any("does not match listing title" in reason for reason in stale.verification_reasons)
