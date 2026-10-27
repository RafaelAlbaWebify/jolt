from jolt.external_evidence_preflight import (
    attach_preflight,
    build_job_preflight,
    sort_application_priority,
)


def test_no_claim_of_verification_from_text_only() -> None:
    job = {
        "source_url": "https://www.linkedin.com/jobs/view/123/",
        "analysis_text": (
            "Easy Apply. Apply at https://jobs.lever.co/acme/abc "
            "or https://www.linkedin.com/jobs/view/123/"
        ),
    }
    result = build_job_preflight(job)
    assert result["easy_apply_available"] is None
    assert result["easy_apply_text_mention"] is True
    assert result["external_source_status"] == "not_checked"
    assert result["official_source_candidates"] == [
        {"url": "https://jobs.lever.co/acme/abc", "source": "captured_text",
         "verification_status": "unverified_candidate"}
    ]


def test_preflight_keeps_jobs_and_counts_unverified_candidates() -> None:
    inbox = {"jobs": [{"analysis_text": "https://boards.greenhouse.io/acme/jobs/1",
                        "source_url": "https://www.linkedin.com/jobs/view/1/"},
                       {"analysis_text": "No external link", "source_url": ""}]}
    output = attach_preflight(inbox)
    assert output is not None
    assert output["preflight_metadata"]["jobs_processed"] == 2
    assert output["preflight_metadata"]["jobs_with_official_candidate_links"] == 1
    assert output["preflight_metadata"]["externally_verified_jobs"] == 0


def test_easy_apply_sort_is_secondary_to_decision() -> None:
    assert sort_application_priority(0, 20, False, "a") < sort_application_priority(1, 99, True, "b")
    assert sort_application_priority(0, 20, True, "a") < sort_application_priority(0, 99, False, "b")
    assert sort_application_priority(0, 99, None, "a") < sort_application_priority(0, 50, None, "b")

def test_index_sort_prioritizes_easy_apply_inside_same_category() -> None:
    from jolt.ai_review_opportunity_index import AIReviewOpportunityIndexItem, _sort_key

    def entry(method: bool | None, score: int, decision: str) -> AIReviewOpportunityIndexItem:
        return AIReviewOpportunityIndexItem(
            posting_id=f"posting-{method}-{score}-{decision}",
            source_url="https://www.linkedin.com/jobs/view/100/",
            title="IT Support",
            company="Acme",
            location="Vigo",
            ai_review_status="reviewed",
            decision=decision,
            priority_score=score,
            easy_apply_available=method,
        )

    assert _sort_key(entry(True, 50, "pursue")) < _sort_key(entry(None, 99, "pursue"))
    assert _sort_key(entry(False, 99, "pursue")) < _sort_key(entry(True, 50, "conditional"))
