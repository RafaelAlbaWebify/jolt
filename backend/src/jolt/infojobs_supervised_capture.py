"""Bounded supervised InfoJobs detail evidence; never promotes or writes JOLT records."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Browser, Page, sync_playwright

from jolt.infojobs_browser_probe import (
    diagnose_page,
    is_offer_url,
    select_infojobs_page,
)


def discover_offer_urls(links: list[str], limit: int = 5) -> list[str]:
    if not 1 <= limit <= 5:
        raise ValueError("Expected 1..5 offers")
    unique: dict[str, str] = {}
    for url in links:
        if not is_offer_url(url):
            continue
        identity = urlparse(url).path.rstrip("/").casefold()
        if identity not in unique:
            unique[identity] = url.split("?", 1)[0]
        if len(unique) == limit:
            break
    return list(unique.values())


def capture_visible(search_page: Page, limit: int = 5) -> dict[str, object]:
    """Capture only page-visible links and their accessible detail pages."""
    diagnostic = diagnose_page(search_page)
    result: dict[str, object] = {
        "source": "infojobs",
        "mode": "supervised_browser_evidence_read_only",
        "search_url": search_page.url,
        "captured_at": datetime.now(UTC).isoformat(),
        "search_diagnostic": diagnostic,
        "offers": [],
        "source_evidence_verified": False,
        "work_from_spain_verified": False,
    }
    if diagnostic.get("status") != "listing_links_observed":
        result["stop_reason"] = "no_reliable_offer_links"
        return result
    anchors = search_page.locator("a[href]").evaluate_all(
        "elements => elements.map(el => el.href).filter(Boolean)"
    )
    urls = discover_offer_urls(anchors, limit)
    offers: list[dict[str, object]] = []
    for expected_url in urls:
        detail = None
        try:
            detail = search_page.context.new_page()
            detail.goto(expected_url, wait_until="domcontentloaded", timeout=30000)
            actual = detail.url
            if (
                not is_offer_url(actual)
                or urlparse(actual).path.rstrip("/").casefold()
                != urlparse(expected_url).path.rstrip("/").casefold()
            ):
                offers.append(
                    {"url": expected_url, "status": "unresolved", "reason": "identity_mismatch"}
                )
                continue
            title = (detail.locator("h1").first.text_content(timeout=5000) or "").strip()
            body = (detail.locator("body").inner_text(timeout=5000) or "").strip()
            if not title or len(body) < 150:
                offers.append(
                    {"url": expected_url, "status": "unresolved", "reason": "incomplete_detail"}
                )
                continue
            offers.append(
                {
                    "url": actual,
                    "source_identity_path": urlparse(actual).path,
                    "title_observed": title[:500],
                    "body_text": body,
                    "body_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                    "body_characters": len(body),
                    "status": "extracted_unverified",
                    "source_evidence_verified": False,
                    "work_from_spain_verified": False,
                }
            )
        except Exception as exc:
            offers.append(
                {
                    "url": expected_url,
                    "status": "unresolved",
                    "reason": "browser_observation_failed",
                    "error_type": type(exc).__name__,
                }
            )
        finally:
            if detail is not None:
                detail.close()
    result["offers"] = offers
    result["discovered_count"] = len(urls)
    result["extracted_count"] = sum(offer["status"] == "extracted_unverified" for offer in offers)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9223")
    parser.add_argument("--limit", type=int, choices=range(1, 6), default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser: Browser = playwright.chromium.connect_over_cdp(args.cdp_endpoint, timeout=10000)
        try:
            search = select_infojobs_page(browser)
            result = (
                capture_visible(search, args.limit)
                if search is not None
                else {"status": "unresolved", "reason": "no_infojobs_tab"}
            )
        finally:
            browser.close()
    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "source": "infojobs",
                "mode": "supervised_browser_evidence_read_only",
                "output": str(args.output) if args.output else None,
                "discovered_count": result.get("discovered_count", 0),
                "extracted_count": result.get("extracted_count", 0),
                "search_diagnostic": result.get("search_diagnostic"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.get("extracted_count", 0) else 2


if __name__ == "__main__":
    raise SystemExit(main())
