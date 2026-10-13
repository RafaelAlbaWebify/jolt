"""Read-only Jobgether offer detail acceptance probe.

Example: python -m jolt.jobgether_detail_probe --url https://jobgether.com/offer/...
No database access or posting promotion occurs.
"""

from __future__ import annotations

import argparse
import json

from jolt.jobgether_detail_fetch import fetch_jobgether_detail
from jolt.jobgether_preview import jobgether_identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Canonical Jobgether offer URL")
    args = parser.parse_args()
    identifier = jobgether_identity(args.url)
    if identifier is None:
        parser.error("Expected an official HTTPS Jobgether offer URL with a 24-character ID")
    try:
        result = fetch_jobgether_detail(observed_id=identifier, observed_url=args.url)
    except (OSError, ValueError) as exc:
        print(json.dumps({"source_job_id": identifier, "status": "unresolved", "error": str(exc)}))
        return 1
    summary = {key: value for key, value in result.items() if key != "description"}
    summary["description_length"] = len(result.get("description") or "")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "structured_detail_present" else 2


if __name__ == "__main__":
    raise SystemExit(main())
