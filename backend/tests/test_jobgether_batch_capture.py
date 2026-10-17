from unittest.mock import Mock

import pytest

from jolt.jobgether_batch_capture import (
    capture_batch,
    discover_card_navigation_urls,
    discover_offer_urls,
    select_search_page,
)

FIRST = "https://jobgether.com/offer/aaaaaaaaaaaaaaaaaaaaaaaa-first"
SECOND = "https://jobgether.com/offer/bbbbbbbbbbbbbbbbbbbbbbbb-second"


def test_discovery_deduplicates_and_rejects_external_urls() -> None:
    urls = discover_offer_urls(
        [FIRST, FIRST, "https://evil.example/offer/cccccccccccccccccccccccc", SECOND]
    )
    assert urls == [FIRST, SECOND]


def test_discovery_respects_limit() -> None:
    assert discover_offer_urls([FIRST, SECOND], limit=1) == [FIRST]
    with pytest.raises(ValueError):
        discover_offer_urls([FIRST], limit=6)


def test_capture_navigation_identity_mismatch_is_unresolved() -> None:
    search = Mock()
    search.url = "https://jobgether.com/talent/matches"
    search.locator.return_value.evaluate_all.return_value = [FIRST]
    detail = search.context.new_page.return_value
    detail.url = SECOND
    result = capture_batch(search, limit=5)
    assert result["captured_count"] == 1
    assert result["offers"][0]["reason"] == "navigation_identity_mismatch"
    assert result["source_evidence_verified"] is False
    detail.close.assert_called_once()


def test_empty_results_do_not_navigate() -> None:
    search = Mock()
    search.url = "https://jobgether.com/talent/matches"
    search.locator.return_value.evaluate_all.return_value = []
    result = capture_batch(search)
    assert result["captured_count"] == 0
    assert result["offers"] == []
    search.context.new_page.assert_not_called()


def test_failed_navigation_stays_unresolved() -> None:
    search = Mock()
    search.url = "https://jobgether.com/talent/matches"
    search.locator.return_value.evaluate_all.return_value = [FIRST]
    search.context.new_page.return_value.goto.side_effect = RuntimeError("denied")
    result = capture_batch(search)
    assert result["offers"][0]["status"] == "unresolved"
    assert result["offers"][0]["error_type"] == "RuntimeError"
    assert result["work_from_spain_verified"] is False


def test_select_search_page_requires_requested_listing() -> None:
    browser = Mock()
    unrelated = Mock(url="https://jobgether.com/offer/aaaaaaaaaaaaaaaaaaaaaaaa-test")
    another = Mock(url="https://jobgether.com/talent/profile")
    requested = Mock(url="https://jobgether.com/talent/matches?sort=new")
    browser.contexts = [Mock(pages=[unrelated, another, requested])]
    assert select_search_page(browser, "https://jobgether.com/talent/matches") is requested
    assert select_search_page(browser, "https://jobgether.com/talent/saved") is None


def test_select_search_page_prefers_freshest_matching_tab() -> None:
    browser = Mock()
    old = Mock(url="https://jobgether.com/talent/matches")
    newest = Mock(url="https://jobgether.com/talent/matches?sort=date")
    browser.contexts = [Mock(pages=[old, newest])]
    assert select_search_page(browser, "https://jobgether.com/talent/matches") is newest


def test_supervised_batch_keeps_real_description_evidence(monkeypatch) -> None:
    search = Mock(url="https://jobgether.com/talent/matches")
    search.locator.return_value.evaluate_all.return_value = [FIRST]
    detail = search.context.new_page.return_value
    detail.url = FIRST
    detail.locator.return_value.first.text_content.return_value = "Technical Engineer"
    detail.locator.return_value.all.return_value = []
    monkeypatch.setattr(
        "jolt.jobgether_batch_capture.extract_offer",
        lambda url, scripts, title: {
            "status": "extracted_unverified",
            "url": url,
            "source_job_id": "a" * 24,
            "title": title,
            "description": "Verified observation text of job responsibilities, not eligibility.",
        },
    )
    result = capture_batch(search, limit=1)
    assert result["extracted_count"] == 1
    assert result["offers"][0]["description"].startswith("Verified observation text")
    assert result["work_from_spain_verified"] is False


def test_card_title_navigation_retains_only_real_canonical_jobgether_url() -> None:
    search = Mock(url="https://jobgether.com/talent/matches")
    headings = search.locator.return_value
    headings.count.return_value = 1
    heading = headings.nth.return_value
    heading.is_visible.return_value = True
    heading.inner_text.return_value = "Level 2 IT Support Specialist"
    heading.evaluate.return_value = True

    detail = search.context.new_page.return_value
    detail.url = FIRST
    detail.get_by_text.return_value.first.is_visible.return_value = True
    detail.context.pages = [search, detail]
    result = discover_card_navigation_urls(search, limit=1)
    assert result == [FIRST]
    detail.get_by_text.assert_called_once_with("Level 2 IT Support Specialist", exact=True)
    detail.close.assert_called_once()


def test_card_title_navigation_rejects_noncanonical_page() -> None:
    search = Mock(url="https://jobgether.com/talent/matches")
    headings = search.locator.return_value
    headings.count.return_value = 1
    heading = headings.nth.return_value
    heading.is_visible.return_value = True
    heading.inner_text.return_value = "Technical Engineer"
    heading.evaluate.return_value = True
    detail = search.context.new_page.return_value
    detail.url = "https://jobgether.com/talent/matches"
    detail.context.pages = [search, detail]
    detail.get_by_text.return_value.first.is_visible.return_value = True
    assert discover_card_navigation_urls(search, limit=1) == []


@pytest.mark.parametrize(
    ("extracted", "expected_exit"),
    [(0, 2), (1, 0)],
)
def test_cli_requires_real_extracted_description(
    monkeypatch, tmp_path, extracted: int, expected_exit: int
) -> None:
    import sys
    from pathlib import Path

    from jolt import jobgether_batch_capture as module

    target = tmp_path / "report.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["jobgether_batch_capture", "--output", str(target)],
    )
    browser = Mock()
    page = Mock(url="https://jobgether.com/talent/matches")
    browser.contexts = [Mock(pages=[page])]
    playwright = Mock()
    playwright.chromium.connect_over_cdp.return_value = browser
    from unittest.mock import MagicMock

    controller = MagicMock()
    controller.__enter__.return_value = playwright
    controller.__exit__.return_value = False
    monkeypatch.setattr(module, "sync_playwright", lambda: controller)
    monkeypatch.setattr(
        module,
        "capture_batch",
        lambda search, limit: {
            "source": "jobgether",
            "mode": "supervised_search_tab_read_only",
            "search_url": page.url,
            "offers": [{"status": "unresolved"}],
            "captured_count": 1,
            "extracted_count": extracted,
        },
    )
    monkeypatch.setattr(module, "load_previous_reports", lambda *args, **kwargs: [])
    monkeypatch.setattr(module, "audit_batch", lambda *args: {})
    assert module.main() == expected_exit
    assert Path(target).is_file()
