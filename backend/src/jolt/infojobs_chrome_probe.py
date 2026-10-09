"""Read-only supervised Chrome probe for InfoJobs result and detail pages.

Operates on a user-opened InfoJobs tab. Does not navigate, click, submit,
bypass checkpoints, or write to JOLT's database.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def probe_page(page) -> dict[str, object]:
    url = page.url
    host = (urlparse(url).hostname or "").lower()
    if host not in {"infojobs.net", "www.infojobs.net"} and not host.endswith(
        ".infojobs.net"
    ):
        raise ValueError("Active page is not on infojobs.net")
    return page.evaluate(
        """() => {
            const normalize = value => (value || '').replace(/\\s+/g, ' ').trim();
            const anchors = [...document.querySelectorAll('a[href]')];
            const offers = [];
            const seen = new Set();
            for (const anchor of anchors) {
                const href = anchor.href;
                const target = new URL(href, location.href);
                if (!target.hostname.endsWith('infojobs.net')) continue;
                const path = target.pathname;
                if (!/\\/(oferta|ofertas-trabajo)\\//i.test(path)) continue;
                const title = normalize(anchor.innerText || anchor.textContent);
                if (!title || seen.has(target.pathname)) continue;
                seen.add(target.pathname);
                offers.push({url: target.origin + target.pathname, title: title.slice(0, 180)});
                if (offers.length >= 30) break;
            }
            const structured = [...document.querySelectorAll(
                'script[type="application/ld+json"]'
            )].map(node => {
                try {
                    const data = JSON.parse(node.textContent || '');
                    return {type: data['@type'] || null,
                            title: data.title || null,
                            descriptionLength: (data.description || '').length};
                } catch {
                    return {type: 'unparseable'};
                }
            });
            return {
                pageUrl: location.href,
                pageTitle: document.title,
                offerCandidates: offers,
                candidateCount: offers.length,
                structuredData: structured,
                paginationLinks: anchors.filter(a => /[?&](page|pagina)=\\d+/i.test(a.href))
                    .slice(0, 12).map(a => ({text: normalize(a.innerText).slice(0, 60),
                                             href: a.href})),
                potentialDetails: [...document.querySelectorAll(
                    '[class*="description"], [id*="description"], [data-testid*="description"]'
                )].slice(0, 12).map(node => ({
                    tag: node.tagName,
                    length: normalize(node.innerText || node.textContent).length
                })),
            };
        }"""
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cdp-endpoint", default="http://127.0.0.1:9222")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.connect_over_cdp(args.cdp_endpoint)
        pages = [page for context in browser.contexts for page in context.pages]
        matching = [
            page for page in pages
            if (urlparse(page.url).hostname or "").lower().endswith("infojobs.net")
        ]
        if not matching:
            parser.error("Open InfoJobs manually in the Chrome debugging session first")
        data = probe_page(matching[-1])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"InfoJobs supervised read-only probe saved: {args.output}")
    print(f"Job candidates: {data['candidateCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
