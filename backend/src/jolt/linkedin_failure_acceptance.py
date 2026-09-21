from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from jolt import multipage_capture
from jolt.linkedin_access import classify_navigation_exception, detect_linkedin_access_problem


def _problem_record(problem: tuple[str, str] | None) -> dict[str, str] | None:
    if problem is None:
        return None
    return {"classification": problem[0], "message": problem[1]}


def _visible_card_count(page: Any) -> int:
    cards, _selector = multipage_capture._wait_for_cards(page)
    return int(cards.count())


def run_acceptance(
    *,
    profile_dir: Path,
    search_url: str,
    output_path: Path,
    interactive_login: bool,
) -> dict[str, object]:
    report: dict[str, object] = {
        "acceptance_type": "linkedin_failure_recovery",
        "performed_at": datetime.now(UTC).isoformat(),
        "search_url": search_url,
        "authwall_detection": {},
        "authenticated_access": {},
        "network_failure": {},
        "network_recovery": {},
        "passed": False,
    }

    temp_profile = Path(tempfile.mkdtemp(prefix="jolt-linkedin-authwall-"))
    try:
        with sync_playwright() as playwright:
            clean = playwright.chromium.launch_persistent_context(
                user_data_dir=temp_profile,
                headless=True,
                viewport={"width": 1280, "height": 900},
            )
            try:
                page = clean.pages[0] if clean.pages else clean.new_page()
                page.goto(
                    "https://www.linkedin.com/login",
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                auth_problem = detect_linkedin_access_problem(page)
                auth_passed = auth_problem is not None and auth_problem[0] in {
                    "authentication_required",
                    "checkpoint",
                }
                report["authwall_detection"] = {
                    "url": page.url,
                    "problem": _problem_record(auth_problem),
                    "passed": auth_passed,
                }
                if not auth_passed:
                    raise RuntimeError(
                        "Real LinkedIn login page was not classified as an auth/checkpoint state."
                    )
            finally:
                clean.close()

            context = playwright.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1440, "height": 1000},
            )
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                problem = detect_linkedin_access_problem(page)

                if problem is not None and interactive_login:
                    print(f"LinkedIn access state: {problem[0]} — {problem[1]}")
                    print("Resolve login/checkpoint in the opened browser, then return here.")
                    input("Press Enter after LinkedIn is ready: ")
                    page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                    problem = detect_linkedin_access_problem(page)

                if problem is not None:
                    report["authenticated_access"] = {
                        "problem": _problem_record(problem),
                        "passed": False,
                    }
                    raise RuntimeError(
                        f"Persistent JOLT profile is not ready: {problem[0]} — {problem[1]}"
                    )

                initial_cards = _visible_card_count(page)
                if initial_cards < 1:
                    raise RuntimeError(
                        "Authenticated LinkedIn search loaded without usable job cards."
                    )
                report["authenticated_access"] = {
                    "final_url": page.url,
                    "visible_job_cards": initial_cards,
                    "passed": True,
                }

                context.set_offline(True)
                try:
                    separator = "&" if "?" in search_url else "?"
                    page.goto(
                        search_url + separator + "jolt_network_probe=1",
                        wait_until="domcontentloaded",
                        timeout=15_000,
                    )
                except Exception as exc:
                    classification = classify_navigation_exception(exc)
                    report["network_failure"] = {
                        "classification": classification,
                        "error_type": type(exc).__name__,
                        "passed": classification == "network_failure",
                    }
                else:
                    report["network_failure"] = {
                        "classification": "no_failure",
                        "passed": False,
                    }
                finally:
                    context.set_offline(False)

                network_failure = report["network_failure"]
                if not isinstance(network_failure, dict) or not network_failure.get("passed"):
                    raise RuntimeError(
                        "Forced offline LinkedIn navigation was not classified as a network failure."
                    )

                page.goto(search_url, wait_until="domcontentloaded", timeout=60_000)
                recovered_problem = detect_linkedin_access_problem(page)
                recovered_cards = 0 if recovered_problem else _visible_card_count(page)
                recovery_passed = recovered_problem is None and recovered_cards >= 1
                report["network_recovery"] = {
                    "problem": _problem_record(recovered_problem),
                    "visible_job_cards": recovered_cards,
                    "passed": recovery_passed,
                }
                if not recovery_passed:
                    raise RuntimeError(
                        "LinkedIn did not recover cleanly after connectivity was restored."
                    )
            finally:
                context.close()

        report["passed"] = True
        return report
    finally:
        shutil.rmtree(temp_profile, ignore_errors=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dated real-site LinkedIn login/network failure and recovery acceptance."
    )
    parser.add_argument("--profile-dir", required=True, type=Path)
    parser.add_argument(
        "--search-url",
        default="https://www.linkedin.com/jobs/search/?keywords=IT%20Support",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--no-interactive-login", action="store_true")
    args = parser.parse_args()

    report = run_acceptance(
        profile_dir=args.profile_dir,
        search_url=args.search_url,
        output_path=args.output,
        interactive_login=not args.no_interactive_login,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
