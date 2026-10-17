"""Bounded read-only Jobgether capture from a supervised Chrome search tab."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, sync_playwright

from jolt.jobgether_batch_audit import audit_batch, load_previous_reports
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


def select_search_page(browser: Browser, search_url: str) -> Page | None:
    """Select the requested listing, never an unrelated Jobgether tab."""
    for context in reversed(browser.contexts):
        for page in reversed(context.pages):
            if page.url.split("?", 1)[0].rstrip("/") == search_url.split("?", 1)[0].rstrip("/"):
                return page
    return None



def discover_card_navigation_urls(search_page: Page, *, limit: int = 5) -> list[str]:
    """Inspect actual clickable card titles, never Apply controls or guessed URLs.

    Some logged-in Jobgether matches render card titles without /offer/ anchors.
    Follow at most five observed title interactions, accepting only a browser
    navigation to a canonical, same-site Jobgether offer.
    """
    headings = search_page.locator(
        "h2, h3, [role='heading'], [class*='job-title'], [class*='jobTitle']"
    )
    candidates: list[str] = []
    for index in range(min(headings.count(), 40)):
        heading = headings.nth(index)
        try:
            if not heading.is_visible(timeout=500):
                continue
            title = (heading.inner_text(timeout=500) or "").strip()
            if not 5 <= len(title) <= 180 or title.casefold() in {"apply", "get early access"}:
                continue
            is_job_card = heading.evaluate(
                """element => {
                    let ancestor = element.parentElement;
                    for (let depth = 0; ancestor && depth < 5; depth++, ancestor = ancestor.parentElement) {
                        const buttons = Array.from(ancestor.querySelectorAll('button'));
                        if (buttons.some(button => /^apply$/i.test((button.innerText || '').trim()))) {
                            return true;
                        }
                    }
                    return false;
                }"""
            )
            if is_job_card and title not in candidates:
                candidates.append(title)
            if len(candidates) >= limit:
                break
        except Exception:
            continue
    found: list[str] = []
    for title in candidates:
        # Open the observed listing in a separate tab; never disturb the
        # authenticated user's original page or click any Apply action.
        detail = None
        try:
            detail = search_page.context.new_page()
            detail.goto(search_page.url, wait_until="domcontentloaded", timeout=30_000)
            heading = detail.get_by_text(title, exact=True).first
            if not heading.is_visible(timeout=5_000):
                continue
            heading.click(timeout=5_000)
            detail.wait_for_timeout(900)
            urls = [detail.url]
            urls.extend(
                page.url
                for page in detail.context.pages
                if page is not search_page and page is not detail
            )
            for url in urls:
                if jobgether_identity(url) is not None:
                    found.append(url)
                    break
        except Exception:
            continue
        finally:
            if detail is not None:
                detail.close()
    return discover_offer_urls(found, limit=limit)



def capture_batch(search_page: Page, *, limit: int = 5) -> dict[str, object]:
    """Read at most five discovered offers without writing to JOLT."""
    links = search_page.locator('a[href*="/offer/"]').evaluate_all(
        "elements => elements.map(el => el.href).filter(Boolean)"
    )
    urls = discover_offer_urls(links, limit=limit)
    discovery_method = "canonical_links"
    if not urls:
        urls = discover_card_navigation_urls(search_page, limit=limit)
        discovery_method = "observed_card_navigation"
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
        "discovery_method": discovery_method,
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
    parser.add_argument("--search-url", default="https://jobgether.com/talent/matches")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--history-dir", type=Path)
    args = parser.parse_args()
    parsed = urlparse(args.search_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"jobgether.com", "www.jobgether.com"}
        or jobgether_identity(args.search_url)
    ):
        parser.error("--search-url must be an HTTPS Jobgether listing URL")
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_endpoint, timeout=10_000)
        try:
            search = select_search_page(browser, args.search_url)
            if search is None:
                result: dict[str, object] = {
                    "status": "unresolved",
                    "reason": "requested_search_tab_missing",
                    "requested_search_url": args.search_url,
                    "open_tab_urls": [page.url for ctx in browser.contexts for page in ctx.pages],
                }
            else:
                result = capture_batch(search, limit=args.limit)
        finally:
            browser.close()
    if result.get("source") == "jobgether":
        history_dir = args.history_dir or (args.output.parent if args.output else None)
        previous = (
            load_previous_reports(history_dir, current_output=args.output) if history_dir else []
        )
        result["quality_audit"] = audit_batch(result, previous)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    captured_count = result.get("captured_count")
    return 0 if isinstance(captured_count, int) and captured_count > 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
