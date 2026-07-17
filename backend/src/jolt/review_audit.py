from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

API_BASE = "http://127.0.0.1:8000"
APP_URL = "http://127.0.0.1:5173"
LEGACY_PROFILE = "rafael-job-search:v2"
LEGACY_ENGINE = "profile-rules-v2"
PRIVATE_ENGINES = {"profile-rules-v3", "profile-rules-v4"}
EXPECTED_READINESS_ENGINE = "application-readiness-v1"
REQUIRED_REVIEW_FIELDS = {
    "proposed_decision",
    "fit_summary",
    "strengths",
    "gaps",
    "blockers",
    "uncertainties",
    "dimensions",
}
REQUIRED_STRATEGY_FIELDS = {
    "eligibility",
    "role_family_id",
    "fit_now",
    "fit_by_interview",
    "fit_on_the_job",
    "interview_days",
    "estimated_preparation_hours",
    "strategy_gaps",
    "preparation_plan",
}
REQUIRED_READINESS_FIELDS = {
    "report_id",
    "profile_version_id",
    "engine_version",
    "priority",
    "readiness_score",
    "evidence_matches",
    "credibility_warnings",
    "cv_tailoring_points",
    "talking_points",
    "interview_questions",
    "revision_topics",
    "checklist",
}


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _get_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
        return response.read()


def _contains_text(text: str, expected: str) -> bool:
    return expected.casefold() in text.casefold()


def _is_versioned_private_profile(value: object) -> bool:
    return isinstance(value, str) and bool(
        re.fullmatch(r"[a-z0-9][a-z0-9._-]*:v[1-9][0-9]*", value)
    )


