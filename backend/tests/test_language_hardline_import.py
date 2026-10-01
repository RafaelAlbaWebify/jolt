from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jolt.ai_review_import import AIReviewImportRequest, import_ai_review
from jolt.database import (
    AIReview,
    CaptureItem,
    CaptureRun,
    Posting,
    SourceDocument,
    create_session_factory,
)
from jolt.job_search_preferences import JobSearchPreferences


def _preferences() -> JobSearchPreferences:
    return JobSearchPreferences(
        languages=["Spanish", "English"],
        language_levels={
            "Spanish": "native",
            "English": "professional",
        },
    )


def _seed(tmp_path, raw_text: str):
    database_url = f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}"
    factory = create_session_factory(database_url)
    now = datetime.now(UTC)

    with factory() as session:
        source = SourceDocument(
            id="source-language",
            source_type="linkedin_live",
            source_url="https://www.linkedin.com/jobs/view/language-test/",
            raw_text=raw_text,
            content_hash="a" * 64,
            captured_at=now,
        )
        capture = CaptureRun(
            id="capture-language",
            source="linkedin",
            mode="supervised_live",
            status="completed",
            search_url="https://www.linkedin.com/jobs/search/",
            warnings_json="[]",
            requested_item_limit=1,
            observed_item_count=1,
            stop_reason="completed",
            started_at=now,
            completed_at=now,
        )
        session.add_all([source, capture])
        session.flush()
        posting = Posting(
            id="posting-language",
            source_document_id=source.id,
            canonical_url=source.source_url,
            identity_key="linkedin:language-test",
            title="Help Desk Specialist",
            company="Example",
            location="Austria · Remote",
            description=raw_text,
            identity_status="verified",
            created_at=now,
        )
        session.add(posting)
        session.flush()
        session.add(
            CaptureItem(
                id="capture-item-language",
                capture_run_id=capture.id,
                source_job_id="language-test",
                source_url=source.source_url,
                title=posting.title,
                company=posting.company,
                location=posting.location,
                detail_status="verified",
                verification_reasons_json="[]",
                source_document_id=source.id,
                posting_id=posting.id,
            )
        )
        session.commit()

    return factory


def _job(**overrides):
    job = {
        "posting_id": "posting-language",
        "source_job_id": "language-test",
        "hardline_status": "PASS",
        "hardline_reasons": [],
        "location_eligibility": "eligible",
        "location_evidence": ["Test geography."],
        "mandatory_requirements": [],
        "mandatory_requirement_results": [],
        "employment_constraints": [],
        "fit_analysis_allowed": True,
        "technical_fit_percent": 88,
        "final_decision": "pursue",
        "decision_reason": "Good fit.",
        "source_conflict": False,
        "linkedin_work_model": "unknown",
        "official_work_model": "unknown",
        "authoritative_source": "unknown",
        "official_source_url": "",
        "remote_status": "unknown",
        "location_verification_status": "unverified",
        "source_confidence": "unknown",
        "decision": "pursue",
        "priority_score": 88,
        "geography_status": "eligible",
        "clearance_status": "clear",
        "language_status": "clear",
        "technical_fit": 88,
        "duplicate_of_posting_id": None,
        "summary": "Potential match.",
        "reasons": [],
    }
    job.update(overrides)
    return job


def _request(job):
    return AIReviewImportRequest.model_validate(
        {
            "contract_type": "jolt_ai_review",
            "contract_version": "1.2",
            "capture_run_id": "capture-language",
            "review_source": "chatgpt_source_first",
            "review_version": "language-hardline-test",
            "reviewed_at": datetime.now(UTC),
            "jobs": [job],
        }
    )


def test_contract_v12_rejects_ai_pass_for_nortal_language_blocker(
    tmp_path,
    monkeypatch,
) -> None:
    raw_text = (
        "Help Desk Specialist\nNortal\n"
        "Sehr gute Deutsch- sowie gute Englischkenntnisse in Wort und Schrift. "
        "Erfahrung im IT-Support und mit Ticketsystemen."
    )
    factory = _seed(tmp_path, raw_text)
    monkeypatch.setattr(
        "jolt.ai_review_import.load_job_search_preferences",
        _preferences,
    )

    with (
        factory() as session,
        pytest.raises(ValueError, match="deterministic language evidence"),
    ):
        import_ai_review(session, _request(_job()))


def test_contract_v12_accepts_and_persists_language_hard_reject(
    tmp_path,
    monkeypatch,
) -> None:
    raw_text = (
        "Technical Support Engineer. German is mandatory for customer communication. "
        "English is used internally."
    )
    factory = _seed(tmp_path, raw_text)
    monkeypatch.setattr(
        "jolt.ai_review_import.load_job_search_preferences",
        _preferences,
    )

    rejected = _job(
        hardline_status="REJECT",
        hardline_reasons=["Mandatory German is not in the candidate profile."],
        fit_analysis_allowed=False,
        technical_fit_percent=None,
        technical_fit=None,
        final_decision="reject",
        decision="reject",
        priority_score=0,
        language_status="blocked",
        summary="Rejected by language hardline.",
    )

    with factory() as session:
        response = import_ai_review(session, _request(rejected))
        assert response.created_count == 1

        stored = session.query(AIReview).one()
        assert stored.decision == "reject"
        assert stored.language_status == "blocked"
        assert "LANGUAGE_REQUIREMENT_UNMET" in stored.hardline_reasons_json


def test_contract_v12_rejects_ai_pass_for_unsupported_job_language(
    tmp_path,
    monkeypatch,
) -> None:
    raw_text = (
        "Wir suchen eine erfahrene Person für unseren technischen Support. "
        "Die Aufgabe umfasst die Bearbeitung von Anfragen, die Analyse von Störungen "
        "und die Zusammenarbeit mit unserem internationalen Team. Sie unterstützen "
        "unsere Kunden bei technischen Problemen und dokumentieren Lösungen sorgfältig. "
        "Wir bieten eine moderne Arbeitsumgebung, flexible Prozesse und die Möglichkeit, "
        "Verantwortung zu übernehmen. Erfahrung mit Windows, Netzwerken und Ticketsystemen "
        "ist hilfreich. Sie arbeiten selbstständig und zuverlässig mit dem Team zusammen."
    )
    factory = _seed(tmp_path, raw_text)
    monkeypatch.setattr(
        "jolt.ai_review_import.load_job_search_preferences",
        _preferences,
    )

    with (
        factory() as session,
        pytest.raises(ValueError, match="deterministic language evidence"),
    ):
        import_ai_review(session, _request(_job()))
