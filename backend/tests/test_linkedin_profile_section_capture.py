from __future__ import annotations

from playwright.sync_api import sync_playwright

from jolt.linkedin_playwright_capture import _collect_profile_section_text


def test_profile_section_capture_scrolls_until_lazy_content_stabilizes() -> None:
    html = """
    <html>
      <body style="margin:0">
        <main id="items"></main>
        <div style="height:1200px">scroll sentinel</div>
        <script>
          const items = document.querySelector('#items');
          let loaded = 0;
          function addBatch() {
            if (loaded >= 4) return;
            loaded += 1;
            for (let i = 1; i <= 3; i += 1) {
              const card = document.createElement('section');
              card.style.height = '280px';
              card.textContent = `Credential ${((loaded - 1) * 3) + i}`;
              items.appendChild(card);
            }
          }
          addBatch();
          window.addEventListener('scroll', () => {
            const atBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 20;
            if (atBottom) addBatch();
          });
        </script>
      </body>
    </html>
    """

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.set_content(html)

        result = _collect_profile_section_text(page)
        browser.close()

    assert result["status"] == "complete"
    assert result["stop_reason"] == "stable_at_document_end"
    assert int(result["scroll_count"]) > 0
    text = str(result["visible_text"])
    assert "Credential 1" in text
    assert "Credential 12" in text


def test_profile_section_capture_marks_budget_exhaustion_partial(monkeypatch) -> None:
    import jolt.linkedin_playwright_capture as capture_module

    html = """
    <html>
      <body style="height:5000px">
        <script>
          let n = 0;
          window.addEventListener('scroll', () => {
            n += 1;
            const item = document.createElement('div');
            item.textContent = `Ever growing ${n}`;
            item.style.height = '300px';
            document.body.appendChild(item);
          });
        </script>
      </body>
    </html>
    """
    monkeypatch.setattr(capture_module, "_MAX_PROFILE_SECTION_SCROLLS", 1)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 700})
        page.set_content(html)
        result = _collect_profile_section_text(page)
        browser.close()

    assert result["status"] == "partial"
    assert result["stop_reason"] == "maximum_scrolls_reached"
