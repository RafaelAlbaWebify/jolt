from __future__ import annotations

from playwright.sync_api import sync_playwright

from jolt.linkedin_playwright_capture import _collect_profile_section_text
from jolt.linkedin_profile_scroll import (
    advance_profile_scroll_surface,
    reset_profile_scroll_surface,
)


def _nested_lazy_profile_html() -> str:
    return """
    <html style="height:100%">
      <body style="height:100%; margin:0; overflow:hidden">
        <main id="profile" style="height:700px; overflow-y:auto">
          <div id="items"></div>
          <div style="height:3000px">sentinel</div>
        </main>
        <script>
          const root = document.querySelector('#profile');
          const items = document.querySelector('#items');
          let stage = 0;
          function addBatch() {
            for (let i = 1; i <= 3; i += 1) {
              const item = document.createElement('section');
              item.style.height = '140px';
              item.textContent = `Credential ${stage * 3 + i}`;
              items.appendChild(item);
            }
            stage += 1;
          }
          addBatch();
          root.addEventListener('scroll', () => {
            const thresholds = [250, 700, 1150];
            if (stage <= thresholds.length && root.scrollTop >= thresholds[stage - 1]) {
              addBatch();
            }
          });
        </script>
      </body>
    </html>
    """


def test_profile_scroll_prefers_nested_scroll_owner_when_window_cannot_scroll() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.set_content(_nested_lazy_profile_html())

        initial = reset_profile_scroll_surface(page)
        assert initial["strategy"] == "scrollable_container"
        assert page.evaluate("() => window.scrollY") == 0

        furthest = 0
        for _ in range(12):
            result = advance_profile_scroll_surface(page)
            assert result["strategy"] == "scrollable_container"
            furthest = max(furthest, int(result["after"]))
            page.wait_for_timeout(20)

        text = page.locator("body").inner_text()
        browser.close()

    assert furthest > 1000
    assert "Credential 12" in text


def test_profile_section_collector_exhausts_nested_scroll_owner() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.set_content(_nested_lazy_profile_html())

        result = _collect_profile_section_text(page)
        browser.close()

    assert result["status"] == "complete"
    assert result["stop_reason"] == "stable_at_scroll_surface_end"
    assert result["scroll_strategy"] == "scrollable_container"
    assert result["observed_movement"] is True
    assert result["scroll_required"] is True
    assert int(result["furthest_scroll_position"]) > 1000
    assert int(result["final_scroll_extent"]) > int(result["viewport_extent"])
    assert "Credential 12" in str(result["visible_text"])


def test_profile_scroll_uses_window_when_document_is_scroll_owner() -> None:
    html = """
    <html>
      <body style="margin:0">
        <div style="height:3200px">window content</div>
      </body>
    </html>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.set_content(html)

        initial = reset_profile_scroll_surface(page)
        result = advance_profile_scroll_surface(page)
        browser.close()

    assert initial["strategy"] == "window"
    assert result["strategy"] == "window"
    assert int(result["after"]) > 0
