from __future__ import annotations

from datetime import UTC, datetime

from jolt import skills_preparation_exchange
from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeScope
from jolt.skills_preparation_exchange import build_skills_preparation_exchange
from jolt.unified_ai_work_package import (
    _compact_exchange_for_unified,
    _compact_review_inbox_payload,
)


def _exchange(section: str, evidence: dict) -> AIExchangeInput:
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=f"exchange-{section}",
        context_version="context-1",
        scope=AIExchangeScope(section=section, analysis_types=["audit_result"]),
        context={"duplicate": "context"},
        evidence=evidence,
        protected_state={},
        requested_output={},
    )


def test_review_inbox_compaction_preserves_every_current_job_and_authoritative_text() -> None:
    payload = {
        "jobs": [
            {
                "posting_id": "posting-1",
                "analysis_text": "FULL VACANCY ONE",
                "description_clean": "FULL VACANCY ONE",
                "source_text_clean": "FULL VACANCY ONE",
                "audit": {
                    "source_raw_text": "FULL VACANCY ONE",
                    "source_raw_text_sha256": "hash-1",
                },
            },
            {
                "posting_id": "posting-2",
                "analysis_text": "FULL VACANCY TWO",
                "description_clean": "FULL VACANCY TWO",
                "source_text_clean": "FULL VACANCY TWO",
                "audit": {
                    "source_raw_text": "FULL VACANCY TWO",
                    "source_raw_text_sha256": "hash-2",
                },
            },
        ]
    }

    compact = _compact_review_inbox_payload(payload)

    assert [job["posting_id"] for job in compact["jobs"]] == ["posting-1", "posting-2"]
    assert [job["analysis_text"] for job in compact["jobs"]] == [
        "FULL VACANCY ONE",
        "FULL VACANCY TWO",
    ]
    assert all("description_clean" not in job for job in compact["jobs"])
    assert all("source_text_clean" not in job for job in compact["jobs"])
    assert all("source_raw_text" not in job["audit"] for job in compact["jobs"])
    assert [job["audit"]["source_raw_text_sha256"] for job in compact["jobs"]] == [
        "hash-1",
        "hash-2",
    ]
    metadata = compact["evidence_compaction"]
    assert metadata["current_jobs_available"] == 2
    assert metadata["current_jobs_exported"] == 2
    assert metadata["current_jobs_omitted"] == 0
    assert metadata["authoritative_vacancy_text_field"] == "jobs[].analysis_text"


def test_unified_skills_exchange_uses_canonical_candidate_evidence_without_losing_vacancies() -> (
    None
):
    exchange = _exchange(
        "skills_gaps",
        {
            "vacancies": [{"posting_id": "posting-1", "evidence_text": "SQL required"}],
            "profile_evidence": [
                {"capture_id": "profile-1", "visible_text": "Experience"},
                {"capture_id": "profile-2", "visible_text": "Skills"},
            ],
            "corpus_policy": {"max_recent_vacancies": 300},
        },
    )

    compact = _compact_exchange_for_unified(exchange)

    assert compact.context == {}
    assert compact.evidence["vacancies"] == [
        {"posting_id": "posting-1", "evidence_text": "SQL required"}
    ]
    assert "profile_evidence" not in compact.evidence
    assert compact.evidence["candidate_evidence_location"] == "candidate_evidence"
    assert compact.evidence["unified_compaction"]["profile_evidence_omitted_as_duplicate"] == 2


def test_unified_linkedin_exchange_keeps_non_profile_evidence_and_workflow_state() -> None:
    recommendations = [{"id": "recommendation-1", "status": "pending"}]
    exchange = _exchange(
        "linkedin_profile",
        {
            "captures": [
                {"id": "profile-1", "category": "profile"},
                {"id": "activity-1", "category": "activity"},
                {"id": "public-1", "category": "public_profile"},
                {"id": "network-1", "category": "network"},
            ],
            "existing_recommendations": recommendations,
        },
    )

    compact = _compact_exchange_for_unified(exchange)

    assert compact.evidence["captures"] == [
        {"id": "activity-1", "category": "activity"},
        {"id": "network-1", "category": "network"},
    ]
    assert compact.evidence["existing_recommendations"] == recommendations
    assert compact.evidence["candidate_evidence_location"] == "candidate_evidence"
    metadata = compact.evidence["unified_compaction"]
    assert metadata["profile_captures_omitted_as_duplicate"] == 2
    assert metadata["non_profile_captures_exported"] == 2
    assert metadata["recommendation_workflow_state_preserved"] is True


def test_skills_exchange_declares_historical_corpus_bounds(monkeypatch) -> None:
    monkeypatch.setattr(
        skills_preparation_exchange,
        "build_global_context_snapshot",
        lambda: {"job_search_preferences": {}},
    )
    monkeypatch.setattr(
        skills_preparation_exchange,
        "global_context_version",
        lambda _context: "context-1",
    )
    monkeypatch.setattr(
        skills_preparation_exchange,
        "_vacancy_evidence",
        lambda _session: ([{"posting_id": "p1"}, {"posting_id": "p2"}], 5),
    )
    monkeypatch.setattr(
        skills_preparation_exchange,
        "_profile_evidence",
        lambda _session: [{"capture_id": "profile-1"}],
    )

    exchange = build_skills_preparation_exchange(object())

    assert exchange.evidence["counts"] == {"vacancies": 2, "profile_captures": 1}
    policy = exchange.evidence["corpus_policy"]
    assert policy["max_recent_vacancies"] == 300
    assert policy["available_vacancies"] == 5
    assert policy["exported_vacancies"] == 2
    assert policy["omitted_vacancies"] == 3
    assert "Current Review Inbox vacancies are not affected" in policy["omission_meaning"]
