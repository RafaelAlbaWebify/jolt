from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LIKELY_TARGET_TITLE = re.compile(
    r"\b(?:technical support|it support|help desk|service desk|application support|"
    r"product support|customer technical support|end user support|2nd line support|"
    r"second line support|first level it support|level 2 it support|support engineer|"
    r"technical support specialist|application support specialist|product support specialist|"
    r"network support|network engineer|noc engineer|active directory|m365|microsoft 365|"
    r"cloud identity|identity engineer|data entry specialist|data quality|"
    r"cyber security analyst|cybersecurity analyst|soc analyst|support service manager|"
    r"service delivery manager|technical support manager)\b",
    re.IGNORECASE,
)
SUPPORT_OR_NETWORK_TITLE = re.compile(
    r"\b(?:technical support|it support|application support|product support|"
    r"customer technical support|end user support|service desk|help desk|"
    r"network support|network engineer|noc engineer|identity engineer|"
    r"active directory|m365|microsoft 365)\b",
    re.IGNORECASE,
)
PREPARATION_REVIEW_THRESHOLD = 40


def _get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def semantic_findings(opportunity: dict[str, Any]) -> list[dict[str, str]]:
    title = str(opportunity.get("title") or "").strip()
    role_family = opportunity.get("role_family_id")
    recommendation = str(opportunity.get("recommendation") or "")
    preparation_hours = opportunity.get("estimated_preparation_hours")
    findings: list[dict[str, str]] = []

    if title and LIKELY_TARGET_TITLE.search(title) and not role_family:
        findings.append(
            {
                "severity": "warning",
                "code": "likely_target_missing_role_family",
                "posting_id": str(opportunity.get("posting_id") or ""),
                "message": f"Likely target title has no role family: {title}.",
            }
        )

    if title and SUPPORT_OR_NETWORK_TITLE.search(title) and recommendation == "do_not_pursue":
        findings.append(
            {
                "severity": "warning",
                "code": "support_title_rejected",
                "posting_id": str(opportunity.get("posting_id") or ""),
                "message": f"Support/network-oriented title is rejected and needs review: {title}.",
            }
        )

    if isinstance(preparation_hours, int) and preparation_hours > PREPARATION_REVIEW_THRESHOLD:
        findings.append(
            {
                "severity": "warning",
                "code": "preparation_hours_high",
                "posting_id": str(opportunity.get("posting_id") or ""),
                "message": (
                    f"Preparation estimate exceeds {PREPARATION_REVIEW_THRESHOLD} hours: "
                    f"{title or opportunity.get('posting_id')} ({preparation_hours} hours)."
                ),
            }
        )

    return findings


def run_semantic_audit(api_url: str, output_path: Path) -> dict[str, object]:
    opportunities = _get_json(f"{api_url.rstrip('/')}/api/opportunities")
    if not isinstance(opportunities, list):
        raise ValueError("Opportunity API did not return a list.")

    findings = [
        finding for opportunity in opportunities for finding in semantic_findings(opportunity)
    ]
    counts: dict[str, int] = {}
    for finding in findings:
        code = finding["code"]
        counts[code] = counts.get(code, 0) + 1

    summary: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "api_url": api_url,
        "opportunity_count": len(opportunities),
        "finding_count": len(findings),
        "finding_counts_by_code": counts,
        "findings": findings,
        "result": "review" if findings else "passed",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, ensure_ascii=True), encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run semantic checks over JOLT opportunities.")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    summary = run_semantic_audit(arguments.api_url, arguments.output)
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
