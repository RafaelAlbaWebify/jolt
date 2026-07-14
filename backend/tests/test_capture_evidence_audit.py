from jolt.capture_evidence_audit import audit_capture_evidence


def _summary() -> dict[str, object]:
    return {
        "capture_run_id": "run-1",
        "source": "linkedin",
        "mode": "supervised_live",
        "status": "completed_with_warnings",
        "search_url": "https://example.test/search",
        "warnings": ["one rejected item"],
        "requested_item_limit": 2,
        "observed_item_count": 2,
        "stop_reason": "requested_limit_reached",
        "started_at": "2026-07-14T10:00:00+00:00",
        "completed_at": "2026-07-14T10:01:00+00:00",
        "total_items": 2,
        "verified_items": 1,
        "rejected_items": 1,
    }


def test_capture_evidence_audit_accepts_current_and_legacy_artifacts() -> None:
    summary = _summary()
    detail = {
        **summary,
        "pages": [],
        "items": [
            {
                "source_job_id": "verified",
                "detail_status": "verified",
                "posting_id": "posting-1",
                "source_document_id": "source-1",
                "artifact_id": "artifact-1",
                "artifact_hash": "a" * 64,
            },
            {
                "source_job_id": "rejected",
                "detail_status": "rejected_unverified",
                "posting_id": None,
                "source_document_id": None,
                "artifact_id": None,
                "artifact_hash": None,
            },
        ],
    }

    details, findings, metrics = audit_capture_evidence([summary], lambda _: detail)

    assert details == {"run-1": detail}
    assert findings == []
    assert metrics == {
        "capture_detail_count": 1,
        "capture_item_count": 2,
        "capture_artifact_count": 1,
        "legacy_capture_item_count": 1,
    }


def test_capture_evidence_audit_reports_broken_chain() -> None:
    summary = _summary()
    detail = {
        **summary,
        "observed_item_count": 3,
        "stop_reason": "",
        "pages": [],
        "items": [
            {
                "source_job_id": "verified",
                "detail_status": "verified",
                "posting_id": None,
                "source_document_id": None,
                "artifact_id": "artifact-1",
                "artifact_hash": "not-a-hash",
            },
            {
                "source_job_id": "rejected",
                "detail_status": "rejected_unverified",
                "posting_id": "posting-2",
                "source_document_id": "source-2",
                "artifact_id": None,
                "artifact_hash": None,
            },
        ],
    }

    _, findings, metrics = audit_capture_evidence([summary], lambda _: detail)

    messages = {finding["message"] for finding in findings}
    assert "Capture run-1: summary and detail metadata differ." in messages
    assert "Capture run-1: observed count does not equal persisted item count." in messages
    assert "Capture run-1: observed count exceeds requested limit." in messages
    assert "Capture run-1: stop reason is missing." in messages
    assert "Capture run-1/verified: verified item lacks canonical linkage." in messages
    assert "Capture run-1/verified: artifact hash is not hexadecimal SHA-256." in messages
    assert "Capture run-1/rejected: rejected item has canonical linkage." in messages
    assert metrics["capture_detail_count"] == 1
