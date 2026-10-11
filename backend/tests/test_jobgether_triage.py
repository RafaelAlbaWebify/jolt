from __future__ import annotations

from jolt.jobgether_triage import triage_jobgether_observation, triage_jobgether_preview


def test_triage_never_asserts_spain_eligibility_or_verified_description() -> None:
    job = {
        "source_job_id": "123",
        "title": "Technical Support Specialist",
        "location": "Europe, Spain",
        "remote": "Full Remote",
        "posted_at": "2026-10-10",
        "quality_flags": [],
    }
    result = triage_jobgether_observation(job)
    assert result["priority"] == "review_first"
    assert result["positive_signals"] == [
        "support_title_match",
        "spain_listed",
        "remote_label",
    ]
    assert result["work_from_spain_verified"] is False
    assert result["full_description_verified"] is False


def test_triage_preserves_stale_internships_and_does_not_mutate_input() -> None:
    jobs = [
        {
            "source_job_id": "old",
            "title": "IT Support Intern",
            "quality_flags": ["older_than_30_days", "internship_title"],
            "posted_at": "2026-08-01",
        },
        {
            "source_job_id": "new",
            "title": "IT Support Engineer",
            "quality_flags": [],
            "posted_at": "2026-10-10",
        },
    ]
    preview = {"jobs": jobs}
    result = triage_jobgether_preview(preview)
    assert result["count"] == 2
    assert [row["source_job_id"] for row in result["ranked"]] == ["new", "old"]
    assert result["ranked"][1]["cautions"] == ["stale_listing", "internship"]
    assert jobs[0]["quality_flags"] == ["older_than_30_days", "internship_title"]


def test_triage_unknown_publication_date_is_caution_not_rejection() -> None:
    row = triage_jobgether_observation({"title": "Service Desk"})
    assert row["priority"] == "review_later"
    assert row["cautions"] == ["unknown_publication_date"]
