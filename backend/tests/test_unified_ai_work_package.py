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


def test_unified_update_rejects_user_owned_context_patch(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    update = UnifiedAIUpdate(
        package_id="package-1",
        reviewed_at=datetime.now(UTC),
        review_version="unified-v1",
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )
    try:
        with pytest.raises(ValueError, match="non-patchable"):
            import_unified_ai_update(session, update)
    finally:
        session.close()


def test_unified_update_requires_section_context_patch_at_top_level(tmp_path) -> None:
    session = create_session_factory(f"sqlite:///{(tmp_path / 'jolt.db').as_posix()}")()
    output = AIExchangeOutput(
        exchange_id="market-1",
        reviewed_at=datetime.now(UTC),
        review_version="market-v1",
        scope=AIExchangeScope(section="market_insights", analysis_types=["context_update"]),
        context_patch={"market_summary": {"signal": "example"}},
    )
    update = UnifiedAIUpdate(
        package_id="package-1",
        reviewed_at=datetime.now(UTC),
        review_version="unified-v1",
        exchanges=[output],
    )
    try:
        with pytest.raises(ValueError, match="top-level context_patch"):
            import_unified_ai_update(session, update)
    finally:
        session.close()
