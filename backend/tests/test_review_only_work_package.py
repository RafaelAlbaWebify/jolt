from jolt.unified_ai_work_package import build_review_only_work_package_json


def test_review_only_export_does_not_build_other_sections(monkeypatch) -> None:
    import json

    import jolt.unified_ai_work_package as work

    monkeypatch.setattr(work, "build_global_context_snapshot", lambda: {})
    monkeypatch.setattr(work, "global_context_version", lambda _: "test-context")
    monkeypatch.setattr(work, "build_candidate_evidence_ledger", lambda _: {"source_evidence": []})
    monkeypatch.setattr(work, "_review_inbox_payload", lambda _: {"jobs": []})
    monkeypatch.setattr(work, "enrich_review_inbox_with_dossiers", lambda review, evidence: review)
    monkeypatch.setattr(work, "attach_preflight", lambda review: review)
    monkeypatch.setattr(work, "attach_captured_official_sources", lambda session, review: review)
    monkeypatch.setattr(work, "build_review_protocol", lambda: {})

    def fail(*args, **kwargs):
        raise AssertionError("Unrelated market exchange must not run")

    monkeypatch.setattr(work, "build_market_intelligence_exchange", fail)
    payload = json.loads(build_review_only_work_package_json(None))
    assert payload["contract_type"] == "jolt_ai_work_package"
    assert payload["review_inbox"] == {"jobs": []}
    assert payload["exchanges"] == []
