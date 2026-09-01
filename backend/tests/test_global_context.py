from datetime import UTC, datetime

import pytest

from jolt.ai_exchange_contract import AIExchangeOutput, AIExchangeScope
from jolt.global_context import (
    GlobalAIContextOverlay,
    apply_global_context_patch,
    build_global_context_exchange,
    global_context_version,
)


def test_global_context_exchange_protects_user_owned_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "jolt.global_context.load_global_ai_context",
        lambda: GlobalAIContextOverlay(market_summary={"sample": True}),
    )

    document = build_global_context_exchange()

    assert document.scope.section == "global_context"
    assert "job_search_preferences" in document.context
    assert "ai_context" in document.context
    assert "job_search_preferences" in document.protected_state["non_patchable"]
    assert "applications" in document.protected_state["non_patchable"]
    assert "human_review_decisions" in document.protected_state["non_patchable"]
    assert "market_summary" in document.protected_state["patchable_namespaces"]


def test_global_context_version_is_content_addressed() -> None:
    snapshot = {"a": 1, "b": {"c": 2}}
    assert global_context_version(snapshot) == global_context_version({"b": {"c": 2}, "a": 1})
    assert global_context_version(snapshot) != global_context_version({"a": 2})


def test_context_patch_updates_only_allowed_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    current = GlobalAIContextOverlay(
        market_summary={"old": True},
        profile_strategy={"keep": True},
    )
    saved: list[GlobalAIContextOverlay] = []
    monkeypatch.setattr("jolt.global_context.load_global_ai_context", lambda: current)
    monkeypatch.setattr(
        "jolt.global_context.save_global_ai_context",
        lambda value: saved.append(value) or value,
    )

    output = AIExchangeOutput(
        exchange_id="exchange-1",
        reviewed_at=datetime.now(UTC),
        review_version="chatgpt-phase2-test",
        scope=AIExchangeScope(section="global_context", analysis_types=["context_update"]),
        context_patch={"market_summary": {"new": True}},
    )

    result = apply_global_context_patch(output)

    assert result.market_summary == {"new": True}
    assert result.profile_strategy == {"keep": True}
    assert result.updated_by == "chatgpt:chatgpt-phase2-test"
    assert saved == [result]


def test_context_patch_rejects_jolt_owned_namespace() -> None:
    output = AIExchangeOutput(
        exchange_id="exchange-2",
        reviewed_at=datetime.now(UTC),
        review_version="chatgpt-phase2-test",
        scope=AIExchangeScope(section="global_context", analysis_types=["context_update"]),
        context_patch={"job_search_preferences": {"languages": ["German"]}},
    )

    with pytest.raises(ValueError, match="non-patchable"):
        apply_global_context_patch(output)


def test_context_patch_rejects_wrong_scope() -> None:
    output = AIExchangeOutput(
        exchange_id="exchange-3",
        reviewed_at=datetime.now(UTC),
        review_version="chatgpt-phase2-test",
        scope=AIExchangeScope(section="market_insights", analysis_types=["context_update"]),
    )

    with pytest.raises(ValueError, match="global_context"):
        apply_global_context_patch(output)
