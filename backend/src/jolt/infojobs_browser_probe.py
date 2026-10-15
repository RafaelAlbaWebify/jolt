"""Read-only InfoJobs availability probe against a user-supervised Chrome tab.

No navigation, application submission, access bypass, or database writes.
"""

from __future__ import annotations

import argparse
import json
import re
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError


def is_infojobs_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {
        "infojobs.net",
        "www.infojobs.net",
    }


def is_offer_url(url: str) -> bool:
    """Recognize classic /oferta/ and current /of-i<hex> job URLs."""
    if not is_infojobs_url(url):
        return False
    path = urlparse(url).path.casefold()
    return "/oferta/" in path or bool(re.search(r"/of-i[0-9a-f]{12,}(?:/|$)", path))


DEFAULT_SEARCH_URL = "https://www.infojobs.net/ofertas-trabajo/support-it"


def _listing_identity(url: str) -> tuple[str, str] | None:
    """Identify requested listing by path and query on a trusted InfoJobs host."""
    if not is_infojobs_url(url):
        return None
    parsed = urlparse(url)
    if not parsed.path.startswith("/ofertas-trabajo/"):
        return None
    return parsed.path.rstrip("/"), parsed.query


def select_infojobs_page(browser: Browser, search_url: str | None = None) -> Page | None:
    """Select the requested listing, never an unrelated or detail tab."""
    wanted = _listing_identity(search_url) if search_url else None
    if search_url and wanted is None:
        return None
    pages = [page for context in browser.contexts for page in context.pages]
    listings = [page for page in pages if _listing_identity(page.url) is not None]
    if wanted is not None:
        return next(
            (page for page in reversed(listings) if _listing_identity(page.url) == wanted),
            None,
        )
    return listings[-1] if listings else None


def observe_stable_page(page: Page, attempts: int = 8) -> dict[str, object]:
    """Retry transient navigations; never navigate or interact with the page."""
    last_error = ""
    observations: list[dict[str, object]] = []
    last_snapshot: dict[str, object] = {}
    for attempt in range(attempts):
        try:
            snapshot = page.main_frame.evaluate(
                """() => ({
                    title: document.title || "",
                    text: document.body?.innerText || "",
                    links: Array.from(document.querySelectorAll("a[href]"), a => a.href),
                    ready_state: document.readyState,
                    html_length: document.documentElement?.outerHTML?.length || 0
                })"""
            )
            if isinstance(snapshot, dict):
                last_snapshot = snapshot
                observations.append(
                    {
                        "ready_state": str(snapshot.get("ready_state", "")),
                        "text_length": len(str(snapshot.get("text") or "")),
                        "html_length": snapshot.get("html_length", 0),
                        "link_count": len(snapshot.get("links", []))
                        if isinstance(snapshot.get("links"), list)
                        else 0,
                    }
                )
            if isinstance(snapshot, dict) and isinstance(snapshot.get("text"), str):
                body_text = snapshot["text"].strip()
                page_title = str(snapshot.get("title") or "").strip()
                raw_links = snapshot.get("links")
                has_offer_links = isinstance(raw_links, list) and any(
                    isinstance(link, str) and is_offer_url(link) for link in raw_links
                )
                restricted = any(
                    marker in (page_title + " " + body_text[:500]).casefold()
                    for marker in (
                        "captcha",
                        "access denied",
                        "acceso denegado",
                        "verifica que eres humano",
                    )
                )
                if restricted or (len(body_text) >= 150 and page_title and has_offer_links):
                    return snapshot
            last_error = "document_not_ready"
        except PlaywrightError as exc:
            last_error = type(exc).__name__
            observations.append({"error": str(exc)[:160]})
        if attempt < attempts - 1:
            page.wait_for_timeout(1000)
    return {
        "title": str(last_snapshot.get("title") or ""),
        "text": str(last_snapshot.get("text") or ""),
        "links": [],
        "ready_state": "unresolved",
        "html_length": last_snapshot.get("html_length", 0),
        "text_excerpt": str(last_snapshot.get("text") or "")[:220],
        "error": last_error,
        "observations": observations,
    }


def diagnose_page(page: Page) -> dict[str, object]:
    """Report observability without claiming that job details are verified."""
    url = page.url
    if not is_infojobs_url(url):
        return {"status": "unresolved", "reason": "not_infojobs"}
    snapshot = observe_stable_page(page)
    title = str(snapshot.get("title") or "").strip()
    text = str(snapshot.get("text") or "")
    lowered = (title + " " + text[:2500]).casefold()
    access_indicators = [
        token
        for token in ("captcha", "access denied", "acceso denegado", "verifica que eres humano")
        if token in lowered
    ]
    raw_links = snapshot.get("links")
    urls = (
        [link for link in raw_links if isinstance(link, str)] if isinstance(raw_links, list) else []
    )
    offer_urls = sorted({link.split("?", 1)[0] for link in urls if is_offer_url(link)})
    domain_links = [link for link in urls if is_infojobs_url(link)]
    candidate_routes = sorted(
        {urlparse(link).path for link in domain_links if "/of-" in urlparse(link).path}
    )
    return {
        "same_domain_anchor_count": len(domain_links),
        "potential_offer_route_samples": candidate_routes[:10],
        "status": (
            "access_restricted"
            if access_indicators
            else "listing_links_observed"
            if offer_urls
            else "unresolved"
            if snapshot.get("error")
            else "visible_page_no_offer_links"
            if title and len(text.strip()) >= 100
            else "unresolved"
        ),
        "url": url,
        "title": title[:250],
        "body_text_length": len(text),
        "offer_links_observed": len(offer_urls),
        "offer_url_samples": offer_urls[:5],
        "access_indicators": access_indicators,
        "observation_error": snapshot.get("error"),
        "observation_attempts": snapshot.get("observations"),
        "html_length": snapshot.get("html_length"),
        "text_excerpt": snapshot.get("text_excerpt"),
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    parser.add_argument("--search-url", default=DEFAULT_SEARCH_URL)
    args = parser.parse_args()
    if _listing_identity(args.search_url) is None:
        parser.error("--search-url must be an HTTPS InfoJobs listing URL")
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_endpoint, timeout=10000)
        try:
            page = select_infojobs_page(browser, args.search_url)
            result = (
                diagnose_page(page)
                if page is not None
                else {
                    "status": "unresolved",
                    "reason": "requested_search_tab_missing",
                    "requested_search_url": args.search_url,
                }
            )
        finally:
            browser.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] in {"listing_links_observed", "visible_page_no_offer_links"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
