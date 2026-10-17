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
            "text": "Jobs " * 90,
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
            "text": "Jobs " * 90,
            "links": ["https://www.infojobs.net/oferta/abc"],
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


def test_explicit_search_selects_correct_tab_with_multiple_listings() -> None:
    browser = Mock()
    wrong = Mock(url="https://www.infojobs.net/ofertas-trabajo/marketing")
    correct = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    browser.contexts = [Mock(pages=[correct, wrong])]
    assert select_infojobs_page(browser, correct.url) is correct


def test_missing_requested_listing_does_not_fall_back_to_another_tab() -> None:
    browser = Mock()
    other = Mock(url="https://www.infojobs.net/ofertas-trabajo/marketing")
    browser.contexts = [Mock(pages=[other])]
    assert (
        select_infojobs_page(browser, "https://www.infojobs.net/ofertas-trabajo/support-it") is None
    )


def test_detail_tab_never_substitutes_for_search_listing() -> None:
    browser = Mock()
    detail = Mock(url="https://www.infojobs.net/madrid/support/of-i0123456789abcdef")
    browser.contexts = [Mock(pages=[detail])]
    assert select_infojobs_page(browser) is None


def test_short_shell_waits_for_real_listing_and_keeps_evidence() -> None:
    page = Mock()
    shell = {
        "title": "",
        "text": "Please wait" * 12,
        "links": [],
        "ready_state": "complete",
        "html_length": 180,
    }
    page.main_frame.evaluate.return_value = shell
    result = observe_stable_page(page, attempts=2)
    assert result["error"] == "document_not_ready"
    assert result["text_excerpt"].startswith("Please wait")
    assert len(result["observations"]) == 2
    assert result["html_length"] == 180


def test_tiny_ad_shell_is_never_reported_as_visible_listing() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "",
        "text": "NUEVA TEMPORADA YA DISPONIBLE SUSCRIBETE " * 3,
        "links": [],
        "ready_state": "complete",
        "html_length": 7684,
    }
    result = diagnose_page(page)
    assert result["status"] == "unresolved"
    assert result["observation_error"] == "document_not_ready"
    assert result["offer_links_observed"] == 0


def test_infojobs_added_filters_keep_requested_listing_selectable() -> None:
    browser = Mock()
    listing = Mock(
        url="https://www.infojobs.net/ofertas-trabajo/support-it?"
        "keyword=support%20it&page=1&sortBy=PUBLICATION_DATE"
    )
    other = Mock(url="https://www.infojobs.net/ofertas-trabajo/marketing?page=1")
    browser.contexts = [Mock(pages=[other, listing])]
    assert (
        select_infojobs_page(browser, "https://www.infojobs.net/ofertas-trabajo/support-it")
        is listing
    )


def test_explicit_filtered_infojobs_search_requires_exact_query() -> None:
    browser = Mock()
    listing = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it?page=2")
    browser.contexts = [Mock(pages=[listing])]
    assert (
        select_infojobs_page(browser, "https://www.infojobs.net/ofertas-trabajo/support-it?page=1")
        is None
    )


def test_current_filtered_search_page_route_is_recognized() -> None:
    from jolt.infojobs_browser_probe import _listing_identity

    url = (
        "https://www.infojobs.net/ofertas-trabajo?"
        "keyword=Administrador%2Fa%20de%20sistemas&page=1&sortBy=RELEVANCE"
    )
    assert _listing_identity(url) == (
        "/ofertas-trabajo",
        "keyword=Administrador%2Fa%20de%20sistemas&page=1&sortBy=RELEVANCE",
    )
    browser = Mock()
    browser.contexts = [Mock(pages=[Mock(url=url)])]
    assert select_infojobs_page(browser, url).url == url
