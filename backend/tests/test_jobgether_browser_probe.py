from unittest.mock import Mock

from jolt.jobgether_browser_probe import inspect_tab


def test_inspect_existing_offer_does_not_promote() -> None:
    page = Mock()
    page.url = "https://jobgether.com/offer/6ac5d9628a27695aea363d32-support"
    page.locator.return_value.first.text_content.return_value = "Support Engineer"
    page.locator.return_value.first.count.return_value = 1
    page.locator.return_value.first.inner_text.return_value = "Job details " * 20
    page.locator.return_value.count.return_value = 1
    result = inspect_tab(page)
    assert result["status"] == "visible_page_observed"
    assert result["source_job_id"] == "6ac5d9628a27695aea363d32"
    assert result["source_evidence_verified"] is False
    assert result["work_from_spain_verified"] is False


def test_rejects_non_offer_tab_without_dom_access() -> None:
    page = Mock()
    page.url = "https://jobgether.com/jobs"
    assert inspect_tab(page)["status"] == "unresolved"
    page.locator.assert_not_called()
