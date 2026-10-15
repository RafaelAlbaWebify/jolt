from unittest.mock import Mock

from jolt.infojobs_browser_probe import (
    diagnose_page,
    is_infojobs_url,
    is_offer_url,
    observe_stable_page,
    select_infojobs_page,
)


def test_infojobs_url_rejects_external_and_insecure_domains() -> None:
    assert is_infojobs_url("https://www.infojobs.net/ofertas-trabajo/support-it")
    assert not is_infojobs_url("https://infojobs.net.evil.example/ofertas-trabajo")
    assert not is_infojobs_url("http://www.infojobs.net/ofertas-trabajo")


def test_search_tab_preferred_over_other_tabs() -> None:
    browser = Mock()
    detail = Mock(url="https://www.infojobs.net/oferta/abc")
    listing = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    browser.contexts = [Mock(pages=[detail, listing])]
    assert select_infojobs_page(browser) is listing


def test_missing_tab_returns_none() -> None:
    browser = Mock()
    browser.contexts = [Mock(pages=[Mock(url="https://example.com")])]
    assert select_infojobs_page(browser) is None


def test_access_indicators_do_not_promote_source_evidence() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "InfoJobs",
        "text": "CAPTCHA " + "x" * 150,
        "links": [],
    }
    result = diagnose_page(page)
    assert result["status"] == "access_restricted"
    assert result["source_evidence_verified"] is False


def test_public_links_are_diagnostic_only() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "InfoJobs",
        "text": "Available jobs " * 20,
        "links": [
            "https://www.infojobs.net/oferta/abc?tracking=1",
            "https://www.infojobs.net/oferta/abc?tracking=2",
            "https://evil.example/oferta/wrong",
        ],
    }
    result = diagnose_page(page)
    assert result["status"] == "listing_links_observed"
    assert result["offer_links_observed"] == 1
    assert result["work_from_spain_verified"] is False


def test_current_infojobs_job_permalinks_are_recognized() -> None:
    url = "https://www.infojobs.net/madrid/support-engineer/of-i0123456789abcdef0123456789abcdef"
    assert is_offer_url(url)
    assert not is_offer_url("https://www.infojobs.net/ofertas-trabajo/support-it")
    assert not is_offer_url("https://www.infojobs.net.evil.example/x/of-i0123456789abcdef")


def test_current_permalinks_are_deduplicated_in_diagnostic() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "InfoJobs",
        "text": "Job results " * 30,
        "links": [
            "https://www.infojobs.net/madrid/support-engineer/of-i0123456789abcdef0123456789abcdef?src=search",
            "https://www.infojobs.net/madrid/support-engineer/of-i0123456789abcdef0123456789abcdef",
        ],
    }
    result = diagnose_page(page)
    assert result["status"] == "listing_links_observed"
    assert result["offer_links_observed"] == 1


def test_observation_retries_empty_document_then_succeeds() -> None:
    page = Mock()
    page.main_frame.evaluate.side_effect = [
        {"title": "", "text": "", "links": [], "ready_state": "loading"},
        {
            "title": "InfoJobs",
            "text": "Jobs " * 30,
            "links": ["https://www.infojobs.net/oferta/abc"],
            "ready_state": "complete",
        },
    ]
    result = observe_stable_page(page, attempts=3)
    assert result["title"] == "InfoJobs"
    assert page.main_frame.evaluate.call_count == 2
    page.wait_for_timeout.assert_called_once_with(1000)


def test_observation_retries_context_destruction() -> None:
    from playwright.sync_api import Error as PlaywrightError

    page = Mock()
    page.main_frame.evaluate.side_effect = [
        PlaywrightError("Execution context was destroyed"),
        {
            "title": "InfoJobs",
            "text": "Jobs " * 30,
            "links": [],
            "ready_state": "complete",
        },
    ]
    result = observe_stable_page(page, attempts=2)
    assert result["ready_state"] == "complete"


def test_observation_exhaustion_stays_unresolved() -> None:
    page = Mock()
    page.main_frame.evaluate.return_value = {
        "title": "InfoJobs",
        "text": "",
        "links": [],
        "ready_state": "loading",
    }
    result = observe_stable_page(page, attempts=2)
    assert result["ready_state"] == "unresolved"
    assert result["error"] == "document_not_ready"
