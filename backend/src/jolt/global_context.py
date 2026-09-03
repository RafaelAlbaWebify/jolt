from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.ai_review_pack import REVIEW_CONTRACT_VERSION
from jolt.job_search_preferences import load_job_search_preferences

_CONTEXT_FILE = "ai_context_overlay.json"
_CONTEXT_HISTORY_DIR = "ai_context_history"
CURRENT_REASONING_POLICY_VERSION = f"hardline-review-{REVIEW_CONTRACT_VERSION}"
_ALLOWED_PATCH_KEYS = frozenset(
    {
        "market_summary",
        "skills_gap_summary",
        "professional_evidence_summary",
        "candidate_evidence_summary",
        "application_strategy",
        "profile_strategy",
        "capture_strategy",
        "outcome_strategy",
        "audit_summary",
    }
)


class GlobalAIContextOverlay(BaseModel):
    schema_version: str = "1.0"
    reasoning_policy_version: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None
    market_summary: dict[str, Any] = Field(default_factory=dict)
    skills_gap_summary: dict[str, Any] = Field(default_factory=dict)
    professional_evidence_summary: dict[str, Any] = Field(default_factory=dict)
    candidate_evidence_summary: dict[str, Any] = Field(default_factory=dict)
    application_strategy: dict[str, Any] = Field(default_factory=dict)
    profile_strategy: dict[str, Any] = Field(default_factory=dict)
    capture_strategy: dict[str, Any] = Field(default_factory=dict)
    outcome_strategy: dict[str, Any] = Field(default_factory=dict)
    audit_summary: dict[str, Any] = Field(default_factory=dict)


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / _CONTEXT_FILE


def _history_dir() -> Path:
    return _data_path().parent / _CONTEXT_HISTORY_DIR


def _empty_current_overlay() -> GlobalAIContextOverlay:
    return GlobalAIContextOverlay(reasoning_policy_version=CURRENT_REASONING_POLICY_VERSION)


def _derived_namespaces(context: GlobalAIContextOverlay) -> list[str]:
    payload = context.model_dump()
    return sorted(key for key in _ALLOWED_PATCH_KEYS if bool(payload.get(key)))


def _load_stored_global_ai_context() -> GlobalAIContextOverlay:
    path = _data_path()
    if not path.exists():
        return _empty_current_overlay()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return GlobalAIContextOverlay.model_validate(payload)
    except (json.JSONDecodeError, OSError, ValueError):
        return _empty_current_overlay()


def _is_current_reasoning_context(context: GlobalAIContextOverlay) -> bool:
    if context.reasoning_policy_version == CURRENT_REASONING_POLICY_VERSION:
        return True
    return not _derived_namespaces(context)


def load_global_ai_context() -> GlobalAIContextOverlay:
    """Return only AI context valid under the current reasoning policy.

    Superseded derived namespaces remain on disk for audit/history but are not exposed as
    active strategy and cannot hitchhike into a later patch.
    """

    stored = _load_stored_global_ai_context()
    if _is_current_reasoning_context(stored):
        if stored.reasoning_policy_version is None:
            return stored.model_copy(
                update={"reasoning_policy_version": CURRENT_REASONING_POLICY_VERSION}
            )
        return stored
    return _empty_current_overlay()


def _archive_superseded_context(context: GlobalAIContextOverlay) -> None:
    if _is_current_reasoning_context(context) or not _derived_namespaces(context):
        return
    rendered = context.model_dump_json(indent=2)
    digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:16]
    history_dir = _history_dir()
    history_dir.mkdir(parents=True, exist_ok=True)
    archive_path = history_dir / f"ai_context_overlay_{digest}.json"
    if not archive_path.exists():
        archive_path.write_text(rendered, encoding="utf-8")


def save_global_ai_context(context: GlobalAIContextOverlay) -> GlobalAIContextOverlay:
    path = _data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    _archive_superseded_context(_load_stored_global_ai_context())
    current_context = context.model_copy(
        update={"reasoning_policy_version": CURRENT_REASONING_POLICY_VERSION}
    )
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary_path.write_text(current_context.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return current_context


def _context_status(stored: GlobalAIContextOverlay) -> dict[str, Any]:
    superseded_namespaces = (
        _derived_namespaces(stored) if not _is_current_reasoning_context(stored) else []
    )
    return {
        "current_reasoning_policy_version": CURRENT_REASONING_POLICY_VERSION,
        "stored_reasoning_policy_version": stored.reasoning_policy_version,
        "active": not superseded_namespaces,
        "superseded_namespaces": superseded_namespaces,
        "stored_updated_at": stored.updated_at.isoformat() if stored.updated_at else None,
        "stored_updated_by": stored.updated_by,
        "history_policy": (
            "Superseded AI-derived strategy is excluded from active reasoning and archived "
            "when a current-policy update replaces it."
        ),
    }


def build_global_context_snapshot() -> dict[str, Any]:
    preferences = load_job_search_preferences()
    stored = _load_stored_global_ai_context()
    active = load_global_ai_context()
    return {
        "job_search_preferences": preferences.model_dump(mode="json"),
        "ai_context": active.model_dump(mode="json"),
        "ai_context_status": _context_status(stored),
        "ownership": {
            "job_search_preferences": "jolt_user_owned",
            "ai_context": "chatgpt_derived_user_reviewable_current_policy_only",
            "ai_context_history": "preserved_not_reasoning_authority",
            "human_review_decisions": "protected_not_patchable_here",
            "applications": "protected_not_patchable_here",
        },
    }


def global_context_version(snapshot: dict[str, Any] | None = None) -> str:
    payload = snapshot if snapshot is not None else build_global_context_snapshot()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"global-context-{digest}"


def build_global_context_exchange() -> AIExchangeInput:
    snapshot = build_global_context_snapshot()
    return AIExchangeInput(
        generated_at=datetime.now(UTC),
        exchange_id=str(uuid4()),
        context_version=global_context_version(snapshot),
        scope=AIExchangeScope(
            section="global_context",
            analysis_types=["context_update", "recommendation", "audit_result"],
            scope_label="JOLT global reasoning context",
        ),
        context=snapshot,
        protected_state={
            "patchable_namespaces": sorted(_ALLOWED_PATCH_KEYS),
            "non_patchable": ["job_search_preferences", "human_review_decisions", "applications"],
        },
        requested_output={
            "context_patch": "Return only changed AI-owned namespaces. Do not rewrite JOLT-owned facts.",
            "feedback": "Use structured feedback for recommendations or audit findings.",
        },
    )


def apply_global_context_patch(output: AIExchangeOutput) -> GlobalAIContextOverlay:
    if output.scope.section != "global_context":
        raise ValueError("Global context import requires scope.section=global_context")

    unknown = sorted(set(output.context_patch) - _ALLOWED_PATCH_KEYS)
    if unknown:
        raise ValueError(f"Global context patch contains non-patchable keys: {', '.join(unknown)}")

    current = load_global_ai_context()
    update = current.model_dump()
    for key, value in output.context_patch.items():
        if not isinstance(value, dict):
            raise ValueError(f"Global context namespace '{key}' must be an object")
        update[key] = value
    update["updated_at"] = output.reviewed_at
    update["updated_by"] = f"chatgpt:{output.review_version}"
    return save_global_ai_context(GlobalAIContextOverlay.model_validate(update))
