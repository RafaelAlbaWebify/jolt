from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from jolt.ai_exchange_contract import AIExchangeInput, AIExchangeOutput, AIExchangeScope
from jolt.job_search_preferences import load_job_search_preferences

_CONTEXT_FILE = "ai_context_overlay.json"
_ALLOWED_PATCH_KEYS = frozenset(
    {
        "market_summary",
        "skills_gap_summary",
        "professional_evidence_summary",
        "application_strategy",
        "profile_strategy",
        "capture_strategy",
        "outcome_strategy",
        "audit_summary",
    }
)


class GlobalAIContextOverlay(BaseModel):
    schema_version: str = "1.0"
    updated_at: datetime | None = None
    updated_by: str | None = None
    market_summary: dict[str, Any] = Field(default_factory=dict)
    skills_gap_summary: dict[str, Any] = Field(default_factory=dict)
    professional_evidence_summary: dict[str, Any] = Field(default_factory=dict)
    application_strategy: dict[str, Any] = Field(default_factory=dict)
    profile_strategy: dict[str, Any] = Field(default_factory=dict)
    capture_strategy: dict[str, Any] = Field(default_factory=dict)
    outcome_strategy: dict[str, Any] = Field(default_factory=dict)
    audit_summary: dict[str, Any] = Field(default_factory=dict)


def _data_path() -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "data" / _CONTEXT_FILE


def load_global_ai_context() -> GlobalAIContextOverlay:
    path = _data_path()
    if not path.exists():
        return GlobalAIContextOverlay()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return GlobalAIContextOverlay.model_validate(payload)
    except (json.JSONDecodeError, OSError, ValueError):
        return GlobalAIContextOverlay()


def save_global_ai_context(context: GlobalAIContextOverlay) -> GlobalAIContextOverlay:
    path = _data_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary_path.write_text(context.model_dump_json(indent=2), encoding="utf-8")
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    return context


def build_global_context_snapshot() -> dict[str, Any]:
    preferences = load_job_search_preferences()
    overlay = load_global_ai_context()
    return {
        "job_search_preferences": preferences.model_dump(mode="json"),
        "ai_context": overlay.model_dump(mode="json"),
        "ownership": {
            "job_search_preferences": "jolt_user_owned",
            "ai_context": "chatgpt_derived_user_reviewable",
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
