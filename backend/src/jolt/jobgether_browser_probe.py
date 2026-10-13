"""Read-only supervised Jobgether DOM probe against an already open Chrome tab.

Does not navigate, start browser sessions, bypass access controls, or write JOLT data.
"""

from __future__ import annotations

import argparse
import json

from playwright.sync_api import Page, sync_playwright

from jolt.jobgether_preview import jobgether_identity
from jolt.jobgether_structured_offer import extract_offer


def _jobposting_diagnostics(page: Page) -> dict[str, object]:
    """Report structured-data coverage without copying full job descriptions."""
    nodes: list[dict[str, object]] = []
    for script in page.locator('script[type="application/ld+json"]').all():
        try:
            payload = json.loads(script.text_content(timeout=5000) or "")
        except (ValueError, TypeError):
            continue

        pending: list[object] = [payload]
        while pending:
            node = pending.pop()
            if isinstance(node, list):
                pending.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, (list, dict)):
                pending.append(graph)
            types = node.get("@type", [])
            if isinstance(types, str):
                types = [types]
            if not isinstance(types, list) or "JobPosting" not in types:
                continue
            description = node.get("description")
            hiring = node.get("hiringOrganization")
            nodes.append(
                {
                    "title_present": bool(node.get("title")),
                    "description_length": len(description) if isinstance(description, str) else 0,
                    "date_posted_present": bool(node.get("datePosted")),
                    "employment_type_present": bool(node.get("employmentType")),
                    "job_location_present": bool(node.get("jobLocation")),
                    "applicant_location_requirements_present": bool(
                        node.get("applicantLocationRequirements")
                    ),
                    "hiring_organization_present": bool(hiring),
                    "identifier_present": bool(node.get("identifier")),
                    "url_present": bool(node.get("url")),
                }
            )
    return {"jobposting_count": len(nodes), "jobposting_fields": nodes}


def inspect_tab(page: Page) -> dict[str, object]:
    """Observe an open offer tab without interacting with the page."""
    url = str(getattr(page, "url", ""))
    identifier = jobgether_identity(url)
    if identifier is None:
        return {"status": "unresolved", "reason": "not_a_canonical_jobgether_offer"}
    title = page.locator("h1").first.text_content(timeout=5000) or ""
    main = page.locator("main").first
    main_text = main.inner_text(timeout=5000) if main.count() else ""
    body = page.locator("body").first
    body_text = body.inner_text(timeout=5000) if body.count() else ""
    schemas = page.locator('script[type="application/ld+json"]').count()
    content_source = (
        "main"
        if len(main_text.strip()) >= 100
        else "body"
        if len(body_text.strip()) >= 100
        else "none"
    )
    diagnostics = _jobposting_diagnostics(page)
    scripts = [
        script.text_content(timeout=5000) or ""
        for script in page.locator('script[type="application/ld+json"]').all()
    ]
    structured = extract_offer(url, scripts, title.strip())
    # Never print full descriptions from the browser probe.
    structured_summary = {
        key: value for key, value in structured.items() if key != "description"
    }
    return {
        "source_job_id": identifier,
        "status": "visible_page_observed"
        if title.strip() and content_source != "none"
        else "unresolved",
        "url": url,
        "title": title.strip()[:250],
        "main_text_length": len(main_text),
        "body_text_length": len(body_text),
        "content_source": content_source,
        "jsonld_blocks": schemas,
        **diagnostics,
        "structured_offer": structured_summary,
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
