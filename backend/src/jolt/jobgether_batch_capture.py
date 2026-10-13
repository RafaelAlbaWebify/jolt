"""Bounded read-only Jobgether capture from a supervised Chrome search tab."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright
from urllib.parse import urlparse

from jolt.jobgether_preview import jobgether_identity
from jolt.jobgether_structured_offer import extract_offer


def discover_offer_urls(links: list[str], *, limit: int = 5) -> list[str]:
    """Preserve order and deduplicate canonical offer identities."""
    if not 1 <= limit <= 5:
        raise ValueError("limit must be between 1 and 5")
    unique: dict[str, str] = {}
    for link in links:
        identifier = jobgether_identity(link)
        if identifier and identifier not in unique:
            unique[identifier] = link
        if len(unique) >= limit:
            break
    return list(unique.values())


def select_search_page(browser: Browser) -> Page | None:
    """Choose a Jobgether page that is not already an individual offer."""
    for context in browser.contexts:
        for page in context.pages:
            parsed = urlparse(page.url)
            if (
                parsed.scheme == "https"
                and parsed.hostname in {"jobgether.com", "www.jobgether.com"}
                and not jobgether_identity(page.url)
            ):
                return page
    return None


def capture_batch(search_page: Page, *, limit: int = 5) -> dict[str, object]:
    """Read at most five discovered offers without writing to JOLT."""
    links = search_page.locator('a[href*="/offer/"]').evaluate_all(
        "elements => elements.map(el => el.href).filter(Boolean)"
    )
    urls = discover_offer_urls(links, limit=limit)
    offers: list[dict[str, object]] = []
    for url in urls:
        page = None
        try:
            page = search_page.context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            actual = page.url
            if jobgether_identity(actual) != jobgether_identity(url):
                offers.append(
                    {"url": url, "status": "unresolved", "reason": "navigation_identity_mismatch"}
                )
                continue
            title = (page.locator("h1").first.text_content(timeout=5000) or "").strip()
            scripts = [
                script.text_content(timeout=5000) or ""
                for script in page.locator('script[type="application/ld+json"]').all()
            ]
            offer = extract_offer(actual, scripts, title)
            offer.pop("description", None)
            offers.append(offer)
        except Exception as exc:
            offers.append(
                {
                    "url": url,
                    "source_job_id": jobgether_identity(url),
                    "status": "unresolved",
                    "reason": "browser_observation_failed",
                    "error_type": type(exc).__name__,
                }
            )
        finally:
            if page is not None:
                page.close()
    return {
        "source": "jobgether",
        "mode": "supervised_search_tab_read_only",
        "search_url": search_page.url,
        "observed_at": datetime.now(UTC).isoformat(),
        "discovered_count": len(urls),
        "captured_count": len(offers),
        "extracted_count": sum(x.get("status") == "extracted_unverified" for x in offers),
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
        "offers": offers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    parser.add_argument("--limit", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_endpoint, timeout=10_000)
        try:
            search = select_search_page(browser)
            result = (
                capture_batch(search, limit=args.limit)
                if search is not None
                else {"status": "unresolved", "reason": "no_jobgether_search_tab"}
            )
        finally:
            browser.close()
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    captured_count = result.get("captured_count")
    return 0 if isinstance(captured_count, int) and captured_count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
