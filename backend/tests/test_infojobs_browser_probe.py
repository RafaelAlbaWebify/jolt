from unittest.mock import Mock

from jolt.infojobs_browser_probe import diagnose_page, is_infojobs_url, select_infojobs_page


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
    page.title.return_value = "InfoJobs"
    page.locator.return_value.first.count.return_value = 1
    page.locator.return_value.first.inner_text.return_value = "CAPTCHA " + "x" * 150
    page.locator.return_value.evaluate_all.return_value = []
    result = diagnose_page(page)
    assert result["status"] == "access_restricted"
    assert result["source_evidence_verified"] is False


def test_public_links_are_diagnostic_only() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.title.return_value = "InfoJobs"
    page.locator.return_value.first.count.return_value = 1
    page.locator.return_value.first.inner_text.return_value = "Available jobs " * 20
    page.locator.return_value.evaluate_all.return_value = [
        "https://www.infojobs.net/oferta/abc?tracking=1",
        "https://www.infojobs.net/oferta/abc?tracking=2",
        "https://evil.example/oferta/wrong",
    ]
    result = diagnose_page(page)
    assert result["status"] == "listing_links_observed"
    assert result["offer_links_observed"] == 1
    assert result["work_from_spain_verified"] is False
