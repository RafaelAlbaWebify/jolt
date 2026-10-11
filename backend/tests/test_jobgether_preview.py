from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from jolt.jobgether_preview import jobgether_identity, preview_jobs, quality_flags


def test_preview_rejects_unbounded_results() -> None:
    with pytest.raises(ValueError, match="1..25"):
        preview_jobs(keyword="support", limit=26)


def test_preview_reads_official_json_without_writing() -> None:
    payload = {
        "jobs": [
            {
                "title": "IT Support",
                "company": "Example",
                "url": "https://jobgether.com/job/example",
                "postedAt": "2026-10-10",
            }
        ]
    }
    response = io.BytesIO(json.dumps(payload).encode())
    with patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=response) as urlopen:
        result = preview_jobs(keyword="IT support", limit=3)
    assert result["count"] == 1
    assert result["jobs"][0]["title"] == "IT Support"
    assert "locations=spain" in urlopen.call_args.args[0].full_url
    assert "sort=date" in urlopen.call_args.args[0].full_url


def test_preview_fails_closed_on_schema_change() -> None:
    with (
        patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=io.BytesIO(b"{}")),
        pytest.raises(ValueError, match="schema"),
    ):
        preview_jobs(keyword="support")


def test_quality_flags_preserve_unverified_records() -> None:
    assert "internship_title" in quality_flags("IT Support Intern", "2026-10-08T00:00:00Z")
    assert "possible_inactive_title" in quality_flags("IT Support (hold)", None)
    assert "missing_posted_at" in quality_flags("IT Support", None)
    assert "unparseable_posted_at" in quality_flags("IT Support", "not-a-date")


def test_jobgether_offer_identity_requires_canonical_host_and_offer_path() -> None:
    key = "6ac85207480485773199660a"
    assert jobgether_identity(f"https://jobgether.com/offer/{key}-role-name") == key
    assert jobgether_identity(f"https://www.jobgether.com/offer/{key}-role-name") == key
    assert jobgether_identity(f"https://untrusted.example/offer/{key}-role-name") is None
    assert jobgether_identity("https://jobgether.com/jobs?keyword=support") is None
    assert jobgether_identity("https://jobgether.com/offer/not-valid") is None


def test_preview_prefers_documented_api_id() -> None:
    key = "6ac85207480485773199660a"
    payload = {
        "jobs": [
            {
                "id": key,
                "url": "https://jobgether.com/offer/new-url-format",
                "title": "IT Support",
            }
        ]
    }
    response = io.BytesIO(json.dumps(payload).encode())
    with patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=response):
        result = preview_jobs(keyword="support")
    assert result["jobs"][0]["source_job_id"] == key
    assert result["jobs"][0]["identity_status"] == "observed_unverified"


def test_preview_fails_closed_on_id_mismatch() -> None:
    payload = {
        "jobs": [
            {
                "id": "6ac85207480485773199660a",
                "url": "https://jobgether.com/offer/6ac700878a27695aea3b995e-other",
                "title": "IT Support",
            }
        ]
    }
    response = io.BytesIO(json.dumps(payload).encode())
    with patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=response):
        result = preview_jobs(keyword="support")
    assert result["jobs"][0]["source_job_id"] is None
    assert result["jobs"][0]["identity_mismatch"] is True


def test_preview_preserves_official_eligibility_metadata() -> None:
    payload = {
        "jobs": [
            {
                "id": "6ac85207480485773199660a",
                "title": "Support Engineer",
                "url": ("https://jobgether.com/offer/6ac85207480485773199660a-support-engineer"),
                "remote": "Full Remote",
                "contractType": "Full time",
                "experience": "Mid-level (2-5 years)",
                "salaryRange": "35000-45000 EUR",
                "jobFunctions": ["IT Support", "Technical Support"],
            }
        ]
    }
    response = io.BytesIO(json.dumps(payload).encode())
    with patch("jolt.jobgether_preview.urllib.request.urlopen", return_value=response):
        row = preview_jobs(keyword="support")["jobs"][0]
    assert row["remote"] == "Full Remote"
    assert row["contract_type"] == "Full time"
    assert row["experience"] == "Mid-level (2-5 years)"
    assert row["salary_range"] == "35000-45000 EUR"
    assert row["job_functions"] == ["IT Support", "Technical Support"]
    assert row["identity_status"] == "observed_unverified"
