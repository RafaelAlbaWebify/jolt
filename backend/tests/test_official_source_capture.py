from __future__ import annotations

from datetime import UTC, datetime

from jolt.database import Posting, SourceDocument, create_session_factory
from jolt.official_source_capture import (
    allowed_source_url,
    attach_captured_official_sources,
    capture_official_candidates,
)


def test_ats_url_allowlist_rejects_redirect_targets_and_non_https() -> None:
    assert allowed_source_url("https://jobs.lever.co/example/123")
    assert allowed_source_url("https://boards.greenhouse.io/example/jobs/123")
    assert not allowed_source_url("http://jobs.lever.co/example/123")
    assert not allowed_source_url("https://jobs.lever.co.evil.test/x")
    assert not allowed_source_url("https://127.0.0.1:1234/admin")
    assert not allowed_source_url("https://www.linkedin.com/jobs/view/3/")


def test_real_capture_is_persisted_but_identity_not_automatically_verified(
    tmp_path, monkeypatch
) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    source = SourceDocument(
        id="source-1",
        source_type="linkedin_live",
        source_url="https://www.linkedin.com/jobs/view/100/",
        raw_text="IT Support",
        content_hash="sha-1",
        captured_at=datetime.now(UTC),
    )
    posting = Posting(
        id="posting-1",
        source_document_id=source.id,
        canonical_url=source.source_url,
        identity_key="linkedin:100",
        title="IT Support",
        company="Acme",
        location="Vigo",
        description="IT Support",
        identity_status="verified",
        created_at=datetime.now(UTC),
    )
    session.add_all([source, posting])
    session.commit()
    from jolt import official_source_capture as capture

    monkeypatch.setattr(capture, "_robots_permits", lambda _url: True)
    monkeypatch.setattr(
        capture,
        "_open_limited",
        lambda _url: (
            200,
            b"<html><body><h1>IT Support</h1><p>Vigo</p></body></html>",
            "text/html",
        ),
    )
    monkeypatch.setattr(capture.time, "sleep", lambda _seconds: None)

    inbox = {
        "jobs": [
            {
                "posting_id": posting.id,
                "external_evidence_preflight": {
                    "official_source_candidates": [
                        {
                            "url": "https://jobs.lever.co/example/123",
                            "source": "captured_apply_control",
                            "verification_status": "unverified_candidate",
                        }
                    ]
                },
            }
        ]
    }
    try:
        result = capture_official_candidates(session, inbox)
        assert result["attempted"] == 1
        assert result["results"][0]["status"] == "captured_identity_unverified"
        enriched = attach_captured_official_sources(session, inbox)
        assert enriched is not None
        samples = enriched["jobs"][0]["external_evidence_preflight"]["captured_official_sources"]
        assert len(samples) == 1
        assert "IT Support" in samples[0]["captured_text_excerpt"]
        assert samples[0]["authority"] == "candidate_official_ats_not_verified_job_identity"
        cached = capture_official_candidates(session, inbox)
        assert cached["attempted"] == 0
        assert cached["cached_fresh"] == 1
    finally:
        session.close()
