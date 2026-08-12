from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from jolt import multipage_capture
from jolt.linkedin_capture import RetryMetrics, capture_pages


def _html() -> str:
    return """
    <html>
      <body>
        <script>
          function openJob(id, title, company, location) {
            document.querySelector("main").innerHTML =
              "<div>" +
              company + " " + title + " " + location +
              " · About the job " +
              "<a href='https://www.linkedin.com/jobs/view/" +
              id + "/'>" + title + "</a>" +
              "<p>Detailed support responsibilities, incident " +
              "ownership, troubleshooting, APIs and documentation." +
              "</p></div>";
          }
        </script>

        <div
          data-testid="lazy-column"
          data-component-type="LazyColumn"
        >
          <div>
            <div
              role="button"
              tabindex="0"
              onclick="openJob(
                '7001',
                'Application Support Engineer',
                'Example One',
                'Spain'
              )"
            >
              Application Support Engineer Example One Spain
              <button
                aria-label="Dismiss Application Support Engineer job"
              ></button>
            </div>
          </div>

          <div>
            <div
              role="button"
              tabindex="0"
              onclick="openJob(
                '7002',
                'Technical Support Specialist',
                'Example Two',
                'Remote Spain'
              )"
            >
              Technical Support Specialist Example Two Remote Spain
              <button
                aria-label="Dismiss Technical Support Specialist job"
              ></button>
            </div>
          </div>
        </div>

        <main></main>
      </body>
    </html>
    """


def test_lazycolumn_cards_capture_verified_identities(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(_html())

        cards, selector = multipage_capture._wait_for_cards(
            page,
            timeout_ms=2_000,
        )

        assert selector == multipage_capture.VIRTUALIZED_CARD_SELECTOR
        assert cards.count() == 2

        captured, pages, skipped, stop_reason = capture_pages(
            page,
            max_jobs=2,
            max_pages=1,
            evidence_dir=evidence,
            metrics=RetryMetrics(),
        )

        browser.close()

    assert [card.source_job_id for card in captured] == [
        "7001",
        "7002",
    ]
    assert [card.title for card in captured] == [
        "Application Support Engineer",
        "Technical Support Specialist",
    ]
    assert all(card.identity_verified for card in captured)
    assert skipped == []
    assert stop_reason == "requested_limit_reached"

    assert pages[0].visible_job_ids == (
        "7001",
        "7002",
    )


def test_legacy_card_selectors_remain_before_lazycolumn() -> None:
    assert multipage_capture.CARD_SELECTORS[:4] == (
        ".jobs-search-results__list-item",
        "li[data-occludable-job-id]",
        "[data-job-id].job-card-container",
        "[data-job-id][class*='job-card']",
    )
    assert multipage_capture.CARD_SELECTORS[4] == multipage_capture.VIRTUALIZED_CARD_SELECTOR