def _validate_evaluation_contract(item: dict[str, object], title: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    profile = item.get("profile_version_id")
    engine = item.get("engine_version")

    if engine == LEGACY_ENGINE:
        if profile != LEGACY_PROFILE:
            findings.append(
                {"severity": "error", "message": f"{title}: legacy engine/profile pair is invalid."}
            )
        return findings

    if engine not in PRIVATE_ENGINES:
        findings.append(
            {"severity": "error", "message": f"{title}: unexpected review engine version."}
        )
        return findings

    if not _is_versioned_private_profile(profile):
        findings.append(
            {"severity": "error", "message": f"{title}: private profile version is invalid."}
        )

    missing_strategy = sorted(field for field in REQUIRED_STRATEGY_FIELDS if field not in item)
    if missing_strategy:
        findings.append(
            {
                "severity": "error",
                "message": f"{title}: missing strategy fields: {', '.join(missing_strategy)}",
            }
        )
        return findings

    for field in ("fit_now", "fit_by_interview", "fit_on_the_job"):
        value = item.get(field)
        if not isinstance(value, int) or not 0 <= value <= 100:
            findings.append(
                {"severity": "error", "message": f"{title}: invalid {field.replace('_', ' ')}."}
            )

    fit_now = item.get("fit_now")
    fit_by_interview = item.get("fit_by_interview")
    fit_on_the_job = item.get("fit_on_the_job")
    if (
        isinstance(fit_now, int)
        and isinstance(fit_by_interview, int)
        and isinstance(fit_on_the_job, int)
    ):
        if not fit_now <= fit_by_interview <= fit_on_the_job:
            findings.append(
                {
                    "severity": "error",
                    "message": f"{title}: strategy fit progression is inconsistent.",
                }
            )
        if item.get("ranking_score") != fit_by_interview:
            findings.append(
                {
                    "severity": "error",
                    "message": f"{title}: ranking score does not match interview-ready fit.",
                }
            )

    interview_days = item.get("interview_days")
    if not isinstance(interview_days, int) or interview_days < 0:
        findings.append({"severity": "error", "message": f"{title}: invalid interview window."})
    preparation_hours = item.get("estimated_preparation_hours")
    if not isinstance(preparation_hours, int) or preparation_hours < 0:
        findings.append({"severity": "error", "message": f"{title}: invalid preparation estimate."})
    if not isinstance(item.get("strategy_gaps"), list):
        findings.append({"severity": "error", "message": f"{title}: strategy gaps are invalid."})
    if not isinstance(item.get("preparation_plan"), list):
        findings.append({"severity": "error", "message": f"{title}: preparation plan is invalid."})
    return findings


def audit(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    health = _get_json(f"{API_BASE}/api/health")
    opportunities = _get_json(f"{API_BASE}/api/opportunities")
    captures = _get_json(f"{API_BASE}/api/captures")

    if not isinstance(opportunities, list):
        raise RuntimeError("Opportunity API did not return a list.")

    findings: list[dict[str, str]] = []
    readiness_histories: dict[str, object] = {}
    pack_dir = output_dir / "preparation-packs"
    pack_dir.mkdir(exist_ok=True)
    preparation_pack_count = 0
    readiness_history_count = 0

    for item in opportunities:
        if not isinstance(item, dict):
            findings.append({"severity": "error", "message": "Non-object opportunity returned."})
            continue
        title = str(item.get("title") or "Untitled opportunity")
        missing = sorted(field for field in REQUIRED_REVIEW_FIELDS if field not in item)
        if missing:
            findings.append(
                {
                    "severity": "error",
                    "message": f"{title}: missing automated-review fields: {', '.join(missing)}",
                }
            )
        findings.extend(_validate_evaluation_contract(item, title))

        score = item.get("ranking_score")
        if not isinstance(score, int) or not 0 <= score <= 100:
            findings.append({"severity": "error", "message": f"{title}: invalid ranking score."})
        if item.get("review_decision") and item.get("proposed_decision") != item.get(
            "review_decision"
        ):
            findings.append(
                {
                    "severity": "info",
                    "message": f"{title}: human decision overrides the automated proposal.",
                }
            )
        if not item.get("fit_summary"):
            findings.append({"severity": "warning", "message": f"{title}: empty fit summary."})
        if not item.get("strengths") and not item.get("gaps"):
            findings.append(
                {"severity": "warning", "message": f"{title}: no strengths or gaps recorded."}
            )

        readiness = item.get("readiness")
        if not isinstance(readiness, dict):
            findings.append(
                {"severity": "error", "message": f"{title}: readiness report is missing."}
            )
        else:
            missing_readiness = sorted(
                field for field in REQUIRED_READINESS_FIELDS if field not in readiness
            )
            if missing_readiness:
                findings.append(
                    {
                        "severity": "error",
                        "message": f"{title}: missing readiness fields: {', '.join(missing_readiness)}",
                    }
                )
            if readiness.get("profile_version_id") != LEGACY_PROFILE:
                findings.append(
                    {
                        "severity": "error",
                        "message": f"{title}: readiness profile version is unexpected.",
                    }
                )
            if readiness.get("engine_version") != EXPECTED_READINESS_ENGINE:
                findings.append(
                    {
                        "severity": "error",
                        "message": f"{title}: readiness engine version is unexpected.",
                    }
                )
            readiness_score = readiness.get("readiness_score")
            if not isinstance(readiness_score, int) or not 0 <= readiness_score <= 100:
                findings.append(
                    {"severity": "error", "message": f"{title}: invalid readiness score."}
                )
            if not readiness.get("checklist"):
                findings.append(
                    {"severity": "warning", "message": f"{title}: readiness checklist is empty."}
                )

        posting_id = str(item.get("posting_id") or "")
        if posting_id:
            try:
                history = _get_json(f"{API_BASE}/api/opportunities/{posting_id}/readiness/history")
                readiness_histories[posting_id] = history
                if not isinstance(history, list) or not history:
                    raise RuntimeError("history endpoint returned no reports")
                current_reports = [
                    report
                    for report in history
                    if isinstance(report, dict) and report.get("is_current") is True
                ]
                if len(current_reports) != 1:
                    raise RuntimeError("history must contain exactly one current report")
                current_report = current_reports[0]
                if isinstance(readiness, dict) and current_report.get("report_id") != readiness.get(
                    "report_id"
                ):
                    raise RuntimeError(
                        "current history report does not match opportunity readiness"
                    )
                readiness_history_count += 1
            except Exception as exc:  # noqa: BLE001
                findings.append(
                    {
                        "severity": "error",
                        "message": f"{title}: readiness history failed: {exc}",
                    }
                )

            try:
                pack = _get_bytes(f"{API_BASE}/api/opportunities/{posting_id}/preparation-pack")
                if not pack.startswith(b"PK"):
                    raise RuntimeError("response is not a ZIP archive")
                (pack_dir / f"{posting_id}.zip").write_bytes(pack)
                preparation_pack_count += 1
            except Exception as exc:  # noqa: BLE001
                findings.append(
                    {"severity": "error", "message": f"{title}: preparation pack failed: {exc}"}
                )

    (output_dir / "health.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
    (output_dir / "opportunities.json").write_text(
        json.dumps(opportunities, indent=2), encoding="utf-8"
    )
    (output_dir / "captures.json").write_text(json.dumps(captures, indent=2), encoding="utf-8")
    (output_dir / "readiness-histories.json").write_text(
        json.dumps(readiness_histories, indent=2), encoding="utf-8"
    )

    console_messages: list[str] = []
    page_errors: list[str] = []
    expanded_history_visible = False
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        page.on(
            "console",
            lambda message: console_messages.append(f"{message.type}: {message.text}"),
        )
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        page.goto(
            APP_URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        page.locator("#root").wait_for(
            state="attached",
            timeout=30_000,
        )

        first_title = ""
        if opportunities and isinstance(opportunities[0], dict):
            first_title = str(
                opportunities[0].get("title") or ""
            ).strip()

        page.wait_for_function(
            """([expectedCount, expectedTitle]) => {
                const text = document.body?.innerText || "";
                const countReady =
                    text.includes(`all (${expectedCount})`);
                const titleReady =
                    Boolean(expectedTitle) &&
                    text.includes(expectedTitle);
                return countReady || titleReady;
            }""",
            arg=[len(opportunities), first_title],
            timeout=60_000,
        )
        page.screenshot(
            path=output_dir / "workbench-full.png",
            full_page=True,
        )
        visible_text = page.locator("body").inner_text()
        history_details = page.locator("details").filter(has_text="Readiness report history")
        if opportunities and history_details.count() > 0:
            first_history = history_details.first
            first_history.evaluate("element => { element.open = true; }")
            page.wait_for_timeout(250)
            page.screenshot(path=output_dir / "workbench-readiness-history.png", full_page=True)
            expanded_text = page.locator("body").inner_text()
            expanded_history_visible = bool(first_history.get_attribute("open") is not None) and (
                _contains_text(expanded_text, "Recalculate readiness")
                or _contains_text(expanded_text, "Current report")
            )
            (output_dir / "workbench-readiness-history-text.txt").write_text(
                expanded_text, encoding="utf-8"
            )
        (output_dir / "workbench-visible-text.txt").write_text(visible_text, encoding="utf-8")
        browser.close()

    if page_errors:
        findings.extend(
            {"severity": "error", "message": f"Browser error: {error}"} for error in page_errors
        )
    automated_review_visible = _contains_text(visible_text, "Automated proposed decision")
    readiness_visible = _contains_text(visible_text, "Application readiness")
    preparation_download_visible = _contains_text(visible_text, "Download preparation pack")
    readiness_history_control_visible = _contains_text(visible_text, "Readiness report history")
    if opportunities and not automated_review_visible:
        findings.append(
            {
                "severity": "error",
                "message": "Automated review data exists but is not visible in the workbench.",
            }
        )
    if opportunities and not readiness_visible:
        findings.append(
            {
                "severity": "error",
                "message": "Readiness data exists but is not visible in the workbench.",
            }
        )
    if opportunities and not preparation_download_visible:
        findings.append(
            {
                "severity": "error",
                "message": "Preparation-pack download is not visible in the workbench.",
            }
        )
    if opportunities and not readiness_history_control_visible:
        findings.append(
            {
                "severity": "error",
                "message": "Readiness-history controls are not visible in the workbench.",
            }
        )
    if opportunities and not expanded_history_visible:
        findings.append(
            {
                "severity": "error",
                "message": "Readiness history could not be expanded in the workbench.",
            }
        )

    summary: dict[str, object] = {
        "status": "failed" if any(item["severity"] == "error" for item in findings) else "passed",
        "opportunity_count": len(opportunities),
        "capture_count": len(captures) if isinstance(captures, list) else None,
        "preparation_pack_count": preparation_pack_count,
        "readiness_history_count": readiness_history_count,
        "automated_review_visible": automated_review_visible,
        "readiness_visible": readiness_visible,
        "preparation_download_visible": preparation_download_visible,
        "readiness_history_control_visible": readiness_history_control_visible,
        "expanded_history_visible": expanded_history_visible,
        "findings": findings,
        "console_messages": console_messages,
        "page_errors": page_errors,
    }
    (output_dir / "audit-summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = audit(args.output_dir)
    print(json.dumps(summary, indent=2))
    return 1 if summary["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
