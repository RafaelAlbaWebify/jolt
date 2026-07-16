from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

from jolt.multipage_capture import capture_pages, parse_args


def _card(job_id: str, title: str) -> str:
    return f"""
    <li class="jobs-search-results__list-item" data-occludable-job-id="{job_id}">
      <a class="job-card-list__title" href="https://www.linkedin.com/jobs/view/{job_id}"
         onclick="event.preventDefault(); showDetail('{job_id}', '{title}')">{title}</a>
      <div class="job-card-container__primary-description">Example Company</div>
      <div class="job-card-container__metadata-item">Remote Europe</div>
    </li>
    """


def _page_html() -> str:
    return f"""
    <html><body>
      <script>
        function showDetail(id, title) {{
          document.querySelector('main').innerHTML =
            `<a href='https://www.linkedin.com/jobs/view/${{id}}'>${{title}}</a>` +
            `<p>Detailed production support responsibilities, incident ownership, APIs, SQL and documentation for job ${{id}}.</p>`;
        }}
        function pageTwo() {{
          document.querySelector('ul').innerHTML = `{_card('2002', 'Duplicate Support Engineer')}{_card('2003', 'Production Support Engineer')}`;
          document.querySelector('.artdeco-pagination').innerHTML = '';
        }}
      </script>
      <ul>
        {_card('2001', 'Application Support Engineer')}
        <li class="jobs-search-results__list-item" data-occludable-job-id="unsupported-card">
          <span>Promoted card without a title link</span>
        </li>
        {_card('2002', 'Technical Support Engineer')}
      </ul>
      <div class="artdeco-pagination"><button aria-label="Page 2" onclick="pageTwo()">2</button></div>
      <main></main>
    </body></html>
    """


def test_capture_skips_unsupported_card_and_continues_to_second_page(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_content(_page_html())

        cards, pages, skipped, stop_reason = capture_pages(
            page,
            max_jobs=3,
            max_pages=3,
            evidence_dir=evidence,
        )
        browser.close()

    assert [card.source_job_id for card in cards] == ["2001", "2002", "2003"]
    assert all(card.identity_verified for card in cards)
    assert [page.page_number for page in pages] == [1, 2]
    assert pages[0].next_control_present is True
    assert pages[0].next_control_enabled is True
    assert pages[1].visible_job_ids == ("2002", "2003")
    assert stop_reason == "requested_limit_reached"
    assert any(item.reason == "Card had no supported title link." for item in skipped)
    assert any(item.reason == "Duplicate job identity across pages." for item in skipped)
    assert (evidence / "page_1_listing.png").exists()
    assert (evidence / "page_2_listing.png").exists()


def test_cli_exposes_bounded_page_count(tmp_path: Path) -> None:
    args = parse_args(
        [
            "--profile-dir",
            str(tmp_path / "profile"),
            "--output-zip",
            str(tmp_path / "capture.zip"),
            "--max-jobs",
            "25",
            "--max-pages",
            "4",
        ]
    )

    assert args.max_jobs == 25
    assert args.max_pages == 4
