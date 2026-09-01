from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AIExchangeSection = Literal[
    "capture_jobs",
    "review_inbox",
    "applications",
    "job_search_preferences",
    "market_insights",
    "skills_gaps",
    "linkedin_profile",
    "professional_evidence",
    "search_preferences",
    "outcomes_strategy",
    "data_quality",
    "global_context",
]

AIAnalysisType = Literal[
    "classification",
    "extraction",
    "recommendation",
    "correction",
    "context_update",
    "market_signal",
    "gap_signal",
    "priority_update",
    "duplicate_link",
    "audit_result",
]


class AIExchangeScope(BaseModel):
    section: AIExchangeSection
    analysis_types: list[AIAnalysisType] = Field(min_length=1)
    scope_id: str | None = None
    scope_label: str | None = None


class AIExchangeInput(BaseModel):
    contract_type: Literal["jolt_ai_exchange_input"] = "jolt_ai_exchange_input"
    contract_version: Literal["1.0"] = "1.0"
    generated_at: datetime
    exchange_id: str = Field(min_length=1)
    context_version: str | None = None
    scope: AIExchangeScope
    context: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)
    protected_state: dict[str, Any] = Field(default_factory=dict)
    requested_output: dict[str, Any] = Field(default_factory=dict)


class AIExchangeFeedbackItem(BaseModel):
    feedback_type: AIAnalysisType
    entity_type: str = Field(min_length=1)
    entity_id: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: int | None = Field(default=None, ge=0, le=100)
    evidence_refs: list[str] = Field(default_factory=list)


class AIExchangeOutput(BaseModel):
    contract_type: Literal["jolt_ai_exchange_output"] = "jolt_ai_exchange_output"
    contract_version: Literal["1.0"] = "1.0"
    exchange_id: str = Field(min_length=1)
    reviewed_at: datetime
    review_source: Literal["chatgpt"] = "chatgpt"
    review_version: str = Field(min_length=1, max_length=80)
    scope: AIExchangeScope
    feedback: list[AIExchangeFeedbackItem] = Field(default_factory=list)
    context_patch: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
