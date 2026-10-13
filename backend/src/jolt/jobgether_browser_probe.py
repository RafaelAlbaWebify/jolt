"""Read-only supervised Jobgether DOM probe against an already open Chrome tab.

Does not navigate, start browser sessions, bypass access controls, or write JOLT data.
"""

from __future__ import annotations

import argparse
import json

from playwright.sync_api import Page, sync_playwright

from jolt.jobgether_preview import jobgether_identity


def inspect_tab(page: Page) -> dict[str, object]:
    """Observe an open offer tab without interacting with the page."""
    url = str(getattr(page, "url", ""))
    identifier = jobgether_identity(url)
    if identifier is None:
        return {"status": "unresolved", "reason": "not_a_canonical_jobgether_offer"}
    title = page.locator("h1").first.text_content(timeout=5000) or ""
    main = page.locator("main").first
    main_text = main.inner_text(timeout=5000) if main.count() else ""
    schemas = page.locator('script[type="application/ld+json"]').count()
    return {
        "source_job_id": identifier,
        "status": "visible_page_observed" if title.strip() and len(main_text) >= 100 else "unresolved",
        "url": url,
        "title": title.strip()[:250],
        "main_text_length": len(main_text),
        "jsonld_blocks": schemas,
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_endpoint, timeout=10000)
        try:
            pages = [page for context in browser.contexts for page in context.pages]
            selected = next((page for page in pages if jobgether_identity(page.url)), None)
            if selected is None:
                result: dict[str, object] = {
                    "status": "unresolved",
                    "reason": "no_open_jobgether_offer_tab",
                }
            else:
                result = inspect_tab(selected)
        finally:
            browser.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "visible_page_observed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
