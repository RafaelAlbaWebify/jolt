"""Read-only InfoJobs availability probe against a user-supervised Chrome tab.

No navigation, application submission, access bypass, or database writes.
"""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, sync_playwright


def is_infojobs_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {
        "infojobs.net",
        "www.infojobs.net",
    }


def select_infojobs_page(browser: Browser) -> Page | None:
    """Prefer a listing page, otherwise an existing InfoJobs page."""
    candidates = [
        page for context in browser.contexts for page in context.pages if is_infojobs_url(page.url)
    ]
    return next(
        (page for page in candidates if "/ofertas-trabajo" in urlparse(page.url).path),
        candidates[0] if candidates else None,
    )


def diagnose_page(page: Page) -> dict[str, object]:
    """Report observability without claiming that job details are verified."""
    url = page.url
    if not is_infojobs_url(url):
        return {"status": "unresolved", "reason": "not_infojobs"}
    title = (page.title() or "").strip()
    body = page.locator("body").first
    text = (body.inner_text(timeout=5000) or "") if body.count() else ""
    lowered = (title + " " + text[:2500]).casefold()
    access_indicators = [
        token
        for token in ("captcha", "access denied", "acceso denegado", "verifica que eres humano")
        if token in lowered
    ]
    urls = page.locator("a[href]").evaluate_all(
        "elements => elements.map(el => el.href).filter(Boolean)"
    )
    offer_urls = sorted(
        {
            link.split("?", 1)[0]
            for link in urls
            if is_infojobs_url(link) and "/oferta/" in urlparse(link).path
        }
    )
    return {
        "status": (
            "access_restricted"
            if access_indicators
            else "listing_links_observed"
            if offer_urls
            else "visible_page_no_offer_links"
            if len(text.strip()) >= 100
            else "unresolved"
        ),
        "url": url,
        "title": title[:250],
        "body_text_length": len(text),
        "offer_links_observed": len(offer_urls),
        "offer_url_samples": offer_urls[:5],
        "access_indicators": access_indicators,
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
            page = select_infojobs_page(browser)
            result = (
                diagnose_page(page)
                if page is not None
                else {"status": "unresolved", "reason": "no_infojobs_tab"}
            )
        finally:
            browser.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"listing_links_observed", "visible_page_no_offer_links"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
