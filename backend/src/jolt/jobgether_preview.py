"""Official Jobgether public API, bounded read-only preview.

Endpoint: https://jobgether.com/api/v1/jobs (no account or key required).
No persistence; use returned URLs as Jobgether listing references only.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
import urllib.parse
import urllib.request


def quality_flags(title: str, posted_at: str | None) -> list[str]:
    """Warnings only; never equate a title or age with a verified vacancy status."""
    flags: list[str] = []
    label = title.casefold()
    if any(term in label for term in ("intern", "internship", "prácticas", "becario")):
        flags.append("internship_title")
    if any(term in label for term in ("(hold)", "on hold", "position filled")):
        flags.append("possible_inactive_title")
    if not posted_at:
        flags.append("missing_posted_at")
    else:
        try:
            age = (datetime.now(UTC) - datetime.fromisoformat(posted_at.replace("Z", "+00:00"))).days
            if age > 30:
                flags.append("older_than_30_days")
        except (TypeError, ValueError):
            flags.append("unparseable_posted_at")
    return flags


def preview_jobs(*, keyword: str, location: str = "spain", limit: int = 10) -> dict:
    if not 1 <= limit <= 25:
        raise ValueError("limit must be 1..25")
    query = urllib.parse.urlencode(
        {"keyword": keyword, "locations": location, "limit": limit, "page": 1}
    )
    url = f"https://jobgether.com/api/v1/jobs?{query}"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "JOLT/0.8"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get("jobs"), list):
        raise ValueError("Unexpected Jobgether API response schema")
    rows = []
    for job in payload["jobs"][:limit]:
        if not isinstance(job, dict):
            continue
        rows.append(
            {
                "title": job.get("title"),
                "company": job.get("company"),
                "url": job.get("url"),
                "posted_at": job.get("postedAt"),
                "location": job.get("location"),
                "quality_flags": quality_flags(
                    str(job.get("title") or ""), job.get("postedAt")
                ),
            }
        )
    return {"source": "jobgether", "count": len(rows), "jobs": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", default="IT support")
    parser.add_argument("--location", default="spain")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    print(
        json.dumps(
            preview_jobs(keyword=args.keyword, location=args.location, limit=args.limit),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
