from unittest.mock import Mock

import pytest

from jolt.jobgether_batch_capture import capture_batch, discover_offer_urls, select_search_page

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
