from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from jolt import global_context
from jolt.ai_exchange_contract import AIExchangeOutput, AIExchangeScope
from jolt.global_context import (
    CURRENT_REASONING_POLICY_VERSION,
    GlobalAIContextOverlay,
    apply_global_context_patch,
    build_global_context_snapshot,
    load_global_ai_context,
    save_global_ai_context,
)


def _bind_paths(monkeypatch, tmp_path: Path) -> Path:
    context_path = tmp_path / "data" / "ai_context_overlay.json"
    history_dir = tmp_path / "data" / "ai_context_history"
    monkeypatch.setattr(global_context, "_data_path", lambda: context_path)
    monkeypatch.setattr(global_context, "_history_dir", lambda: history_dir)
    return context_path


def _write_legacy_context(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "updated_at": "2026-09-01T19:30:00+00:00",
                "updated_by": "chatgpt:pre-hardline-review",
                "market_summary": {"top_roles": ["Old role priority"]},
                "application_strategy": {"priority_jobs": ["Superseded job"]},
                "audit_summary": {"note": "historical"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_legacy_ai_strategy_is_not_exposed_as_active_context(tmp_path, monkeypatch) -> None:
    path = _bind_paths(monkeypatch, tmp_path)
    _write_legacy_context(path)

    active = load_global_ai_context()

    assert active.reasoning_policy_version == CURRENT_REASONING_POLICY_VERSION
    assert active.market_summary == {}
    assert active.application_strategy == {}
    assert active.audit_summary == {}


def test_snapshot_marks_legacy_namespaces_superseded_without_exporting_them(
    tmp_path,
    monkeypatch,
) -> None:
    path = _bind_paths(monkeypatch, tmp_path)
    _write_legacy_context(path)
    monkeypatch.setattr(
        global_context,
        "load_job_search_preferences",
        lambda: type(
            "Preferences",
            (),
            {"model_dump": lambda self, mode=None: {"languages": ["English", "Spanish"]}},
        )(),
    )

    snapshot = build_global_context_snapshot()

    assert snapshot["ai_context"]["market_summary"] == {}
    assert snapshot["ai_context"]["application_strategy"] == {}
    assert snapshot["ai_context_status"]["active"] is False
    assert snapshot["ai_context_status"]["stored_reasoning_policy_version"] is None
    assert snapshot["ai_context_status"]["current_reasoning_policy_version"] == (
        CURRENT_REASONING_POLICY_VERSION
    )
    assert snapshot["ai_context_status"]["superseded_namespaces"] == [
        "application_strategy",
        "audit_summary",
        "market_summary",
    ]


def test_current_policy_save_archives_superseded_overlay_before_replacement(
    tmp_path,
    monkeypatch,
) -> None:
    path = _bind_paths(monkeypatch, tmp_path)
    _write_legacy_context(path)

    saved = save_global_ai_context(
        GlobalAIContextOverlay(
            audit_summary={"status": "revalidated"},
            updated_at=datetime(2026, 9, 3, tzinfo=UTC),
            updated_by="chatgpt:hardline-review",
        )
    )

    assert saved.reasoning_policy_version == CURRENT_REASONING_POLICY_VERSION
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["reasoning_policy_version"] == CURRENT_REASONING_POLICY_VERSION
    assert persisted["market_summary"] == {}
    assert persisted["application_strategy"] == {}
    assert persisted["audit_summary"] == {"status": "revalidated"}

    archives = list((tmp_path / "data" / "ai_context_history").glob("*.json"))
    assert len(archives) == 1
    historical = json.loads(archives[0].read_text(encoding="utf-8"))
    assert historical["application_strategy"] == {"priority_jobs": ["Superseded job"]}
    assert historical["market_summary"] == {"top_roles": ["Old role priority"]}
    assert historical["reasoning_policy_version"] is None


def test_partial_new_patch_does_not_carry_stale_namespaces_forward(tmp_path, monkeypatch) -> None:
    path = _bind_paths(monkeypatch, tmp_path)
    _write_legacy_context(path)

    output = AIExchangeOutput(
        exchange_id="global-context-test",
        reviewed_at=datetime(2026, 9, 3, tzinfo=UTC),
        review_version="hardline-context-test",
        scope=AIExchangeScope(
            section="global_context",
            analysis_types=["context_update"],
        ),
        context_patch={"audit_summary": {"status": "fresh"}},
    )

    saved = apply_global_context_patch(output)

    assert saved.reasoning_policy_version == CURRENT_REASONING_POLICY_VERSION
    assert saved.audit_summary == {"status": "fresh"}
    assert saved.market_summary == {}
    assert saved.application_strategy == {}


def test_empty_legacy_overlay_is_safe_and_does_not_create_history(tmp_path, monkeypatch) -> None:
    path = _bind_paths(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(GlobalAIContextOverlay().model_dump_json(indent=2), encoding="utf-8")

    active = load_global_ai_context()
    assert active.reasoning_policy_version == CURRENT_REASONING_POLICY_VERSION

    save_global_ai_context(active)
    assert list((tmp_path / "data" / "ai_context_history").glob("*.json")) == []
