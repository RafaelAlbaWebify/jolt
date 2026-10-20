from jolt.ai_review_import import AIReviewJob


def _base():
    return dict(
        posting_id="posting-1", source_job_id="job-1",
        priority_score=60, geography_status="conditional",
        clearance_status="unknown", language_status="unknown",
        hardline_status="MANUAL_REVIEW", fit_analysis_allowed=False,
        technical_fit_percent=None, final_decision="conditional",
    )


def test_legacy_ai_reviews_default_to_uncertain_demand():
    review = AIReviewJob.model_validate(_base())
    assert review.employment_track == "unknown"
    assert review.physical_demand_status == "uncertain"
    assert review.physical_demand_evidence == []


def test_ai_review_can_preserve_explicit_physical_job_evidence():
    review = AIReviewJob.model_validate({
        **_base(), "employment_track": "bridge",
        "physical_demand_status": "incompatible",
        "physical_demand_evidence": ["Regular lifting of 25kg boxes"],
        "commercial_pressure_status": "uncertain",
    })
    assert review.physical_demand_status == "incompatible"
    assert review.physical_demand_evidence == ["Regular lifting of 25kg boxes"]


def test_office_jobs_do_not_default_to_incompatible():
    review = AIReviewJob.model_validate({**_base(), "employment_track": "bridge"})
    assert review.physical_demand_status == "uncertain"
