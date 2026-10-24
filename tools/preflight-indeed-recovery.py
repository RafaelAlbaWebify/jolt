"""Read-only acceptance of an Indeed capture ZIP before any persistence attempt.

Extracts the original validated submission payload from the recorded Pydantic
validation error; never connects to the API or database.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


def inspect_archive(path: Path) -> dict:
    if not path.is_file():
        raise ValueError(f"Capture ZIP does not exist: {path}")
    with zipfile.ZipFile(path) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            raise ValueError(f"Corrupt archive member: {corrupt}")
        names = archive.namelist()
        api_names = [name for name in names if name.endswith("/api_result.json") or name == "api_result.json"]
        if len(api_names) != 1:
            raise ValueError(f"Expected exactly one api_result.json, found {len(api_names)}")
        api = json.loads(archive.read(api_names[0]))
        failures = api.get("validation_errors") or []
        inputs = [e.get("input") for e in failures if isinstance(e, dict)]
        payloads = [p for p in inputs if isinstance(p, dict) and isinstance(p.get("items"), list)]
        if not payloads:
            raise ValueError("Original complete request payload not found in validation_errors")
        payload = max(payloads, key=lambda p: len(p["items"]))
        items = payload["items"]
        ids = [item.get("source_job_id") for item in items]
        if not items or not all(isinstance(i, str) and i.strip() for i in ids):
            raise ValueError("Missing durable source_job_id values")
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate source_job_id values in captured request")
        if not all(item.get("identity_verified") is True for item in items):
            raise ValueError("Original request contains unverified job identity")
        if not all(str(item.get("description") or "").strip() for item in items):
            raise ValueError("Original request contains an empty job description")
        pages = payload.get("pages") or []
        page_numbers = [page.get("page_number") for page in pages]
        if page_numbers and sorted(page_numbers) != list(range(1, len(pages) + 1)):
            raise ValueError("Page evidence is not contiguous")
        return {
            "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "archive_members": len(names),
            "item_count": len(items),
            "page_count": len(pages),
            "requested_item_limit": payload.get("requested_item_limit"),
            "all_identities_verified": True,
            "all_descriptions_present": True,
            "recovered_request": payload,
        }


def local_schema_validate(payload: dict, root: Path) -> None:
    sys.path.insert(0, str(root / "backend/src"))
    from jolt.schemas import IndeedLiveCaptureRequest
    IndeedLiveCaptureRequest.model_validate(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("zip", type=Path)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="Optional PRIVATE payload JSON (contains job descriptions)")
    parser.add_argument("--summary", type=Path, help="Optional metadata-only report")
    args = parser.parse_args()
    result = inspect_archive(args.zip)
    try:
        local_schema_validate(result["recovered_request"], args.repo)
        schema_status = "accepted"
    except Exception as exc:
        schema_status = f"rejected: {type(exc).__name__}: {exc}"
    public = {k: v for k, v in result.items() if k != "recovered_request"}
    public["local_schema"] = schema_status
    if args.output and schema_status == "accepted":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result["recovered_request"], ensure_ascii=False, indent=2), encoding="utf-8")
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(public, indent=2), encoding="utf-8")
    print(json.dumps(public, indent=2))
    return 0 if schema_status == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
