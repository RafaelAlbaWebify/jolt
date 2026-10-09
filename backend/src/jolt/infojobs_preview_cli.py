"""Read-only InfoJobs preview. Requires developer app credentials in environment."""

from __future__ import annotations

import argparse
import json

from jolt.infojobs_adapter import preview_search


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--province", default="")
    parser.add_argument("--max-pages", type=int, default=2)
    parser.add_argument("--max-offers", type=int, default=20)
    args = parser.parse_args()
    try:
        results = preview_search(
            args.keywords,
            page_limit=args.max_pages,
            result_limit=args.max_offers,
            province=args.province,
        )
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"InfoJobs preview failed: {exc}\n")
    print(
        json.dumps(
            {
                "source": "infojobs",
                "mode": "read_only_preview",
                "total": len(results),
                "offers": [
                    {
                        "source_job_id": entry.candidate.source_job_id,
                        "title": entry.candidate.title,
                        "company": entry.candidate.company,
                        "location": entry.candidate.location,
                        "source_url": entry.candidate.source_url,
                        "description_characters": len(entry.description),
                    }
                    for entry in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
