from __future__ import annotations

from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import AIExchangeOutput, AIExchangeScope
from jolt.database import create_session_factory
from jolt.unified_ai_work_package import (
    UnifiedAIUpdate,
    build_unified_ai_work_package,
    import_unified_ai_update,
)


def test_unified_package_deduplicates_section_context(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    try:
        package = build_unified_ai_work_package(session)
    finally:
        session.close()

    assert package.contract_type == "jolt_ai_work_package"
    assert package.global_context
    assert len(package.exchanges) == 7
    assert {exchange.scope.section for exchange in package.exchanges} == {
        "market_insights",
        "applications",
        "linkedin_profile",
        "skills_gaps",
        "professional_evidence",
        "search_preferences",
        "data_quality",
    }
    assert all(exchange.context == {} for exchange in package.exchanges)
    assert package.review_inbox is None

    protocol = package.instructions["three_message_review"]
    assert protocol["protocol_version"] == "1.1"
    assert protocol["invocation"]["message_1"] == "Mensaje 1"
    assert protocol["invocation"]["message_2"] == "Mensaje 2"
    assert protocol["invocation"]["resume"] == "Continuar JOLT"
    assert protocol["invocation"]["message_3"] == "Mensaje 3"
    assert "source_context_version" in protocol["checkpoint"]["required"]
    assert "verified_jobs" in protocol["progress_tracking"]["report"]
    assert "jolt_ai_work_package_update" in protocol["stage_3"]["steps"][2]


def test_unified_update_rejects_user_owned_context_patch(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    update = UnifiedAIUpdate(
        package_id="package-1",
        source_context_version="stale-but-patch-validation-runs-first",
        reviewed_at=datetime.now(UTC),
        review_version="unified-v1",
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )
    try:
        with pytest.raises(ValueError, match="non-patchable"):
            import_unified_ai_update(session, update)
    finally:
        session.close()


def test_unified_update_rejects_stale_context_version(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    update = UnifiedAIUpdate(
        package_id="package-1",
        source_context_version="stale-context-version",
        reviewed_at=datetime.now(UTC),
        review_version="unified-v1",
    )
    try:
        with pytest.raises(ValueError, match="stale"):
            import_unified_ai_update(session, update)
    finally:
        session.close()


def test_unified_update_requires_section_context_patch_at_top_level(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    package = build_unified_ai_work_package(session)
    output = AIExchangeOutput(
        exchange_id="market-1",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(section="market_insights", analysis_types=["context_update"]),
        context_patch={"market_summary": {"signal": "example"}},
    )
    update = UnifiedAIUpdate(
        package_id="package-1",
        source_context_version=package.context_version,
        reviewed_at=datetime.now(UTC),
        review_version="unified-v1",
        exchanges=[output],
    )
    try:
        with pytest.raises(ValueError, match="top-level context_patch"):
            import_unified_ai_update(session, update)
    finally:
        session.close()


def test_unified_bundle_prevalidates_all_groups_before_first_import(tmp_path, monkeypatch) -> None:
    import jolt.unified_ai_work_package as unified
    from jolt.ai_review_import import AIReviewImportRequest
    from jolt.unified_ai_work_package import AIReviewBundleImportRequest

    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    package = build_unified_ai_work_package(session)
    requests = [
        AIReviewImportRequest(
            contract_type="jolt_ai_review",
            contract_version="1.0",
            capture_run_id=capture_id,
            review_source="chatgpt_source_first",
            review_version="v1",
            reviewed_at=datetime.now(UTC),
            jobs=[],
        )
        for capture_id in ("capture-valid", "capture-invalid")
    ]
    imported = []

    def preflight(_session, request):
        if request.capture_run_id == "capture-invalid":
            raise ValueError("Invalid second group")

    monkeypatch.setattr(unified, "_validate_capture_membership", preflight)
    monkeypatch.setattr(
        unified, "import_ai_review", lambda _session, request: imported.append(request)
    )
    update = UnifiedAIUpdate(
        package_id=package.package_id,
        source_context_version=package.context_version,
        reviewed_at=datetime.now(UTC),
        review_version="v1",
        review_inbox=AIReviewBundleImportRequest(reviews=requests),
    )
    try:
        with pytest.raises(ValueError, match="Invalid second group"):
            import_unified_ai_update(session, update)
        assert imported == []
    finally:
        session.close()


def test_unified_bundle_rolls_back_first_group_when_second_write_fails(
    tmp_path, monkeypatch
) -> None:
    from sqlalchemy import text

    import jolt.unified_ai_work_package as unified
    from jolt.ai_review_import import AIReviewImportRequest
    from jolt.unified_ai_work_package import AIReviewBundleImportRequest

    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    session.execute(text("CREATE TABLE import_probe (capture_id TEXT NOT NULL)"))
    session.commit()
    package = build_unified_ai_work_package(session)
    requests = [
        AIReviewImportRequest(
            contract_type="jolt_ai_review",
            contract_version="1.0",
            capture_run_id=capture_id,
            review_source="chatgpt_source_first",
            review_version="v1",
            reviewed_at=datetime.now(UTC),
            jobs=[],
        )
        for capture_id in ("capture-one", "capture-two")
    ]
    monkeypatch.setattr(unified, "_validate_capture_membership", lambda *_args: None)

    def importing(group_session, request, *, commit=True):
        assert commit is False
        if request.capture_run_id == "capture-two":
            raise RuntimeError("simulated second-write failure")
        group_session.execute(
            text("INSERT INTO import_probe(capture_id) VALUES (:capture_id)"),
            {"capture_id": request.capture_run_id},
        )
        return None

    monkeypatch.setattr(unified, "import_ai_review", importing)
    update = UnifiedAIUpdate(
        package_id=package.package_id,
        source_context_version=package.context_version,
        reviewed_at=datetime.now(UTC),
        review_version="v1",
        review_inbox=AIReviewBundleImportRequest(reviews=requests),
    )
    try:
        with pytest.raises(RuntimeError, match="simulated second-write failure"):
            import_unified_ai_update(session, update)
        assert session.scalar(text("SELECT COUNT(*) FROM import_probe")) == 0
    finally:
        session.close()
