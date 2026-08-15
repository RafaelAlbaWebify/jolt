from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from jolt.linkedin_capture import RetryMetrics, capture_pages


def _html() -> str:
    return """
    <html>
      <body>
        <script>
          function openJob(id, title) {
            document.querySelector("main").innerHTML =
              "<a href='https://www.linkedin.com/jobs/view/" +
              id + "/'>" + title + "</a>" +
              "<section id='JobDetails_AboutTheJob_" + id + "'>" +
              "<span data-testid='expandable-text-box'>" +
              "Detailed technical support responsibilities, incident ownership, " +
              "troubleshooting, APIs and documentation for " + title + "." +
              "</span></section>";
          }

          function pageTwo() {
            document.querySelector(
              '[data-testid="lazy-column"]'
            ).innerHTML =
              "<div role='button' tabindex='0' " +
              "onclick=\\\"openJob('7201','Cloud Support Engineer')\\\">" +
              "Cloud Support Engineer Example Three Spain" +
              "<button aria-label='Dismiss Cloud Support Engineer job'></button>" +
              "</div>" +
              "<div role='button' tabindex='0' " +
              "onclick=\\\"openJob('7202','Production Support Engineer')\\\">" +
              "Production Support Engineer Example Four Spain" +
              "<button aria-label='Dismiss Production Support Engineer job'></button>" +
              "</div>";

            document.querySelector(
              "button[aria-label='Page 1']"
            ).setAttribute("aria-current", "false");

            document.querySelector(
              "button[aria-label='Page 2']"
            ).setAttribute("aria-current", "true");
          }
        </script>

        <div
          data-testid="lazy-column"
          data-component-type="LazyColumn"
        >
          <div
            role="button"
            tabindex="0"
            onclick="openJob('7101','Application Support Engineer')"
          >
            Application Support Engineer Example One Spain
            <button
              aria-label="Dismiss Application Support Engineer job"
            ></button>
          </div>

          <div
            role="button"
            tabindex="0"
            onclick="openJob('7102','Technical Support Specialist')"
          >
            Technical Support Specialist Example Two Spain
            <button
              aria-label="Dismiss Technical Support Specialist job"
            ></button>
          </div>
        </div>

        <div class="jobs-search-pagination">
          <button aria-label="Page 1" aria-current="true">1</button>
          <button
            aria-label="Page 2"
            aria-current="false"
            onclick="pageTwo()"
          >2</button>
        </div>

        <main></main>
      </body>
    </html>
    """


def test_lazycolumn_capture_advances_to_second_page(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(_html())

        captured, pages, skipped, stop_reason = capture_pages(
            page,
            max_jobs=4,
            max_pages=2,
            evidence_dir=evidence,
            metrics=RetryMetrics(),
        )

        browser.close()

    assert [card.source_job_id for card in captured] == [
        "7101",
        "7102",
        "7201",
        "7202",
    ]
    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].next_control_present is True
    assert pages[0].next_control_enabled is True
    assert stop_reason == "requested_limit_reached"
    assert skipped == []
