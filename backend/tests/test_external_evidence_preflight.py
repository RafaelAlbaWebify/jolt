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
        {
            "url": "https://jobs.lever.co/acme/abc",
            "source": "captured_text",
            "verification_status": "unverified_candidate",
        }
    ]


def test_preflight_keeps_jobs_and_counts_unverified_candidates() -> None:
    inbox = {
        "jobs": [
            {
                "analysis_text": "https://boards.greenhouse.io/acme/jobs/1",
                "source_url": "https://www.linkedin.com/jobs/view/1/",
            },
            {"analysis_text": "No external link", "source_url": ""},
        ]
    }
    output = attach_preflight(inbox)
    assert output is not None
    assert output["preflight_metadata"]["jobs_processed"] == 2
    assert output["preflight_metadata"]["jobs_with_official_candidate_links"] == 1
    assert output["preflight_metadata"]["externally_verified_jobs"] == 0


def test_easy_apply_sort_is_secondary_to_decision() -> None:
    assert sort_application_priority(0, 20, False, "a") < sort_application_priority(
        1, 99, True, "b"
    )
    assert sort_application_priority(0, 20, True, "a") < sort_application_priority(
        0, 99, False, "b"
    )
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


def test_job_specific_application_control_survives_preflight() -> None:
    job = {
        "source_url": "https://www.linkedin.com/jobs/view/100/",
        "outbound_application_url": "https://jobs.lever.co/acme/abc",
        "application_method": "external_apply",
        "easy_apply_available": False,
        "easy_apply_observed_at": "2026-10-27T12:00:00+00:00",
        "analysis_text": "IT Support, Vigo",
    }
    evidence = build_job_preflight(job)
    assert evidence["official_source_candidates"][0]["source"] == "captured_apply_control"
    assert evidence["easy_apply_available"] is False
    assert evidence["needs_ui_observation"] is False
    assert evidence["application_url"] == job["outbound_application_url"]


def test_discovery_without_configured_api_key_remains_explicit(monkeypatch) -> None:
    from jolt.official_ats_discovery import discover_ats_candidates

    monkeypatch.delenv("JOLT_BRAVE_SEARCH_API_KEY", raising=False)
    assert discover_ats_candidates(title="IT Support", company="Acme") == {
        "status": "provider_not_configured",
        "candidates": [],
    }


def test_corporate_dxc_apply_url_is_candidate_not_verified() -> None:
    job = {
        "source_url": "https://www.linkedin.com/jobs/view/4478107931/",
        "outbound_application_url": "https://careers.dxc.com/job/24002544/sap-abap-any-city-es/",
        "easy_apply_available": False,
        "analysis_text": "SAP ABAP role",
    }
    evidence = build_job_preflight(job)
    assert evidence["official_source_candidates"][0]["url"] == job["outbound_application_url"]
    assert evidence["official_source_candidates"][0]["source"] == "captured_apply_control"
    assert evidence["external_source_status"] == "not_checked"


def test_preflight_uses_observed_outbound_application_url() -> None:
    result = build_job_preflight(
        {
            "source_url": "https://www.linkedin.com/jobs/view/123/",
            "analysis_text": "Job description without an ATS link.",
            "outbound_application_url": "https://jobs.lever.co/acme/123",
        }
    )

    assert result["official_source_candidates"] == [
        {
            "url": "https://jobs.lever.co/acme/123",
            "source": "captured_apply_control",
            "verification_status": "unverified_candidate",
        }
    ]
