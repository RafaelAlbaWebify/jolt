"""Official Jobgether public API, bounded read-only preview.

Endpoint: https://jobgether.com/api/v1/jobs (no account or key required).
No persistence; use returned URLs as Jobgether listing references only.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request


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
