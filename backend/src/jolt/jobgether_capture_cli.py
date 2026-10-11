"""Run a bounded Jobgether API observation; writes only with --commit.

No Postings, Reviews or Applications are created by this workflow.
"""

from __future__ import annotations

import argparse
import json
from urllib.parse import urlencode

from jolt.database import create_session_factory
from jolt.jobgether_observations import stage_jobgether_observations
from jolt.jobgether_preview import preview_jobs


def run(*, keyword: str, location: str, limit: int, commit: bool) -> dict:
    preview = preview_jobs(keyword=keyword, location=location, limit=limit)
    if not commit:
        return {
            **preview,
            "committed": False,
            "message": "Read-only preview. Use --commit to stage observations.",
        }
    url = "https://jobgether.com/api/v1/jobs?" + urlencode(
        {"keyword": keyword, "locations": location, "limit": limit, "page": 1}
    )
    factory = create_session_factory()
    with factory() as session:
        try:
            result = stage_jobgether_observations(
                session, search_url=url, jobs=preview["jobs"]
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
    return {**result, "committed": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keyword", default="IT support")
    parser.add_argument("--location", default="spain")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run(
                keyword=args.keyword,
                location=args.location,
                limit=args.limit,
                commit=args.commit,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
