from pathlib import Path

from playwright.sync_api import expect, sync_playwright


FIXTURE = Path(__file__).parent / "fixtures" / "linkedin_search.html"


def test_detail_panel_changes_to_selected_job_identity() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.goto(FIXTURE.resolve().as_uri())

        second_card = page.locator('[data-job-id="4435000001"]')
        second_card.locator("a").click()

        detail = page.locator("#detail")
        expect(detail).to_have_attribute("data-job-id", "4435000001")
        expect(detail.locator(".jobs-unified-top-card__job-title")).to_have_text(
            "Production Support Engineer"
        )
        expect(detail.locator(".jobs-unified-top-card__company-name")).to_have_text(
            "Factory Cloud"
        )
        browser.close()
