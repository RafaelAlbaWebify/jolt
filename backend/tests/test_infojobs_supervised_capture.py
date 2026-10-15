from unittest.mock import Mock

import pytest

from jolt.infojobs_supervised_capture import capture_visible, discover_offer_urls

OFFER = "https://www.infojobs.net/madrid/support/of-i0123456789abcdef0123456789abcdef"


def test_discovery_is_bounded_deduplicated_and_domain_checked() -> None:
    assert discover_offer_urls(
        [OFFER + "?campaign=1", OFFER, "https://attacker.example/of-i0123456789abcdef"]
    ) == [OFFER]
    with pytest.raises(ValueError):
        discover_offer_urls([OFFER], limit=6)


def test_nonlisting_diagnostic_never_opens_details() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "Access denied",
        "text": "CAPTCHA " * 30,
        "links": [],
    }
    result = capture_visible(page)
    assert result["stop_reason"] == "no_reliable_offer_links"
    assert result["offers"] == []
    assert result["source_evidence_verified"] is False


def test_detail_identity_mismatch_fails_closed() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "InfoJobs",
        "text": "Available opportunities " * 25,
        "links": [OFFER],
    }
    detail = Mock(url="https://www.infojobs.net/madrid/other/of-iabcdef0123456789abcdef0123456789")
    page.context.new_page.return_value = detail
    result = capture_visible(page)
    assert result["offers"][0]["reason"] == "identity_mismatch"
    assert result["extracted_count"] == 0
    page.locator.assert_not_called()
    detail.close.assert_called_once()


def test_read_only_capture_keeps_source_text_but_not_verification() -> None:
    page = Mock(url="https://www.infojobs.net/ofertas-trabajo/support-it")
    page.main_frame.evaluate.return_value = {
        "title": "InfoJobs",
        "text": "Available opportunities " * 25,
        "links": [OFFER],
    }
    detail = Mock(url=OFFER)
    detail.locator.return_value.first.text_content.return_value = "Support Engineer"
    detail.locator.return_value.inner_text.return_value = "Offer details " * 25
    page.context.new_page.return_value = detail
    result = capture_visible(page)
    assert result["extracted_count"] == 1
    page.locator.assert_not_called()
    assert result["offers"][0]["title_observed"] == "Support Engineer"
    assert result["offers"][0]["source_evidence_verified"] is False
    assert result["offers"][0]["body_sha256"]
