from __future__ import annotations

import json
from pathlib import Path

import pytest
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
              " · " +
              "<a href='https://www.linkedin.com/jobs/view/" +
              id + "/'>" + title + "</a>" +
              "<section id='JobDetails_AboutTheJob_" + id + "'>" +
              "<div data-sdui-component='" +
              "com.linkedin.sdui.generated.jobseeker.dsl.impl.aboutTheJob'>" +
              "<h2>About the job</h2>" +
              "<span data-testid='expandable-text-box'>" +
              "Detailed support responsibilities, incident ownership, " +
              "troubleshooting, APIs and documentation." +
              "</span></div></section>" +
              "<section id='recommended-jobs'>" +
              "<h2>Other jobs you may like</h2>" +
              "<p>Senior Software Developer C# Angular Portuguese " +
              "required relocation mandatory management role.</p>" +
              "</section>" +
              "</div>";
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


@pytest.mark.parametrize(
    ("apply_control", "expected_url"),
    [
        (
            '<button class="jobs-apply-button" aria-label="Apply on company website" '
            "onclick=\"window.open('https://employer.example/apply')\">Apply</button>",
            "",
        ),
        (
            '<a class="jobs-apply-button" href="https://employer.example/apply" '
            'aria-label="Apply on company website" target="_blank">Apply on company website</a>',
            "https://employer.example/apply",
        ),
    ],
)
def test_lazycolumn_cards_capture_verified_identities(
    tmp_path: Path,
    apply_control: str,
    expected_url: str,
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        html = _html().replace(
            "\"<section id='recommended-jobs'>\" +",
            json.dumps(apply_control) + " + \"<section id='recommended-jobs'>\" +",
        )
        page.set_content(html)
        opened_pages = []
        network_requests = []
        page.context.on("page", lambda opened: opened_pages.append(opened))

        def block_network(route):
            network_requests.append(route.request.url)
            route.abort()

        page.context.route("**/*", block_network)

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

        assert opened_pages == []
        assert network_requests == []
        assert len(page.context.pages) == 1
        browser.close()

    assert all(card.application_url == expected_url for card in captured)
    assert all(card.easy_apply_available is False for card in captured)
    assert [card.source_job_id for card in captured] == [
        "7001",
        "7002",
    ]
    assert [card.title for card in captured] == [
        "Application Support Engineer",
        "Technical Support Specialist",
    ]
    assert all(card.identity_verified for card in captured)

    for card in captured:
        assert "Detailed support responsibilities" in card.description
        assert "Software Developer" not in card.description
        assert "Portuguese" not in card.description
        assert "relocation mandatory" not in card.description
        assert "management role" not in card.description
        assert "Other jobs you may like" not in card.description

    assert skipped == []
    assert stop_reason == "requested_limit_reached"

    assert pages[0].visible_job_ids == (
        "7001",
        "7002",
    )


def test_lazycolumn_description_falls_back_only_to_about_job_container(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence-fallback"
    evidence.mkdir()

    html = """
    <html>
      <body>
        <script>
          function openJob() {
            document.querySelector("main").innerHTML =
              "<div>" +
              "<a href='https://www.linkedin.com/jobs/view/8001/'>" +
              "IT Support Engineer</a>" +
              "<section id='JobDetails_AboutTheJob_8001'>" +
              "<div data-sdui-component='" +
              "com.linkedin.sdui.generated.jobseeker.dsl.impl.aboutTheJob'>" +
              "<h2>About the job</h2>" +
              "<p>Provide Windows and Active Directory support.</p>" +
              "<ul>" +
              "<li>Troubleshoot incidents and service requests.</li>" +
              "<li>Maintain endpoint and user documentation.</li>" +
              "</ul>" +
              "</div>" +
              "</section>" +
              "<section id='recommended-jobs'>" +
              "<p>Senior Software Developer C# Angular Portuguese " +
              "required relocation mandatory management role.</p>" +
              "</section>" +
              "</div>";
          }
        </script>

        <div
          data-testid="lazy-column"
          data-component-type="LazyColumn"
        >
          <div
            role="button"
            tabindex="0"
            onclick="openJob()"
          >
            IT Support Engineer Example Spain
            <button
              aria-label="Dismiss IT Support Engineer job"
            ></button>
          </div>
        </div>

        <main></main>
      </body>
    </html>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(html)

        captured, _, skipped, _ = capture_pages(
            page,
            max_jobs=1,
            max_pages=1,
            evidence_dir=evidence,
            metrics=RetryMetrics(),
        )

        browser.close()

    assert skipped == []
    assert len(captured) == 1

    description = captured[0].description

    assert "Windows and Active Directory support" in description
    assert "Troubleshoot incidents" in description
    assert "Maintain endpoint" in description

    assert "Software Developer" not in description
    assert "Portuguese" not in description
    assert "relocation mandatory" not in description
    assert "management role" not in description


def test_legacy_card_selectors_remain_before_lazycolumn() -> None:
    assert multipage_capture.CARD_SELECTORS[:4] == (
        ".jobs-search-results__list-item",
        "li[data-occludable-job-id]",
        "[data-job-id].job-card-container",
        "[data-job-id][class*='job-card']",
    )
    assert multipage_capture.CARD_SELECTORS[4] == multipage_capture.VIRTUALIZED_CARD_SELECTOR
