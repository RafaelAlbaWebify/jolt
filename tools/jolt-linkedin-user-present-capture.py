from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-._")
    return slug[:80] or "linkedin-capture"


def _post_capture(api_base: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{api_base.rstrip('/')}/api/linkedin-command-center/captures",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"JOLT API rejected the capture: HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Unable to reach JOLT API at {api_base}: {exc}") from exc


def _capture_with_playwright(
    *,
    url: str,
    category: str,
    title: str,
    notes: str,
    api_base: str,
    output_dir: Path,
    full_page_screenshot: bool,
) -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed in this environment. Run through `uv --project backend run python ...`."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    screenshot_path = output_dir / f"{stamp}_{_safe_slug(category)}_{_safe_slug(title)}.png"
    browser_profile = output_dir / "browser-profile"

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(browser_profile),
            headless=False,
            viewport={"width": 1440, "height": 1100},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        print("\nVisible browser opened.")
        print("Log in or navigate manually. Do not run bulk searches or automated actions.")
        print("When the exact page section is visible and you approve the capture, return here and press Enter.")
        input("Press Enter to capture this visible LinkedIn evidence, or Ctrl+C to cancel... ")

        final_url = page.url
        page_title = page.title()
        visible_text = page.locator("body").inner_text(timeout=10_000).strip()
        page.screenshot(path=str(screenshot_path), full_page=full_page_screenshot)
        context.close()

    payload = {
        "category": category,
        "title": title or page_title or category.replace("_", " "),
        "source_url": final_url,
        "visible_text": visible_text,
        "notes": "\n".join(
            line for line in [notes.strip(), f"Screenshot: {screenshot_path}"] if line
        ),
    }
    result = _post_capture(api_base, payload)
    result["screenshot_path"] = str(screenshot_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="User-present LinkedIn capture helper for JOLT. Opens a visible browser and saves only the user-approved current page evidence."
    )
    parser.add_argument("--url", required=True, help="LinkedIn URL to open first.")
    parser.add_argument(
        "--category",
        required=True,
        choices=[
            "profile",
            "public_profile",
            "analytics",
            "activity",
            "network_contact",
            "network_request",
            "target_company",
            "target_recruiter",
            "job_search",
            "other",
        ],
    )
    parser.add_argument("--title", default="", help="Capture title shown in JOLT.")
    parser.add_argument("--notes", default="", help="Optional notes stored with the capture.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--output-dir",
        default=str(Path.home() / "Downloads" / "JOLT_LINKEDIN_CAPTURES"),
        help="Where screenshots/browser profile are stored.",
    )
    parser.add_argument(
        "--full-page-screenshot",
        action="store_true",
        help="Capture the full rendered page screenshot. Default captures the current viewport only.",
    )
    args = parser.parse_args()

    try:
        result = _capture_with_playwright(
            url=args.url,
            category=args.category,
            title=args.title,
            notes=args.notes,
            api_base=args.api_base,
            output_dir=Path(args.output_dir),
            full_page_screenshot=args.full_page_screenshot,
        )
    except KeyboardInterrupt:
        print("\nCancelled before capture.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print("\nSaved LinkedIn evidence snapshot to JOLT.")
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
